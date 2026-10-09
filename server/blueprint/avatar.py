"""Optional video avatar for the Narrator.

Off by default. Set ``AVATAR_PROVIDER=anam`` (plus ``ANAM_API_KEY`` and
``ANAM_AVATAR_ID``) and the narrator's TTS audio is lip-synced by an Anam
avatar, through Anam's ``pipecat-anam`` plugin. Its video is streamed to the
client over the same WebRTC connection, with the audio re-timed to match.

The avatar never costs the voice: while Anam is still connecting, and after any
Anam error or session end, the TTS audio goes straight to the transport and the
session carries on voice only (see ``_resilient``).

Tavus and HeyGen work the same way in Pipecat (``TavusVideoService``,
``HeyGenVideoService``); add a branch below when you pick one. Both need an
``aiohttp.ClientSession`` that lives as long as the session.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

import yaml
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

# Anam sends 3:2 video. The transport scales to this size, so a different aspect
# ratio here would stretch the presenter.
AVATAR_WIDTH = 720
AVATAR_HEIGHT = 480

TTS_FRAMES = (TTSStartedFrame, TTSAudioRawFrame, TTSStoppedFrame)


def selected_avatar() -> dict:
    """The narrator's entry in avatars.yaml: AVATAR_ID, else the file's default_avatar.

    Empty when there is no catalog file, so the env-only setup keeps working.
    """
    path = Path(os.getenv("AVATARS_FILE") or Path(__file__).parent.parent / "avatars.yaml")
    if not path.exists():
        return {}
    catalog = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    avatars = {a["id"]: a for a in catalog.get("avatars", [])}
    avatar_id = os.getenv("AVATAR_ID") or catalog.get("default_avatar")
    if avatar_id not in avatars:
        raise ValueError(
            f"Unknown avatar {avatar_id!r} in {path}. Use one of: {', '.join(avatars)}."
        )
    return avatars[avatar_id]


def _provider() -> str:
    return os.getenv("AVATAR_PROVIDER", "none").strip().lower()


def avatar_enabled() -> bool:
    return _provider() not in ("", "none")


def _resilient(base: type) -> type:
    """Wrap pipecat-anam's service so an avatar problem costs the video, not the voice.

    The plugin never forwards TTS audio itself: it hands it to Anam and plays back
    what Anam returns, whether or not Anam is connected. On its own, a failed
    connect, a session Anam ends, or a send error therefore leaves the bot silent.
    This wrapper plays every utterance Anam cannot take straight through the
    transport, and tells the client once when the avatar is gone.

    Relies on pipecat-anam 0.1.0 internals: ``_session_ready_event``, ``_send_task``,
    ``_agent_audio_stream``, ``_connect_task``, ``_close_session`` and
    ``_on_connection_closed``.
    """

    class ResilientAnamVideoService(base):
        _unavailable = False
        # Called once, with the reason, when the avatar is gone; the bot uses it to stop
        # waiting for the video before it speaks.
        on_unavailable: Callable[[str], Awaitable[None]] | None = None
        # Utterances remembered, so audio chunks arriving after their stop frame still
        # find their route.
        _ROUTES_KEPT = 8

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # TTS context id -> True when that utterance plays through the transport.
            self._direct: dict[str, bool] = {}

        def _anam_ready(self) -> bool:
            """True while Anam has said it can take TTS and the plugin's send loop is alive."""
            send_task = getattr(self, "_send_task", None)
            ready = getattr(self, "_session_ready_event", None)
            return (
                not self._unavailable
                and ready is not None
                and ready.is_set()
                and send_task is not None
                and not send_task.done()
                and getattr(self, "_agent_audio_stream", None) is not None
            )

        def _plays_direct(self, frame: Frame) -> bool:
            """Decided at each TTSStartedFrame; the audio and stop frames follow it."""
            ctx = getattr(frame, "context_id", None)
            ctx = "__legacy__" if ctx is None else ctx
            if isinstance(frame, TTSStartedFrame) or ctx not in self._direct:
                self._direct[ctx] = not self._anam_ready()
                while len(self._direct) > self._ROUTES_KEPT:
                    self._direct.pop(next(iter(self._direct)))
            return self._direct[ctx]

        async def _mark_unavailable(self, reason: str) -> None:
            if self._unavailable:
                return
            self._unavailable = True
            logger.warning(f"Avatar unavailable, continuing with voice only: {reason}")
            await self.push_frame(
                RTVIServerMessageFrame(data={"type": "avatar_unavailable", "reason": reason})
            )
            if self.on_unavailable:
                await self.on_unavailable(reason)

        async def push_error_frame(self, error: ErrorFrame, force_treat_as_permanent=False):
            # The plugin reports a failed connect (e.g. Anam's concurrent session limit)
            # as fatal, which would end the session, and audio send/consume errors as
            # plain errors while it keeps swallowing the TTS audio. Either way: voice only.
            await self._mark_unavailable(str(error.error))

        async def _on_connection_closed(self, code: str, reason: str | None = None) -> None:
            # The plugin ignores a normal close (session length reached, ended by Anam)
            # and would stay silent for the rest of the session.
            await super()._on_connection_closed(code, reason)
            detail = f"Anam session closed: {code}"
            if reason:
                detail += f" - {reason}"
            await self._mark_unavailable(detail)

        async def process_frame(self, frame: Frame, direction: FrameDirection):
            if self._unavailable or (isinstance(frame, TTS_FRAMES) and self._plays_direct(frame)):
                # Around the plugin, TTS audio included, so the voice plays. Start, End
                # and Cancel still reach the plugin's own handlers through the base class.
                await FrameProcessor.process_frame(self, frame, direction)
                await self.push_frame(frame, direction)
                return
            await super().process_frame(frame, direction)

        async def _close_session(self):
            # A client that drops while the avatar is still connecting would leave the
            # Anam session open (and block the next one on single-session plans). Let
            # the connect finish so there is a session to close.
            task = self._connect_task
            if task and not task.done() and task is not asyncio.current_task():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=15)
                except Exception:
                    pass
            await super()._close_session()

    return ResilientAnamVideoService


def build_avatar() -> FrameProcessor | None:
    provider = _provider()
    if provider in ("", "none"):
        return None
    if provider == "anam":
        from anam import PersonaConfig
        from pipecat_anam import AnamVideoService

        # ANAM_AVATAR_ID overrides the catalog; the catalog's model belongs to its own id.
        host = {} if os.getenv("ANAM_AVATAR_ID") else selected_avatar()
        return _resilient(AnamVideoService)(
            api_key=os.environ["ANAM_API_KEY"],
            # pipecat-anam 0.1.0 passes None through, which becomes ".../None/engine/session".
            api_version="v1",
            persona_config=PersonaConfig(
                avatar_id=os.getenv("ANAM_AVATAR_ID") or host["anam_avatar_id"],
                avatar_model=host.get("anam_avatar_model"),
                # Lip-sync our TTS audio instead of using Anam's own LLM and voice.
                enable_audio_passthrough=True,
            ),
            # Anam records sessions unless told not to.
            enable_session_replay=os.getenv("ANAM_SESSION_REPLAY", "0") == "1",
        )
    logger.warning(f"AVATAR_PROVIDER={provider!r} is not wired yet; running without avatar")
    return None
