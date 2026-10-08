"""Publish a layout to a Miro board through the Miro REST API v2.

Creates (on ``MIRO_BOARD_ID``, or a new board if unset):
* one frame per screen,
* one shape per wireframe block inside each frame,
* connectors between frames for the user flow,
* sticky notes with budget, timeline, team and risks.

Needs ``MIRO_ACCESS_TOKEN`` with the ``boards:write`` scope. Without a token the
publisher returns a dry run (the payloads it would send) so the demo still works.

Note: Miro positions are item *centres*. For items with a parent frame we send
coordinates relative to the frame's top-left corner; verify on your board and
adjust ``CHILD_RELATIVE`` if your tenant behaves differently.
"""

from __future__ import annotations

import os

import httpx
from loguru import logger

from blueprint.models import BlueprintRun, PublishResult

API = "https://api.miro.com/v2"
CHILD_RELATIVE = True

LABELS = {
    "header": "",
    "title": "Title",
    "text": "Text",
    "input": "Input",
    "button": "Button",
    "image": "Image",
    "cards": "Cards",
    "list": "List",
    "calendar": "Calendar",
    "slots": "Time slots",
    "chart": "Chart",
    "table": "Table",
    "chat": "Messages",
    "map": "Map",
    "avatar": "Avatar",
    "tabbar": "Tab bar",
    "upload": "Upload",
}


def _sticky_texts(run: BlueprintRun) -> list[str]:
    est = run.estimate
    if est is None:
        return []
    notes = [
        f"<p><strong>Budget</strong></p><p>{est.currency} {est.total:,.0f}"
        f" ({est.low:,.0f}–{est.high:,.0f})</p>",
        f"<p><strong>Timeline</strong></p><p>{est.weeks} weeks</p>",
        f"<p><strong>Team</strong></p><p>{est.people} people · {est.fte:.1f} FTE</p>",
    ]
    if est.risks:
        notes.append("<p><strong>Risks</strong></p>" + "".join(f"<p>• {r}</p>" for r in est.risks))
    return notes


async def publish_to_miro(run: BlueprintRun) -> PublishResult:
    assert run.layout is not None
    token = os.getenv("MIRO_ACCESS_TOKEN")
    board_id = os.getenv("MIRO_BOARD_ID")
    n_items = len(run.layout.frames) + sum(len(f.nodes) for f in run.layout.frames)

    if not token:
        return PublishResult(
            target="miro",
            status="dry_run",
            detail=f"No MIRO_ACCESS_TOKEN set. Would create {n_items} items on "
            f"{'board ' + board_id if board_id else 'a new board'}.",
            items_created=0,
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    created = 0
    async with httpx.AsyncClient(base_url=API, headers=headers, timeout=30) as http:
        if not board_id:
            r = await http.post("/boards", json={"name": f"Blueprint {run.run_id}"})
            r.raise_for_status()
            board_id = r.json()["id"]

        frame_ids: dict[str, str] = {}
        for f in run.layout.frames:
            r = await http.post(
                f"/boards/{board_id}/frames",
                json={
                    "data": {"title": f.name, "format": "custom", "type": "freeform"},
                    "position": {"x": f.x + f.w / 2, "y": f.y + f.h / 2},
                    "geometry": {"width": f.w, "height": f.h},
                },
            )
            r.raise_for_status()
            frame_ids[f.screen_id] = r.json()["id"]
            created += 1

            for n in f.nodes:
                cx, cy = n.x + n.w / 2, n.y + n.h / 2
                if not CHILD_RELATIVE:
                    cx, cy = cx + f.x, cy + f.y
                body = {
                    "data": {
                        "shape": "round_rectangle"
                        if n.type in ("button", "input")
                        else "rectangle",
                        "content": f.name if n.type == "header" else LABELS.get(n.type, n.type),
                    },
                    "style": {"borderColor": "#9aa1b1", "fontSize": "14"},
                    "position": {"x": cx, "y": cy},
                    "geometry": {"width": n.w, "height": n.h},
                    "parent": {"id": frame_ids[f.screen_id]},
                }
                r = await http.post(f"/boards/{board_id}/shapes", json=body)
                if r.status_code >= 400:
                    logger.warning(f"Miro shape failed ({r.status_code}): {r.text[:200]}")
                    continue
                created += 1

        for a, b in run.layout.links:
            if a in frame_ids and b in frame_ids:
                r = await http.post(
                    f"/boards/{board_id}/connectors",
                    json={"startItem": {"id": frame_ids[a]}, "endItem": {"id": frame_ids[b]}},
                )
                if r.status_code < 400:
                    created += 1

        top = max((f.h for f in run.layout.frames), default=800) + 200
        for i, text in enumerate(_sticky_texts(run)):
            r = await http.post(
                f"/boards/{board_id}/sticky_notes",
                json={
                    "data": {"content": text, "shape": "rectangle"},
                    "style": {"fillColor": "light_yellow"},
                    "position": {"x": 200 + i * 360, "y": top},
                },
            )
            if r.status_code < 400:
                created += 1

    return PublishResult(
        target="miro",
        status="published",
        url=f"https://miro.com/app/board/{board_id}/",
        detail=f"Created {created} items",
        items_created=created,
    )
