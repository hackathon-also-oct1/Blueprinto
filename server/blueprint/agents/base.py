"""Base class for the agent processors.

Each agent is a Pipecat ``FrameProcessor``. When a ``BlueprintRunFrame`` arrives
it reports ``working`` to the client, does its part of the run, reports
``done`` (or ``error``) and pushes the frame on to the next agent. Status and
log lines reach the browser as RTVI server messages, which the client renders
as the live agent view.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from loguru import logger
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from blueprint.azure_llm import AgentLLM
from blueprint.frames import BlueprintRunFrame
from blueprint.models import BlueprintRun


class AgentProcessor(FrameProcessor):
    agent_id: str = "agent"
    title: str = "Agent"
    service: str = ""

    def __init__(self, llm: AgentLLM, **kwargs):
        super().__init__(name=self.title, **kwargs)
        self.llm = llm
        self._tokens = 0
        # Set by ParallelAgents: messages then go out through the stage, because an
        # agent inside a stage is not linked into the pipeline itself.
        self._sink: FrameProcessor | None = None

    # -- messaging helpers -------------------------------------------------

    async def emit(self, data: dict[str, Any]) -> None:
        await (self._sink or self).push_frame(RTVIServerMessageFrame(data=data))

    def count_tokens(self, run: BlueprintRun, tokens: int) -> None:
        """Add model tokens to the run and to this agent's own count."""
        run.tokens += tokens
        self._tokens += tokens

    async def log(self, run: BlueprintRun, message: str) -> None:
        logger.info(f"[{run.run_id}] {self.title}: {message}")
        await self.emit(
            {"type": "agent_log", "run_id": run.run_id, "agent": self.agent_id, "message": message}
        )

    async def status(self, run: BlueprintRun, status: str, **extra: Any) -> None:
        await self.emit(
            {
                "type": "agent_status",
                "run_id": run.run_id,
                "agent": self.agent_id,
                "status": status,
                **extra,
            }
        )

    async def mock_pause(self) -> None:
        """In mock mode, pause briefly so the live view is watchable."""
        if self.llm.mock:
            await asyncio.sleep(random.uniform(0.5, 1.1))

    # -- frame handling ----------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, BlueprintRunFrame) and frame.run.error is None:
            # Work in a task: a run takes a while, and the pipeline has to keep
            # carrying the conversation meanwhile (and survive an interruption).
            self.create_task(self._work(frame), f"{self.title}::run")
            return

        await self.push_frame(frame, direction)

    async def _work(self, frame: BlueprintRunFrame) -> None:
        await self.execute(frame.run)
        await self.push_frame(frame)

    async def execute(self, run: BlueprintRun) -> None:
        """Run this agent's part and report its status, without handing the run on."""
        await self.status(run, "working")
        started = time.monotonic()
        self._tokens = 0
        try:
            note = await self.run(run)
            await self.status(
                run,
                "done",
                note=note,
                duration_ms=int((time.monotonic() - started) * 1000),
                tokens=self._tokens,
            )
        except Exception as e:
            logger.exception(f"{self.title} failed")
            run.error = f"{self.title}: {e}"
            await self.status(run, "error", note=str(e))
            await self.emit({"type": "run_error", "run_id": run.run_id, "error": run.error})

    async def run(self, run: BlueprintRun) -> str:
        """Do this agent's work. Return a one-line note for the UI."""
        raise NotImplementedError


class ParallelAgents(FrameProcessor):
    """Runs agents that do not depend on each other at the same time on one run,
    then hands the run on once all of them are done."""

    def __init__(self, agents: list[AgentProcessor], **kwargs):
        super().__init__(name=" + ".join(a.title for a in agents), **kwargs)
        self.agents = agents
        for agent in agents:
            agent._sink = self

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, BlueprintRunFrame) and frame.run.error is None:
            self.create_task(self._work(frame), f"{self.name}::run")
            return

        await self.push_frame(frame, direction)

    async def _work(self, frame: BlueprintRunFrame) -> None:
        await asyncio.gather(*(agent.execute(frame.run) for agent in self.agents))
        await self.push_frame(frame)
