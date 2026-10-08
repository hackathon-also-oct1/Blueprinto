"""The voice agent: listens, talks, and starts the agent team when asked.

    mic → SLNG STT → user aggregator → Azure OpenAI (Responses API, tools) → agent chain → TTS

The LLM has one tool, ``start_blueprint``. It pushes a ``StartBlueprintFrame``
down the pipeline, where the Orchestrator turns it into a run, exactly as it
does for a requirement typed in the browser. When the run ends, the Narrator
hands the result back so the agent can report it and answer questions.

Needs ``SLNG_API_KEY`` (speech) and the Azure OpenAI settings (the model). Without
them the app keeps working from the text box alone.
"""

from __future__ import annotations

import os

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.responses.llm import OpenAIResponsesHttpLLMService
from pipecat.transcriptions.language import Language
from pydantic import ValidationError

from blueprint.azure_llm import AgentLLM
from blueprint.frames import StartBlueprintFrame
from blueprint.models import RunRequest

SYSTEM = """You are the presenter of Blueprint Agent Studio, a tool where a team of AI agents \
turns a product requirement into wireframes, a budget, a timeline and a team plan.

Your job is to find out what the user wants to build and then start the agent team.
- If the user has not said what to build, ask. One short question at a time.
- As soon as you know the product and its main features, call start_blueprint. Write the \
requirement yourself as a few complete sentences covering who uses the product and what they \
can do, using what the user told you. Do not ask for more detail than you need; a couple of \
sentences from the user is enough.
- After calling it, tell the user the agents are working and that it takes about a minute. \
Do not call it again while a run is in progress.
- When you are told a run finished, report the result, then answer questions about it from \
what you were told. Start a new run only if the user asks for a change or a new product.

Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that \
can't be spoken. Keep every reply to one to three short sentences."""

GREETING = "Greet the user in one sentence and ask what product they would like to plan."


def world_part() -> str:
    """SLNG region. Maps the old zone names so SLNG_WORLD_PART=eu keeps working."""
    value = os.getenv("SLNG_WORLD_PART", "eu-north")
    return {"eu": "eu-north", "na": "us-east"}.get(value, value)


def conversation_enabled(agent_llm: AgentLLM) -> bool:
    return bool(os.getenv("SLNG_API_KEY")) and not agent_llm.mock


def build_stt():
    from pipecat_slng import SlngSTTService

    return SlngSTTService(
        api_key=os.environ["SLNG_API_KEY"],
        world_part=world_part(),
        model=os.getenv("SLNG_STT_MODEL", "deepgram/nova:3"),
        language=Language.EN,
    )


async def start_blueprint(params: FunctionCallParams, requirement: str, platform: str = "both"):
    """Start the agent team on a product requirement. Results appear on screen in about a minute.

    Args:
        requirement: The product to plan, as a few complete sentences: who uses it and what
            they can do.
        platform: Where it runs: "web", "mobile" or "both".
    """
    try:
        request = RunRequest(
            requirement=requirement,
            platform=platform if platform in ("web", "mobile", "both") else "both",  # type: ignore[arg-type]
        )
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
