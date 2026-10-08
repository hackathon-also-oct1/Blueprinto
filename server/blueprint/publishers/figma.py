"""Prepare a layout for Figma.

Figma's REST API cannot create design nodes, so publishing to Figma goes
through the plugin in ``figma-plugin/``. This module builds the JSON that the
plugin imports, saves it next to the run, and returns it to the client, which
offers a "Copy for Figma" button. Paste it into the plugin to build the frames.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from blueprint.models import BlueprintRun, PublishResult


def figma_payload(run: BlueprintRun) -> dict:
    assert run.layout is not None
    est = run.estimate
    return {
        "version": 1,
        "run_id": run.run_id,
        "title": run.spec.summary if run.spec else run.run_id,
        "device": run.layout.device,
        "frames": [f.model_dump(mode="json") for f in run.layout.frames],
        "links": run.layout.links,
        "notes": (
            [
                f"Budget: {est.currency} {est.total:,.0f} ({est.low:,.0f}–{est.high:,.0f})",
                f"Timeline: {est.weeks} weeks",
                f"Team: {est.people} people ({est.fte:.1f} FTE)",
                *[f"Risk: {r}" for r in est.risks],
            ]
            if est
            else []
        ),
    }


async def publish_to_figma(run: BlueprintRun) -> tuple[PublishResult, dict]:
    payload = figma_payload(run)
    runs_dir = Path(os.getenv("RUNS_DIR", Path(__file__).resolve().parents[2] / "runs"))
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run.run_id}.figma.json"
    path.write_text(json.dumps(payload, indent=2))
    return (
        PublishResult(
            target="figma",
            status="prepared",
            detail="Layout ready. Copy it and paste into the Blueprint Importer plugin in Figma.",
            items_created=len(payload["frames"]),
        ),
        payload,
    )
