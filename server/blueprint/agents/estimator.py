"""Estimator: budget, timeline and team.

The LLM only judges what it is good at (how complex each screen is, and the
main delivery risks). The numbers come from a deterministic model so the same
inputs always give the same budget, and the client can recompute costs live
when someone edits a day rate.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from blueprint.agents.base import AgentProcessor
from blueprint.catalog import EFFORT, PATTERNS
from blueprint.models import (
    BlueprintRun,
    Complexity,
    Estimate,
    Phase,
    RoleLine,
    ScreenEstimate,
)
from blueprint.references import CATEGORY_RECIPES

PLATFORM_FE_FACTOR = {"web": 1.0, "mobile": 1.2, "both": 1.8}
FE_BASELINE = 6  # design system, app shell, routing
BE_BASELINE = 8  # auth (Entra External ID), API layer, data model, CI/CD hooks


class ComplexityItem(BaseModel):
    screen_id: str
    complexity: Complexity
    reason: str = ""


class ComplexityReview(BaseModel):
    screens: list[ComplexityItem]
    risks: list[str]


SYSTEM = """You are a delivery lead estimating a software project. For each screen,
rate implementation complexity as S, M or L, considering integrations (payments,
messaging, calendars), real-time features and data volume. Then list the 3 to 5
biggest delivery risks in one short sentence each."""


def compute_estimate(
    run: BlueprintRun, complexity: dict[str, Complexity], risks: list[str]
) -> Estimate:
    assert run.flow is not None
    req = run.request
    factor = PLATFORM_FE_FACTOR[req.platform]

    screens: list[ScreenEstimate] = []
    for s in run.flow.screens:
        c = (
            complexity.get(s.id)
            or (CATEGORY_RECIPES[s.category]["complexity"] if s.category else None)
            or PATTERNS.get(s.id, {}).get("complexity", "M")
        )
        fe, be = EFFORT[c]
        screens.append(
            ScreenEstimate(screen_id=s.id, complexity=c, fe_days=round(fe * factor, 1), be_days=be)
        )

    fe_days = round(sum(s.fe_days for s in screens) + FE_BASELINE)
    be_days = round(sum(s.be_days for s in screens) + BE_BASELINE)
    ux_days = len(screens) * 2 + 5
    qa_days = round((fe_days + be_days) * 0.25)

    fe_n = min(4, max(1, math.ceil(fe_days / 45)))
    be_n = min(4, max(1, math.ceil(be_days / 45)))
    qa_n = 2 if fe_days + be_days > 140 else 1

    discovery = min(3, max(1, math.ceil(ux_days / 12)))
    build = max(2, math.ceil(max(fe_days / fe_n, be_days / be_n) / 5))
    harden = 2 if len(screens) > 8 else 1
    weeks = discovery + build + harden

    ops_days = 8 + weeks
    pm_days = round(weeks * 5 * 0.5)

    rates = {r.id: r for r in req.rates}
    plan = {
        "pm": (0.5, pm_days),
        "ux": (1, ux_days),
        "fe": (fe_n, fe_days),
        "be": (be_n, be_days),
        "qa": (qa_n, qa_days),
        "ops": (0.5, ops_days),
    }
    lines = []
    for role_id, (heads, days) in plan.items():
        rate = rates.get(role_id)
        day_rate = rate.day_rate if rate else 0
        lines.append(
            RoleLine(
                role_id=role_id,
                name=rate.name if rate else role_id,
                headcount=heads,
                days=days,
                day_rate=day_rate,
                cost=round(days * day_rate, 2),
            )
        )
    subtotal = sum(line.cost for line in lines)
    total = subtotal * (1 + req.contingency_pct / 100)
    return Estimate(
        currency=req.currency,
        screens=screens,
        lines=lines,
        subtotal=round(subtotal, 2),
        contingency_pct=req.contingency_pct,
        total=round(total, 2),
        low=round(total * 0.85, 2),
        high=round(total * 1.25, 2),
        weeks=weeks,
        people=2 + fe_n + be_n + qa_n,  # PM+DevOps shared seat, UX, devs, QA
        fte=0.5 + 1 + fe_n + be_n + qa_n + 0.5,
        phases=[
            Phase(name="Discovery & UX", start_week=0, weeks=discovery),
            Phase(name="Build sprints", start_week=discovery, weeks=build),
            Phase(name="QA & hardening", start_week=discovery + build - 1, weeks=harden + 1),
            Phase(name="Launch", start_week=weeks - 0.4, weeks=0.4),
        ],
        risks=risks,
        assumptions=[
            "Frontend includes a shared TypeScript design system and app shell.",
            "Backend includes auth (Microsoft Entra External ID), API layer and data model.",
            "Azure running costs and third-party licences are not included.",
            f"Platform factor for '{req.platform}' applied to frontend effort: x{factor}.",
        ],
    )


class Estimator(AgentProcessor):
    agent_id = "est"
    title = "Estimator"
    service = "Azure OpenAI · Cosmos DB history"

    async def run(self, run: BlueprintRun) -> str:
        assert run.flow is not None
        complexity: dict[str, Complexity] = {}
        risks: list[str] = []
        if self.llm.mock:
            await self.mock_pause()
            risks = [
                "Third-party integrations (payments, SMS) need early sandbox access.",
                "Scope growth in admin reporting.",
                "App store review time for the mobile release.",
            ]
        else:
            screens = "\n".join(
                f"- {s.id}: {s.name} — {s.purpose} (blocks: {', '.join(s.blocks)})"
                for s in run.flow.screens
            )
            user = f"Platform: {run.request.platform}\nScreens:\n{screens}"
            review, tokens = await self.llm.structured(SYSTEM, user, ComplexityReview)
            self.count_tokens(run, tokens)
            complexity = {i.screen_id: i.complexity for i in review.screens}
            risks = review.risks

        est = compute_estimate(run, complexity, risks)
        run.estimate = est
        await self.log(
            run,
            f"Estimate: {est.currency} {est.total:,.0f} · {est.weeks} weeks · {est.people} people",
        )
        await self.log(run, "Hand-off → Narrator")
        return f"{est.currency} {est.total:,.0f} · {est.weeks} wks"
