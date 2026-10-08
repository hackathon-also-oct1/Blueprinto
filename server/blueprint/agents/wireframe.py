"""Wireframe Builder: deterministic layout engine (no LLM needed).

Turns each screen's block list into absolutely positioned nodes inside a device
frame. The same layout JSON feeds the client preview, Miro and the Figma plugin.
"""

from blueprint.agents.base import AgentProcessor
from blueprint.models import BlueprintRun, Layout, LayoutFrame, LayoutNode

MOBILE = (390, 844)
DESKTOP = (1280, 800)
GAP_BETWEEN_FRAMES = 160
PAD = 20
SPACING = 14

# Default height of each block type on a mobile frame (px)
HEIGHTS = {
    "header": 56,
    "title": 28,
    "text": 18,
    "input": 48,
    "button": 52,
    "image": 180,
    "cards": 220,
    "list": 300,
    "calendar": 260,
    "slots": 120,
    "chart": 200,
    "table": 240,
    "chat": 460,
    "map": 380,
    "avatar": 96,
    "tabbar": 64,
    "upload": 160,
}


def build_layout(run: BlueprintRun) -> Layout:
    assert run.flow is not None
    device = "desktop" if run.request.platform == "web" else "mobile"
    fw, fh = DESKTOP if device == "desktop" else MOBILE
    frames: list[LayoutFrame] = []
    for i, screen in enumerate(run.flow.screens):
        nodes: list[LayoutNode] = []
        y = PAD
        for block in screen.blocks:
            h = HEIGHTS[block]
            if block == "header":
                nodes.append(LayoutNode(type=block, x=0, y=0, w=fw, h=h, label=screen.name))
                y = h + SPACING
                continue
            if block == "tabbar":
                nodes.append(LayoutNode(type=block, x=0, y=fh - h, w=fw, h=h))
                continue
            w = fw - 2 * PAD
            if block in ("avatar",):
                w = h
            if y + h > fh - PAD:  # shrink to fit rather than overflow the frame
                h = max(24, fh - PAD - y)
            nodes.append(
                LayoutNode(
                    type=block,
                    x=PAD if block != "avatar" else (fw - w) // 2,
                    y=y,
                    w=w,
                    h=h,
                    label=block,
                )
            )
            y += h + SPACING
        frames.append(
            LayoutFrame(
                screen_id=screen.id,
                name=screen.name,
                x=i * (fw + GAP_BETWEEN_FRAMES),
                y=0,
                w=fw,
                h=fh,
                nodes=nodes,
            )
        )
    ids = {s.id for s in run.flow.screens}
    links = [(s.id, t) for s in run.flow.screens for t in s.links_to if t in ids and t != s.id]
    if not links:
        links = [(a.id, b.id) for a, b in zip(run.flow.screens, run.flow.screens[1:], strict=False)]
    return Layout(device=device, frames=frames, links=links)


class WireframeBuilder(AgentProcessor):
    agent_id = "wf"
    title = "Wireframe Builder"
    service = "Layout engine · 390×844 / 1280×800 frames"

    async def run(self, run: BlueprintRun) -> str:
        await self.mock_pause()
        run.layout = build_layout(run)
        nodes = sum(len(f.nodes) for f in run.layout.frames)
        await self.log(
            run, f"Laid out {len(run.layout.frames)} {run.layout.device} frames, {nodes} blocks"
        )
        # Send the wireframes early so the UI can draw them while estimation runs.
        await self.emit(
            {
                "type": "wireframes",
                "run_id": run.run_id,
                "flow": run.flow.model_dump(mode="json") if run.flow else None,
                "layout": run.layout.model_dump(mode="json"),
            }
        )
        return f"{nodes} blocks laid out"
