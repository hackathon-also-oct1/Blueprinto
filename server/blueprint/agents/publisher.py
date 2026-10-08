"""Publisher: prepares the board during a run and publishes on request.

Publishing is a separate, explicit step (the user presses Publish), because it
writes to an external workspace.
"""

from __future__ import annotations

import time

from loguru import logger
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection

from blueprint.agents.base import AgentProcessor
from blueprint.frames import PublishRequestFrame
from blueprint.models import BlueprintRun, PublishResult
from blueprint.publishers import publish_to_figma, publish_to_miro
from blueprint.storage import RunStore


class Publisher(AgentProcessor):
    agent_id = "pub"
    title = "Publisher"
    service = "Miro REST API · Figma plugin"

    def __init__(self, llm, store: RunStore, **kwargs):
        super().__init__(llm, **kwargs)
        self.store = store

    async def run(self, run: BlueprintRun) -> str:
        await self.mock_pause()
        target = run.request.target
        run.publish = PublishResult(target=target, status="prepared", detail="Waiting for approval")
        frames = len(run.layout.frames) if run.layout else 0
        await self.log(
            run,
            f"Prepared {frames} frames for {target.title()}. Press Publish to send them.",
        )
        return "Ready to publish"

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, PublishRequestFrame):
            await super(AgentProcessor, self).process_frame(frame, direction)
            await self._publish(frame)
            return  # consumed
        await super().process_frame(frame, direction)

    async def _publish(self, req: PublishRequestFrame) -> None:
        run = await self.store.get(req.run_id)
        if run is None or run.layout is None:
            await self.emit(
                {
                    "type": "publish_result",
                    "run_id": req.run_id,
                    "publish": {
                        "target": req.target,
                        "status": "failed",
                        "detail": "Run not found. Run the agents again.",
                    },
                }
            )
            return
        await self.status(run, "working", note=f"Publishing to {req.target.title()}")
        started = time.monotonic()
        extra: dict = {}
        try:
            if req.target == "miro":
                await self.log(run, "Creating frames, shapes, connectors and sticky notes…")
                result = await publish_to_miro(run)
            else:
                result, payload = await publish_to_figma(run)
                extra["figma_payload"] = payload
        except Exception as e:
            logger.exception("Publish failed")
            result = PublishResult(target=req.target, status="failed", detail=str(e))
        run.publish = result
        await self.store.save(run)
        await self.log(run, f"{req.target.title()}: {result.status} — {result.detail}")
        await self.status(
            run,
            "done" if result.status != "failed" else "error",
            note=result.status.replace("_", " ").capitalize(),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        await self.emit(
            {
                "type": "publish_result",
                "run_id": run.run_id,
                "publish": result.model_dump(mode="json"),
                **extra,
            }
        )
