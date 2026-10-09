"""The voice agent: asks three intake questions, then starts the agent team on "build it".

    mic → SLNG STT → user aggregator → Azure OpenAI (Responses API, tools) → agent chain → TTS

The LLM has one tool, ``start_blueprint``. It pushes a ``StartBlueprintFrame``
down the pipeline, where the Orchestrator turns it into a run, exactly as it
does for a requirement typed in the browser. When the run ends, the Narrator
hands the result back so the agent can report it and answer questions.

Needs ``SLNG_API_KEY`` (speech) and the Azure OpenAI settings (the model). Without
them the app keeps working from the text box alone.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.responses.llm import OpenAIResponsesHttpLLMService
from pipecat.transcriptions.language import Language
from pipecat_slng import SlngSTTService
from pydantic import ValidationError

from blueprint.azure_llm import AgentLLM
from blueprint.frames import StartBlueprintFrame
from blueprint.models import RunRequest

# The presenter's name, as the site introduces it.
AGENT_NAME = "Nuno"

QUESTIONS = (
    "What kind of website are you thinking about?",
    "About how many pages do you need?",
    "Roughly how much do you want to spend?",
)

# The opening line goes straight into the first intake question.
WELCOME = f"Hi, I'm {AGENT_NAME}. {QUESTIONS[0]}"

SYSTEM = f"""You are {AGENT_NAME}, the presenter of Blueprinto, a website consultancy's building app. A team \
of AI agents turns a client's brief into wireframes for their website. The client tells you their budget; you never
estimate or calculate one.

You open the conversation, once, with this line, word for word: "{WELCOME}" Never say it again
after that.

That line already asks the first of three intake questions. Ask exactly these three questions, in
this order, one per turn, in these words:
1. {QUESTIONS[0]}
2. {QUESTIONS[1]}
3. {QUESTIONS[2]}

Rules:
- Never ask any other question, and never ask for more detail. Accept whatever the client \
answers, even if it is vague, and move on to the next question. If an answer was unintelligible, \
repeat the same question once.
- After the third answer, do not start. Say you have what you need and that they can say \
"build it" when they are ready.
- Call start_blueprint only when the client says "build it" or clearly tells you to go ahead and \
build. Never call it on your own. If they say it before answering all three questions, start \
with what you have, as long as you know what kind of website they want.
- When you call start_blueprint, write the requirement yourself: the kind of website they want, \
the number of pages they asked for, and their budget.
- After calling it, tell the client the agents are working and that it takes about a minute. \
Do not call it again while a run is in progress.
- When you are told a run finished, report the result, then answer questions about it from \
what you were told. Start a new run only when the client says "build it" again.
- If the client asks you something, answer briefly, then return to the next unanswered question.

Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that \
can't be spoken. Keep every reply to one or two short sentences."""

# One-off: it stays in the context, so it must not read as a standing instruction.
GREETING = "The client has just connected. Say your opening line now, this one time."


class Greeter:
    """Has the presenter say its opening line exactly once per session, at the right moment.

    With a video presenter the line waits until the client reports that the video is
    showing (its ``presenter_ready`` message), so the visitor hears Nuno only once they
    can see him. Without one, or once the avatar has given up, the line goes out as soon
    as the client is ready. A client that never reports its video is greeted after
    ``fallback_secs`` anyway, so nobody is left in silence.
    """

    def __init__(
        self,
        speak: Callable[[], Awaitable[None]],
        *,
        wait_for_video: bool,
        fallback_secs: float = 12.0,
    ):
        self._speak = speak
        self._wait_for_video = wait_for_video
        self._fallback_secs = fallback_secs
        self._spoken = False
        self._client_ready = False
        self._video_showing = False
        self._timer: asyncio.Task | None = None

    @property
    def spoken(self) -> bool:
        return self._spoken

    async def client_ready(self) -> None:
        """The client finished the RTVI handshake and can take the bot's output."""
        self._client_ready = True
        if not self._wait_for_video or self._video_showing:
            await self._say()
        elif self._timer is None:
            self._timer = asyncio.create_task(self._fallback())

    async def presenter_ready(self) -> None:
        """The client reports the presenter's video is playing."""
        self._video_showing = True
        if self._client_ready:
            await self._say()

    async def avatar_unavailable(self, reason: str = "") -> None:
        """The avatar gave up: voice only from here on, so nothing is left to wait for."""
        self._wait_for_video = False
        if self._client_ready:
            await self._say()

    def cancel(self) -> None:
        """The session is over; stop a pending fallback."""
        if self._timer and not self._timer.done():
            self._timer.cancel()

    async def _fallback(self) -> None:
        await asyncio.sleep(self._fallback_secs)
        if not self._spoken:
            logger.info("No presenter_ready from the client; greeting anyway")
            await self._say()

    async def _say(self) -> None:
        if self._spoken:
            return
        self._spoken = True
        await self._speak()


def world_part() -> str:
    """SLNG region. Maps the old zone names so SLNG_WORLD_PART=eu keeps working."""
    value = os.getenv("SLNG_WORLD_PART", "eu-north")
    return {"eu": "eu-north", "na": "us-east"}.get(value, value)


def conversation_enabled(agent_llm: AgentLLM) -> bool:
    return bool(os.getenv("SLNG_API_KEY")) and not agent_llm.mock


class BatchedSlngSTT(SlngSTTService):
    """SLNG STT that stays inside the gateway's limits on a live microphone.

    WebRTC delivers 20 ms audio frames, 3000 a minute, and SLNG closes a socket
    that sends more than 2000 messages a minute, so audio goes out in 100 ms
    batches. With the mic muted no audio flows at all, and the provider drops
    the stream after about ten idle seconds, so keepalives start after three.
    """

    BATCH_SECS = 0.1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._keepalive_timeout = 3
        self._keepalive_interval = 2
        self._pending = b""

    async def run_stt(self, audio: bytes):
        self._pending += audio
        if len(self._pending) < int(self.sample_rate * 2 * self.BATCH_SECS):
            yield None
            return
        batch, self._pending = self._pending, b""
        async for frame in super().run_stt(batch):
            yield frame


def build_stt():
    return BatchedSlngSTT(
        api_key=os.environ["SLNG_API_KEY"],
        world_part=world_part(),
        model=os.getenv("SLNG_STT_MODEL", "deepgram/nova:3"),
        language=Language.EN,
    )


async def start_blueprint(params: FunctionCallParams, requirement: str):
    """Start the agent team building the plan. Call only after the client says "build it".

    Args:
        requirement: The website to plan, as a few complete sentences: what kind of website it is,
            how many pages it needs and the budget.
    """
    try:
        request = RunRequest(requirement=requirement)
    except ValidationError:
        await params.result_callback(
            {"started": False, "reason": "The requirement is too short. Ask for more detail."}
        )
        return
    await params.result_callback(
        {"started": True, "note": "The agents are working. You will be told when they finish."}
    )
    await params.llm.push_frame(StartBlueprintFrame(request=request))


def build_voice_agent() -> tuple[OpenAIResponsesHttpLLMService, LLMContextAggregatorPair]:
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].strip().rstrip("/")
    if not endpoint.endswith("/openai/v1"):
        endpoint += "/openai/v1"
    # The Responses API on Azure's v1 surface: reasoning deployments reject function
    # tools on chat completions, which is what AzureLLMService would use.
    llm = OpenAIResponsesHttpLLMService(
        base_url=endpoint + "/",
        api_key=os.environ["AZURE_OPENAI_API_KEY"].strip(),
        settings=OpenAIResponsesHttpLLMService.Settings(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
            system_instruction=SYSTEM,
        ),
    )
    context = LLMContext(tools=[start_blueprint])
    aggregators = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    return llm, aggregators
