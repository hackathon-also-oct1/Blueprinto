"""The Anam wrapper never lets the avatar cost the voice. No Anam account needed.

uv run pytest -q tests/test_avatar.py
"""

import asyncio
from dataclasses import dataclass

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from pipecat.tests.utils import run_test

from blueprint.avatar import _resilient


@dataclass
class AnamHangsUp(Frame):
    """Test only: Anam ends the session normally (for example, its length limit)."""


@dataclass
class AnamBreaks(Frame):
    """Test only: the plugin hits an error that is not a connect failure."""


class FakeAnam(FrameProcessor):
    """Stands in for pipecat-anam's AnamVideoService.

    Like the real one, it hands TTS frames to Anam and never forwards the audio
    itself, connected or not, and it does nothing on a normal session close.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session_ready_event = asyncio.Event()
        self._send_task = None
        self._agent_audio_stream = None
        self._connect_task = None
        self.sent_to_anam: list[Frame] = []

    def ready(self):
        self._session_ready_event.set()
        self._send_task = asyncio.get_running_loop().create_future()  # pending: a live loop
        self._agent_audio_stream = object()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, AnamHangsUp):
            await self._on_connection_closed("normal", "max session length reached")
            return
        if isinstance(frame, AnamBreaks):
            await self.push_error_frame(ErrorFrame(error="Anam audio send error: boom"))
            return
        if isinstance(frame, (TTSStartedFrame, TTSAudioRawFrame, TTSStoppedFrame)):
            self.sent_to_anam.append(frame)
            if isinstance(frame, TTSAudioRawFrame):
                return
        await self.push_frame(frame, direction)

    async def _on_connection_closed(self, code, reason=None):
        pass

    async def _close_session(self):
        pass


def utterance(ctx: str, chunks: int = 2) -> list[Frame]:
    frames: list[Frame] = [TTSStartedFrame(context_id=ctx)]
    frames += [
        TTSAudioRawFrame(audio=b"\0\0" * 160, sample_rate=16000, num_channels=1, context_id=ctx)
        for _ in range(chunks)
    ]
    frames.append(TTSStoppedFrame(context_id=ctx))
    return frames


def heard(frames):
    """Context ids of the TTS audio that reached the transport."""
    return [f.context_id for f in frames if isinstance(f, TTSAudioRawFrame)]


def notices(frames):
    return [f.data["type"] for f in frames if isinstance(f, RTVIServerMessageFrame)]


async def test_voice_plays_through_while_anam_connects():
    avatar = _resilient(FakeAnam)()
    down, _ = await run_test(avatar, frames_to_send=utterance("greeting"))
    assert heard(down) == ["greeting", "greeting"]
    assert avatar.sent_to_anam == []  # not queued, so Anam will not replay it later
    assert notices(down) == []  # a connecting avatar is not a problem to report


async def test_anam_lip_syncs_once_ready():
    avatar = _resilient(FakeAnam)()
    avatar.ready()
    down, _ = await run_test(avatar, frames_to_send=utterance("answer"))
    assert heard(down) == []  # Anam plays this one back, lip-synced
    assert heard(avatar.sent_to_anam) == ["answer", "answer"]


async def test_voice_returns_after_anam_ends_the_session():
    avatar = _resilient(FakeAnam)()
    avatar.ready()
    down, _ = await run_test(
        avatar, frames_to_send=[*utterance("first"), AnamHangsUp(), *utterance("second")]
    )
    assert heard(avatar.sent_to_anam) == ["first", "first"]
    assert heard(down) == ["second", "second"]
    assert notices(down) == ["avatar_unavailable"]


async def test_any_anam_error_means_voice_only_not_silence():
    avatar = _resilient(FakeAnam)()
    avatar.ready()
    down, up = await run_test(
        avatar, frames_to_send=[*utterance("first"), AnamBreaks(), *utterance("second")]
    )
    assert heard(down) == ["second", "second"]
    assert notices(down) == ["avatar_unavailable"]
    assert not any(isinstance(f, ErrorFrame) for f in up)  # the session is not ended
