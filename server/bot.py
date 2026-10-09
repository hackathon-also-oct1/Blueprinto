#
# Blueprint Studio — Pipecat multi-agent server
#
# Scaffolded with the Pipecat CLI (`pipecat init`, SmallWebRTC + Azure) and
# adapted into a multi-agent pipeline driven by voice or text.
#

"""Blueprint Studio bot.

The user gives a requirement by talking to the presenter, or by typing it in the
browser (sent as an RTVI client message). Inside this Pipecat pipeline five agent
processors turn it into a UX flow and wireframes. Every agent streams its status
back to the browser as RTVI server messages.

Pipeline::

    transport.input()
      → SLNG STT → user context → Azure OpenAI voice agent     (with SLNG + Azure keys)
      → Orchestrator → Requirements Analyst → UX Architect → Wireframe Builder → Narrator
      → SLNG or Azure TTS (optional) → video avatar (optional)
      → transport.output() → assistant context

Run::

    uv run bot.py          # serves http://localhost:7860, client connects to /start
"""

import os

from dotenv import load_dotenv
from loguru import logger
from pipecat.frames.frames import LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

from blueprint.avatar import (
    AVATAR_HEIGHT,
    AVATAR_WIDTH,
    avatar_enabled,
    build_avatar,
    selected_avatar,
)
from blueprint.azure_llm import AgentLLM
from blueprint.conversation import (
    GREETING,
    Greeter,
    build_stt,
    build_voice_agent,
    conversation_enabled,
    world_part,
)
from blueprint.pipeline import build_agent_chain
from blueprint.storage import RunStore

load_dotenv(override=True)

# One store per server process, shared by sessions; the Narrator saves every run to it.
STORE = RunStore()

# With a video presenter, the opening line waits until the client says its video is
# showing (a ``presenter_ready`` message), so the visitor hears Nuno only once they can
# see him. A client that never says so is still greeted after this many seconds.
GREET_FALLBACK_SECS = 12


def build_tts():
    """Narrator voice: SLNG if SLNG_API_KEY is set, else Azure AI Speech, else none."""
    slng_key = os.getenv("SLNG_API_KEY")
    if slng_key:
        from pipecat_slng import SlngTTSService

        return SlngTTSService(
            api_key=slng_key,
            world_part=world_part(),
            model=os.getenv("SLNG_TTS_MODEL", "cartesia/sonic:3"),
            voice=os.getenv("SLNG_TTS_VOICE") or selected_avatar().get("voice"),
            encoding=os.getenv("SLNG_TTS_ENCODING", "linear16"),
            sample_rate=int(os.getenv("SLNG_TTS_SAMPLE_RATE", "24000")),
        )

    key = os.getenv("AZURE_SPEECH_API_KEY")
    if not key:
        return None
    from pipecat.services.azure.tts import AzureTTSService

    return AzureTTSService(
        api_key=key,
        region=os.getenv("AZURE_SPEECH_REGION"),
        settings=AzureTTSService.Settings(
            voice=os.getenv("AZURE_SPEECH_VOICE_ID", "en-US-AvaMultilingualNeural"),
        ),
    )


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    logger.info("Starting Blueprint Studio session")

    llm = AgentLLM()
    tts = build_tts()
    avatar = build_avatar() if tts else None
    converse = tts is not None and conversation_enabled(llm)

    processors = [transport.input()]
    if converse:
        voice_llm, context = build_voice_agent()
        processors += [build_stt(), context.user(), voice_llm]
    processors += build_agent_chain(llm, STORE, speak=tts is not None, converse=converse)
    if tts:
        processors.append(tts)
    if avatar:
        processors.append(avatar)
    processors.append(transport.output())
    if converse:
        processors.append(context.assistant())

    worker = PipelineWorker(
        Pipeline(processors),
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        # A planning session can sit idle while the user reads the results.
        idle_timeout_secs=30 * 60,
    )

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    async def say_opening_line() -> None:
        await worker.queue_frames(
            [
                LLMMessagesAppendFrame(
                    messages=[{"role": "developer", "content": GREETING}], run_llm=True
                )
            ]
        )

    # The opening line, once per session: when the client shows the presenter's video,
    # or right away when there is no video to wait for (see Greeter).
    greeter = Greeter(
        say_opening_line, wait_for_video=avatar is not None, fallback_secs=GREET_FALLBACK_SECS
    )
    if avatar is not None:
        avatar.on_unavailable = greeter.avatar_unavailable

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.send_server_message(
            {
                "type": "session_ready",
                "mock": llm.mock,
                "voice": tts is not None,
                "avatar": avatar is not None,
                "conversation": converse,
            }
        )
        if converse:
            await greeter.client_ready()

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        # The client's video is playing: the presenter can say hello.
        if message.type == "presenter_ready":
            await greeter.presenter_ready()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        greeter.cancel()
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Main bot entry point (discovered by the Pipecat dev runner)."""
    video = avatar_enabled()
    transport_params = {
        "webrtc": lambda: TransportParams(
            # The mic feeds the voice agent; typed requirements still work without it.
            audio_in_enabled=bool(os.getenv("SLNG_API_KEY")),
            audio_out_enabled=True,  # presenter voice
            video_out_enabled=video,
            video_out_is_live=video,
            video_out_width=AVATAR_WIDTH,
            video_out_height=AVATAR_HEIGHT,
        ),
    }
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    import sys

    from pipecat.runner.run import main

    # The runner's banner uses box-drawing characters. When output is piped (as under
    # `npm run dev`) Windows falls back to cp1252, which cannot encode them.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    main()
