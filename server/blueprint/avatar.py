"""Optional video avatar for the Narrator.

Off by default. Set ``AVATAR_PROVIDER=anam`` (plus ``ANAM_API_KEY`` and
``ANAM_AVATAR_ID``) and the narrator's Azure TTS audio is lip-synced by an Anam
avatar, through Anam's ``pipecat-anam`` plugin. Its video is streamed to the
client over the same WebRTC connection, with the audio re-timed to match.

Tavus and HeyGen work the same way in Pipecat (``TavusVideoService``,
``HeyGenVideoService``); add a branch below when you pick one. Both need an
``aiohttp.ClientSession`` that lives as long as the session.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import yaml
from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

# Anam sends 3:2 video. The transport scales to this size, so a different aspect
# ratio here would stretch the presenter.
AVATAR_WIDTH = 720
AVATAR_HEIGHT = 480


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
    """Wrap pipecat-anam's service so an avatar problem costs the video, not the session."""

    class ResilientAnamVideoService(base):
        _unavailable = False

        async def push_error_frame(self, error: ErrorFrame, force_treat_as_permanent=False):
            # The plugin reports a failed connect (e.g. Anam's concurrent session limit)
            # as fatal, which would end the session. Carry on with voice only instead.
            if not self._unavailable and "connect" in str(error.error).lower():
                self._unavailable = True
                logger.warning(f"Avatar unavailable, continuing with voice only: {error.error}")
                await self.push_frame(
                    RTVIServerMessageFrame(
                        data={"type": "avatar_unavailable", "reason": str(error.error)}
                    )
                )
                return
            await super().push_error_frame(error, force_treat_as_permanent)

        async def process_frame(self, frame: Frame, direction: FrameDirection):
            if self._unavailable:
                # Pass everything through, TTS audio included, so the voice still plays.
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
