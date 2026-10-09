"""End-to-end test of the agent chain in mock mode (no Azure keys needed).

uv run pytest -q
"""

import os

import pytest
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frameworks.rtvi import RTVIClientMessageFrame, RTVIServerMessageFrame
from pipecat.tests.utils import SleepFrame, run_test

os.environ["BLUEPRINT_MOCK"] = "1"

from blueprint.agents.estimator import compute_estimate  # noqa: E402
from blueprint.agents.ux_architect import apply_plan  # noqa: E402
from blueprint.azure_llm import AgentLLM  # noqa: E402
from blueprint.models import BlueprintRun, PagePlan, RunRequest, UXFlow  # noqa: E402
from blueprint.pipeline import build_agent_chain  # noqa: E402
from blueprint.references import category_screens  # noqa: E402
from blueprint.storage import RunStore  # noqa: E402

REQ = (
    "A booking app for a physiotherapy clinic. Patients sign in, browse therapists, book and "
    "pay for appointments, get SMS reminders, and chat with the clinic. Admins see a dashboard "
    "with revenue and utilization reports."
)


def messages(frames):
    return [f.data for f in frames if isinstance(f, RTVIServerMessageFrame)]


@pytest.mark.asyncio
async def test_full_run(tmp_path):
    os.environ["RUNS_DIR"] = str(tmp_path)
    store = RunStore()
    chain = Pipeline(build_agent_chain(AgentLLM(), store))

    down, _ = await run_test(
        chain,
        frames_to_send=[
            RTVIClientMessageFrame(
                msg_id="1", type="run_blueprint", data={"requirement": REQ}
            ),
            SleepFrame(sleep=8),
        ],
    )
    msgs = messages(down)
    types = [m["type"] for m in msgs]
    assert types[0] == "run_started"
    assert "wireframes" in types
    final = next(m for m in msgs if m["type"] == "run_result")
    result = final["run"]
    # The wireframes tab still shows budget, weeks and team; they are not part of the run.
    assert final["kpis"]["total"] > 0 and final["kpis"]["weeks"] > 0
    assert result["error"] is None
    screens = result["flow"]["screens"]
    # Only pages with a reference screenshot: one per page category.
    assert [s["category"] for s in screens] == [
        "home",
        "about",
        "services",
        "service_detail",
        "contact",
        "error_404",
    ]
    assert all(f["screenshot"] for f in result["layout"]["frames"])
    assert result["estimate"] is None  # the client states the budget; none is calculated
    # The Requirements Analyst and the UX Architect run at the same time.
    steps = [(m["agent"], m["status"]) for m in msgs if m["type"] == "agent_status"]
    started = max(steps.index(("req", "working")), steps.index(("ux", "working")))
    assert started < min(steps.index(("req", "done")), steps.index(("ux", "done")))
    done = {m["agent"] for m in msgs if m["type"] == "agent_status" and m["status"] == "done"}
    assert done == {"orch", "dom", "req", "ux", "wf"}


def test_estimate_scales_with_platform():
    flow = UXFlow(screens=category_screens("it-services"))
    web = BlueprintRun(request=RunRequest(requirement=REQ, platform="web"), flow=flow)
    both = BlueprintRun(request=RunRequest(requirement=REQ, platform="both"), flow=flow)
    e_web, e_both = compute_estimate(web, {}, []), compute_estimate(both, {}, [])
    assert e_both.total > e_web.total
    assert e_web.total == pytest.approx(e_web.subtotal * 1.15)


def test_flow_keeps_only_page_categories():
    plan = [
        PagePlan(category="login", name="Sign in", purpose=""),
        PagePlan(category="services", name="Rooms", purpose="All rooms", persona="guest"),
        PagePlan(category="home", name="Welcome", purpose="Hero"),
        PagePlan(category="services", name="Suites", purpose=""),
    ]
    screens, dropped, added = apply_plan(plan, "hospitality")
    # Every category once, in order: the model's names applied, the missing ones added.
    assert [s.category for s in screens] == [
        "home",
        "about",
        "services",
        "service_detail",
        "contact",
        "error_404",
    ]
    assert [s.name for s in screens][:3] == ["Welcome", "About us", "Rooms"]
    assert screens[2].persona == "guest" and screens[2].blocks  # blocks from the recipe
    assert dropped == ["Sign in", "Suites"]
    assert added == ["About us", "Room detail", "Contact", "Error 404"]
