import re

from blueprint.agents.base import AgentProcessor
from blueprint.domain_classifier import classify_domain
from blueprint.models import BlueprintRun, Screen, UXFlow
from blueprint.references import CATEGORY_RECIPES, categories_prompt, category_screens

SYSTEM = """You are a UX architect. Design the page flow for the website below.
Return exactly one page for EACH of these page categories, all of them:
{categories}
Leave out everything else (sign in, payment, dashboards, …): those pages are not
part of this flow.
Return the pages in the order a visitor meets them. For each page give a short
kebab-case id, a name that fits the product (e.g. "Rooms & suites" for a hotel's
services page), its purpose, the persona who uses it, the ids of the pages it links
to, its category, and an ordered list of 3 to 7 wireframe blocks taken ONLY from:
header, title, text, input, button, image, cards, list, map."""


def keep_categorised(
    screens: list[Screen], domain: str
) -> tuple[list[Screen], list[str], list[str]]:
    """One screen per category, in category order: the model's where it gave one, the
    default otherwise. Returns (screens, names dropped, names added)."""
    by_cat: dict[str, Screen] = {}
    dropped: list[str] = []
    for s in screens:
        if s.category is None or s.category in by_cat:
            dropped.append(s.name)
        else:
            by_cat[s.category] = s
    added: list[str] = []
    for default in category_screens(domain):
        if default.category not in by_cat:
            by_cat[default.category] = default
            added.append(default.name)
    return [by_cat[c] for c in CATEGORY_RECIPES], dropped, added


class UXArchitect(AgentProcessor):
    agent_id = "ux"
    title = "UX Architect"
    service = "Azure OpenAI · page categories"

    async def run(self, run: BlueprintRun) -> str:
        # Runs alongside the Requirements Analyst, so it works from the raw requirement
        # and the domain, not from the analyst's spec.
        domain = (run.domain or classify_domain(run.request.requirement)).domain
        if self.llm.mock:
            await self.mock_pause()
            flow = UXFlow(screens=category_screens(domain))
        else:
            user = (
                f"Domain: {domain}\nPlatform: {run.request.platform}\n"
                f"Requirement:\n{run.request.requirement}"
            )
            flow, tokens = await self.llm.structured(
                SYSTEM.format(categories=categories_prompt()), user, UXFlow
            )
            self.count_tokens(run, tokens)
            for s in flow.screens:  # keep ids safe for Miro/Figma names and the client
                s.id = re.sub(r"[^a-z0-9-]", "-", s.id.lower()).strip("-") or "screen"
            flow.screens, dropped, added = keep_categorised(flow.screens, domain)
            if dropped:
                await self.log(run, f"Left out (no page category): {', '.join(dropped)}")
            if added:
                await self.log(run, f"Added missing pages: {', '.join(added)}")
        run.flow = flow
        names = " → ".join(s.name for s in flow.screens)
        await self.log(run, f"Flow: {names}")
        await self.log(run, "Hand-off → Wireframe Builder and Estimator")
        return f"{len(flow.screens)}-page flow"
