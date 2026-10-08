"""Data models shared by the agents.

A single ``BlueprintRun`` travels through the Pipecat pipeline inside a
``BlueprintRunFrame``. Each agent fills in its own section, so the run is also
the complete record of a run (it is what gets stored and sent to the client).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["web", "mobile", "both"]
PublishTarget = Literal["miro", "figma"]
Complexity = Literal["S", "M", "L"]

# Wireframe building blocks the UX Architect may use. The Wireframe Builder and
# the client both know how to draw each one.
BlockType = Literal[
    "header",
    "title",
    "text",
    "input",
    "button",
    "image",
    "cards",
    "list",
    "calendar",
    "slots",
    "chart",
    "table",
    "chat",
    "map",
    "avatar",
    "tabbar",
    "upload",
]


# Page categories that have a reference screenshot (see blueprint/references.py).
PageCategory = Literal["home", "about", "services", "service_detail", "contact", "error_404"]


class RoleRate(BaseModel):
    id: str
    name: str
    day_rate: float


DEFAULT_RATES: list[RoleRate] = [
    RoleRate(id="pm", name="Product manager", day_rate=650),
    RoleRate(id="ux", name="UX/UI designer", day_rate=600),
    RoleRate(id="fe", name="Frontend engineer (TypeScript)", day_rate=560),
    RoleRate(id="be", name="Backend engineer (Azure)", day_rate=580),
    RoleRate(id="qa", name="QA engineer", day_rate=450),
    RoleRate(id="ops", name="DevOps engineer", day_rate=620),
]


class RunRequest(BaseModel):
    """What the client sends with the ``run_blueprint`` message."""

    requirement: str = Field(min_length=10, max_length=8000)
    platform: Platform = "both"
    target: PublishTarget = "miro"
    currency: str = "EUR"
    contingency_pct: float = 15
    rates: list[RoleRate] = Field(default_factory=lambda: [r.model_copy() for r in DEFAULT_RATES])


# ---- Domain Classifier ----------------------------------------------------


class DomainMatch(BaseModel):
    """Which reference domain (screenshots/<domain>/) a requirement belongs to."""

    domain: str
    name: str
    reference_set: str
    score: int
    confidence: float
    matched: list[str] = Field(default_factory=list)
    fallback: bool = False  # True when no rule scored high enough


# ---- Requirements Analyst -------------------------------------------------


class Feature(BaseModel):
    name: str
    description: str
    priority: Literal["must", "should", "could"] = "must"


class RequirementSpec(BaseModel):
    summary: str
    personas: list[str]
    features: list[Feature]
    non_functional: list[str] = Field(default_factory=list)


# ---- UX Architect ---------------------------------------------------------


class Screen(BaseModel):
    id: str
    name: str
    purpose: str
    persona: str = ""
    blocks: list[BlockType]
    links_to: list[str] = Field(default_factory=list)
    category: PageCategory | None = None


class UXFlow(BaseModel):
    screens: list[Screen]


class PagePlan(BaseModel):
    """What the UX Architect's model decides per page; the rest comes from the
    category recipe (blueprint/references.py)."""

    # A plain string so an unknown category is dropped, not a validation retry.
    category: str
    name: str
    purpose: str
    persona: str = ""


class SitePlan(BaseModel):
    pages: list[PagePlan]


# ---- Wireframe Builder ----------------------------------------------------


class LayoutNode(BaseModel):
    type: BlockType
    x: int
    y: int
    w: int
    h: int
    label: str = ""


class LayoutFrame(BaseModel):
    screen_id: str
    name: str
    x: int
    y: int
    w: int
    h: int
    nodes: list[LayoutNode]
    category: PageCategory | None = None
    # Reference screenshot path inside screenshots/ ("<domain>/<file>"), shown instead of the blocks.
    screenshot: str | None = None


class Layout(BaseModel):
    device: Literal["mobile", "desktop"]
    frames: list[LayoutFrame]
    links: list[tuple[str, str]]
    reference_set: str | None = None
    reference_name: str = ""
    reference_domain: str = ""


# ---- Estimator ------------------------------------------------------------


class ScreenEstimate(BaseModel):
    screen_id: str
    complexity: Complexity
    fe_days: float
    be_days: float


class RoleLine(BaseModel):
    role_id: str
    name: str
    headcount: float
    days: float
    day_rate: float
    cost: float


class Phase(BaseModel):
    name: str
    start_week: float
    weeks: float


class Estimate(BaseModel):
    currency: str
    screens: list[ScreenEstimate]
    lines: list[RoleLine]
    subtotal: float
    contingency_pct: float
    total: float
    low: float
    high: float
    weeks: int
    people: int
    fte: float
    phases: list[Phase]
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


# ---- Publisher ------------------------------------------------------------


class PublishResult(BaseModel):
    target: PublishTarget
    status: Literal["prepared", "published", "dry_run", "failed"]
    url: str | None = None
    detail: str = ""
    items_created: int = 0


# ---- The run --------------------------------------------------------------


class BlueprintRun(BaseModel):
    run_id: str = Field(default_factory=lambda: "run-" + uuid.uuid4().hex[:8])
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    request: RunRequest
    domain: DomainMatch | None = None
    spec: RequirementSpec | None = None
    flow: UXFlow | None = None
    layout: Layout | None = None
    estimate: Estimate | None = None
    publish: PublishResult | None = None
    error: str | None = None
    tokens: int = 0
