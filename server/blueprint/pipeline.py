"""Assembles the agent chain that sits inside the Pipecat pipeline.

    Orchestrator → Requirements Analyst → UX Architect → Wireframe Builder
                 → Estimator → Publisher → Narrator

Each arrow is a Pipecat frame hand-off: the ``BlueprintRunFrame`` moves down the
pipeline, and every agent streams its status to the browser over RTVI.
"""

from __future__ import annotations

from pipecat.processors.frame_processor import FrameProcessor

from blueprint.agents import (
    Estimator,
    Narrator,
    Orchestrator,
    Publisher,
    RequirementsAnalyst,
    UXArchitect,
    WireframeBuilder,
)
from blueprint.azure_llm import AgentLLM
from blueprint.storage import RunStore


def build_agent_chain(
    llm: AgentLLM | None = None,
    store: RunStore | None = None,
    speak: bool = False,
    converse: bool = False,
) -> list[FrameProcessor]:
    llm = llm or AgentLLM()
    store = store or RunStore()

    agents = [
        RequirementsAnalyst(llm),
        UXArchitect(llm),
        WireframeBuilder(llm),
        Estimator(llm),
        Publisher(llm, store),
    ]
    roster = [
        {"id": Orchestrator.agent_id, "title": Orchestrator.title, "service": Orchestrator.service}
    ]
    roster += [{"id": a.agent_id, "title": a.title, "service": a.service} for a in agents]

    return [
        Orchestrator(roster, mock=llm.mock),
        *agents,
        Narrator(store, speak=speak, converse=converse),
    ]
