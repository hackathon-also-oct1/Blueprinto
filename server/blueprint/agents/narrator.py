"""Narrator: closes the run.

Saves the run and sends the full result to the client. With the voice agent in
the pipeline it hands the result to that agent, which reports it and can answer
questions about it; otherwise, when there is a TTS service, it speaks a fixed
summary. Either way the video avatar (Anam) lip-syncs what is said.
"""

from __future__ import annotations

from pipecat.frames.frames import Frame, LLMMessagesAppendFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from blueprint.agents.estimator import compute_estimate
from blueprint.frames import BlueprintRunFrame
from blueprint.models import BlueprintRun
from blueprint.storage import RunStore


def spoken_summary(run: BlueprintRun) -> str:
    est = run.estimate
    screens = len(run.flow.screens) if run.flow else 0
    if est is None:
        return "The blueprint is ready."
    thousands = round(est.total / 1000)
    return (
        f"Your blueprint is ready. I designed {screens} screens. "
        f"Building it should take about {est.weeks} weeks with a team of {est.people}, "
        f"for roughly {thousands} thousand {'euros' if est.currency == 'EUR' else est.currency}. "
    )


def result_brief(run: BlueprintRun) -> str:
    """What the voice agent is told when a run ends, so it can report and answer questions."""
    if run.error is not None:
        return f"The blueprint run failed: {run.error}. Tell the user briefly and offer to retry."
    facts = []
    if run.spec:
        facts.append(f"Summary: {run.spec.summary}")
        facts.append("Features: " + ", ".join(f.name for f in run.spec.features))
    if run.flow:
        facts.append(
            f"{len(run.flow.screens)} screens: " + ", ".join(s.name for s in run.flow.screens)
        )
    if est := run.estimate:
        facts.append(
            f"Estimate: {est.currency} {est.total:,.0f} (range {est.low:,.0f} to {est.high:,.0f}), "
            f"{est.weeks} weeks, {est.people} people"
        )
        if est.risks:
            facts.append("Risks: " + "; ".join(est.risks))
    return (
        "The blueprint run finished and the results are on screen.\n"
        + "\n".join(facts)
        + "\nTell the user it is ready in one or two short sentences, with the number of pages."
    )


class Narrator(FrameProcessor):
    def __init__(self, store: RunStore, speak: bool, converse: bool = False, **kwargs):
        super().__init__(name="Narrator", **kwargs)
        self.store = store
        self.speak = speak
        self.converse = converse

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, BlueprintRunFrame):
            run = frame.run
            await self.store.save(run)
            if run.error is None:
                await self.push_frame(
                    RTVIServerMessageFrame(
                        data={
                            "type": "agent_status",
                            "run_id": run.run_id,
                            "agent": "orch",
                            "status": "done",
                            "note": f"Run complete · {run.tokens:,} tokens",
                        }
                    )
                )
            # Figures for the wireframes tab only. run.estimate stays empty, so the
            # budget is not spoken and not part of the run.
            kpis = compute_estimate(run, {}, []) if run.flow and run.error is None else None
            await self.push_frame(
                RTVIServerMessageFrame(
                    data={
                        "type": "run_result",
                        "run": run.model_dump(mode="json"),
                        "kpis": kpis.model_dump(mode="json") if kpis else None,
                    }
                )
            )
            if self.converse:
                # The voice agent sits upstream: hand it the result and let it speak.
                await self.push_frame(
                    LLMMessagesAppendFrame(
                        messages=[{"role": "developer", "content": result_brief(run)}],
                        run_llm=True,
                    ),
                    FrameDirection.UPSTREAM,
                )
            elif self.speak and run.error is None:
                await self.push_frame(TTSSpeakFrame(spoken_summary(run), append_to_context=False))
            return  # the run frame stops here

        await self.push_frame(frame, direction)
