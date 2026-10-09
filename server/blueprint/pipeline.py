"""Assembles the agent chain that sits inside the Pipecat pipeline.

    Orchestrator → Domain Classifier → [Requirements Analyst ∥ UX Architect]
                 → Wireframe Builder → Narrator

The Estimator (blueprint.agents.estimator) is not in the chain: the client states
their budget in the intake, so no budget is calculated.

The Requirements Analyst and the UX Architect run at the same time: the flow is
built from the requirement and its domain, so it does not wait for the spec.

Each arrow is a Pipecat frame hand-off: the ``BlueprintRunFrame`` moves down the
pipeline, and every agent streams its status to the browser over RTVI.
"""

from __future__ import annotations

from pipecat.processors.frame_processor import FrameProcessor

from blueprint.agents import (
    DomainClassifier,
    Narrator,
    Orchestrator,
    RequirementsAnalyst,
    UXArchitect,
    WireframeBuilder,
)
from blueprint.agents.base import ParallelAgents
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
        DomainClassifier(llm),
        RequirementsAnalyst(llm),
        UXArchitect(llm),
        WireframeBuilder(llm),
    ]
    roster = [
        {"id": Orchestrator.agent_id, "title": Orchestrator.title, "service": Orchestrator.service}
    ]
    roster += [{"id": a.agent_id, "title": a.title, "service": a.service} for a in agents]

    domain, analyst, ux, *rest = agents
    return [
        Orchestrator(roster, mock=llm.mock),
        domain,
        ParallelAgents([analyst, ux]),
        *rest,
        Narrator(store, speak=speak, converse=converse),
    ]
