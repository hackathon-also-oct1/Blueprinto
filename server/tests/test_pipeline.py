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
from blueprint.agents.ux_architect import keep_categorised  # noqa: E402
from blueprint.azure_llm import AgentLLM  # noqa: E402
from blueprint.models import BlueprintRun, RunRequest, Screen, UXFlow  # noqa: E402
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
async def test_full_run_and_publish(tmp_path):
    os.environ["RUNS_DIR"] = str(tmp_path)
    os.environ.pop("MIRO_ACCESS_TOKEN", None)
    store = RunStore()
    chain = Pipeline(build_agent_chain(AgentLLM(), store))

    down, _ = await run_test(
        chain,
        frames_to_send=[
            RTVIClientMessageFrame(
                msg_id="1", type="run_blueprint", data={"requirement": REQ, "target": "miro"}
            ),
            SleepFrame(sleep=8),
        ],
    )
    msgs = messages(down)
    types = [m["type"] for m in msgs]
    assert types[0] == "run_started"
    assert "wireframes" in types
    result = next(m for m in msgs if m["type"] == "run_result")["run"]
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
    assert result["estimate"]["total"] > 0
    done = {m["agent"] for m in msgs if m["type"] == "agent_status" and m["status"] == "done"}
    assert done == {"orch", "dom", "req", "ux", "wf", "est", "pub"}

    run_id = result["run_id"]
    for target, expected in (("miro", "dry_run"), ("figma", "prepared")):
        down, _ = await run_test(
            Pipeline(build_agent_chain(AgentLLM(), store)),
            frames_to_send=[
                RTVIClientMessageFrame(
                    msg_id="2", type="publish", data={"run_id": run_id, "target": target}
                ),
                SleepFrame(sleep=0.5),
            ],
        )
        pub = next(m for m in messages(down) if m["type"] == "publish_result")
        assert pub["publish"]["status"] == expected
        if target == "figma":
            assert len(pub["figma_payload"]["frames"]) == len(result["flow"]["screens"])


def test_estimate_scales_with_platform():
    flow = UXFlow(screens=category_screens("it-services"))
    web = BlueprintRun(request=RunRequest(requirement=REQ, platform="web"), flow=flow)
    both = BlueprintRun(request=RunRequest(requirement=REQ, platform="both"), flow=flow)
    e_web, e_both = compute_estimate(web, {}, []), compute_estimate(both, {}, [])
    assert e_both.total > e_web.total
    assert e_web.total == pytest.approx(e_web.subtotal * 1.15)


def test_flow_keeps_only_page_categories():
    llm_screens = [
        Screen(id="sign-in", name="Sign in", purpose="", blocks=["input"]),
        Screen(id="rooms", name="Rooms", purpose="", blocks=["cards"], category="services"),
        Screen(id="home", name="Home", purpose="", blocks=["image"], category="home"),
        Screen(id="suites", name="Suites", purpose="", blocks=["cards"], category="services"),
    ]
    screens, dropped, added = keep_categorised(llm_screens, "hospitality")
    # Every category once, in order: the model's pages kept, the missing ones added.
    assert [s.id for s in screens] == [
        "home",
        "about",
        "rooms",
        "service-detail",
        "contact",
        "error-404",
    ]
    assert dropped == ["Sign in", "Suites"]
    assert added == ["About us", "Room detail", "Contact", "Error 404"]
