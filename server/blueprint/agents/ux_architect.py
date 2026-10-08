from blueprint.agents.base import AgentProcessor
from blueprint.domain_classifier import classify_domain
from blueprint.models import BlueprintRun, PagePlan, Screen, SitePlan, UXFlow
from blueprint.references import categories_prompt, category_screens

SYSTEM = """You are a UX architect. Plan the pages of the website below.
Return exactly one page for EACH of these page categories, all of them:
{categories}
Leave out everything else (sign in, payment, dashboards, …).
For each page give its category, a name that fits the product (e.g. "Rooms & suites"
for a hotel's services page), its purpose in at most 12 words, and the persona who
uses it as a role name only (e.g. "prospective client").
Output compact JSON on one line, without indentation."""


def apply_plan(pages: list[PagePlan], domain: str) -> tuple[list[Screen], list[str], list[str]]:
    """Put the model's names, purposes and personas onto the default category flow
    (ids, blocks and links come from the category recipes). One page per category:
    an unknown or repeated category is dropped, a missing one keeps its default.
    Returns (screens, names dropped, names added)."""
    screens = category_screens(domain)
    by_cat = {s.category: s for s in screens}
    planned: set[str] = set()
    dropped: list[str] = []
    for page in pages:
        if page.category not in by_cat or page.category in planned:
            dropped.append(page.name)
            continue
        planned.add(page.category)
        screen = by_cat[page.category]
        screen.name, screen.purpose, screen.persona = page.name, page.purpose, page.persona
    added = [s.name for s in screens if s.category not in planned]
    return screens, dropped, added


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
            # The model only names the pages; short output and low effort keep this
            # quick (measured ~11 s -> ~4 s on gpt-6-astra).
            plan, tokens = await self.llm.structured(
                SYSTEM.format(categories=categories_prompt()),
                user,
                SitePlan,
                reasoning_effort="low",
            )
            self.count_tokens(run, tokens)
            screens, dropped, added = apply_plan(plan.pages, domain)
            flow = UXFlow(screens=screens)
            if dropped:
                await self.log(
                    run, f"Left out (unknown or repeated category): {', '.join(dropped)}"
                )
            if added:
                await self.log(run, f"Added missing pages: {', '.join(added)}")
        run.flow = flow
        names = " → ".join(s.name for s in flow.screens)
        await self.log(run, f"Flow: {names}")
        await self.log(run, "Hand-off → Wireframe Builder and Estimator")
        return f"{len(flow.screens)}-page flow"
