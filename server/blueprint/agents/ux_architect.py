import re

from blueprint.agents.base import AgentProcessor
from blueprint.catalog import catalog_prompt, heuristic_screens
from blueprint.models import BlueprintRun, UXFlow

SYSTEM = """You are a UX architect. Design the screen flow for the product below.
Return 4 to 12 screens in the order a user meets them. For each screen give a short
kebab-case id, a name, its purpose, the persona who uses it, the ids of the screens it
links to, and an ordered list of wireframe blocks taken ONLY from:
header, title, text, input, button, image, cards, list, calendar, slots, chart, table,
chat, map, avatar, tabbar, upload.
Use 3 to 7 blocks per screen. Prefer these proven patterns where they fit:
{catalog}"""


class UXArchitect(AgentProcessor):
    agent_id = "ux"
    title = "UX Architect"
    service = "Azure OpenAI · pattern library"

    async def run(self, run: BlueprintRun) -> str:
        assert run.spec is not None
        if self.llm.mock:
            await self.mock_pause()
            flow = UXFlow(screens=heuristic_screens(run.request.requirement))
        else:
            features = "\n".join(
                f"- [{f.priority}] {f.name}: {f.description}" for f in run.spec.features
            )
            user = (
                f"Summary: {run.spec.summary}\nPersonas: {', '.join(run.spec.personas)}\n"
                f"Platform: {run.request.platform}\nFeatures:\n{features}"
            )
            flow, tokens = await self.llm.structured(
                SYSTEM.format(catalog=catalog_prompt()), user, UXFlow
            )
            run.tokens += tokens
            for s in flow.screens:  # keep ids safe for Miro/Figma names and the client
                s.id = re.sub(r"[^a-z0-9-]", "-", s.id.lower()).strip("-") or "screen"
        run.flow = flow
        names = " → ".join(s.name for s in flow.screens)
        await self.log(run, f"Flow: {names}")
        await self.log(run, "Hand-off → Wireframe Builder and Estimator")
        return f"{len(flow.screens)}-screen flow"
