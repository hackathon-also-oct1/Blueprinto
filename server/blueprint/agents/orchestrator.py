"""Orchestrator: turns client messages into runs and starts the agent chain.

Client → server messages (sent with ``client.sendClientMessage(type, data)``):

* ``run_blueprint``  data = RunRequest fields

The voice agent starts a run the same way, with a ``StartBlueprintFrame``.
"""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIClientMessageFrame, RTVIServerMessageFrame
from pydantic import ValidationError

from blueprint.frames import BlueprintRunFrame, StartBlueprintFrame
from blueprint.models import BlueprintRun, RunRequest


class Orchestrator(FrameProcessor):
    agent_id = "orch"
    title = "Orchestrator"
    service = "Pipecat pipeline · Azure Container Apps"

    def __init__(self, agents: list[dict], mock: bool, **kwargs):
        super().__init__(name=self.title, **kwargs)
        self._agents = agents
        self._mock = mock

    async def _emit(self, data: dict) -> None:
        await self.push_frame(RTVIServerMessageFrame(data=data))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, RTVIClientMessageFrame):
            await self._handle_client_message(frame)
            return  # consumed

        if isinstance(frame, StartBlueprintFrame):
            await self._start_run(frame.request)
            return  # consumed

        await self.push_frame(frame, direction)

    async def _start_run(self, request: RunRequest) -> None:
        run = BlueprintRun(request=request)
        logger.info(f"Starting {run.run_id}")
        await self._emit(
            {
                "type": "run_started",
                "run_id": run.run_id,
                "mock": self._mock,
                "agents": self._agents,
                # Lets the client show a requirement that was spoken, not typed.
                "requirement": request.requirement,
            }
        )
        await self._emit(
            {
                "type": "agent_status",
                "run_id": run.run_id,
                "agent": self.agent_id,
                "status": "working",
                "note": f"Planning {len(self._agents) - 1} hand-offs",
            }
        )
        words = len(request.requirement.split())
        await self._emit(
            {
                "type": "agent_log",
                "run_id": run.run_id,
                "agent": self.agent_id,
                "message": f"Received requirement ({words} words). Hand-off → Requirements Analyst",
            }
        )
        await self.push_frame(BlueprintRunFrame(run=run))

    async def _handle_client_message(self, frame: RTVIClientMessageFrame) -> None:
        data = frame.data or {}
        if frame.type == "run_blueprint":
            try:
                request = RunRequest.model_validate(data)
            except ValidationError as e:
                await self._emit({"type": "run_error", "run_id": None, "error": str(e)})
                return
            await self._start_run(request)

        else:
            logger.debug(f"Ignoring client message type {frame.type!r}")
