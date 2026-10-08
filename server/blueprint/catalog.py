"""Screen pattern catalog.

Used two ways:
* as grounding for the UX Architect prompt (allowed patterns and blocks), and
* as the deterministic fallback when no Azure OpenAI keys are configured.
"""

from __future__ import annotations

import re

from blueprint.models import Complexity, Feature, RequirementSpec, Screen

PATTERNS: dict[str, dict] = {
    "login": {
        "name": "Sign in",
        "kw": ["sign in", "login", "log in", "sign up", "register", "account"],
        "blocks": ["image", "input", "input", "button", "text"],
        "complexity": "M",
    },
    "home": {
        "name": "Home",
        "always": True,
        "blocks": ["header", "image", "cards", "tabbar"],
        "complexity": "M",
    },
    "browse": {
        "name": "Browse",
        "kw": ["browse", "catalog", "search", "find", "directory", "list of"],
        "blocks": ["header", "input", "list", "tabbar"],
        "complexity": "M",
    },
    "detail": {
        "name": "Detail",
        "kw": ["therapist", "product", "listing", "detail"],
        "blocks": ["header", "image", "title", "text", "button"],
        "complexity": "S",
    },
    "booking": {
        "name": "Book",
        "kw": ["book", "appointment", "schedule", "reservation", "calendar"],
        "blocks": ["header", "calendar", "slots", "button"],
        "complexity": "L",
    },
    "payment": {
        "name": "Pay",
        "kw": ["pay", "payment", "checkout", "billing", "subscription", "invoice"],
        "blocks": ["header", "title", "text", "input", "input", "button"],
        "complexity": "L",
    },
    "notify": {
        "name": "Reminders",
        "kw": ["reminder", "notification", "alert", "sms", "push"],
        "blocks": ["header", "list"],
        "complexity": "S",
    },
    "chat": {
        "name": "Chat",
        "kw": ["chat", "message", "messaging", "support"],
        "blocks": ["header", "chat", "input"],
        "complexity": "L",
    },
    "map": {
        "name": "Map",
        "kw": ["map", "location", "nearby", "delivery", "track"],
        "blocks": ["header", "map", "list"],
        "complexity": "M",
    },
    "upload": {
        "name": "Documents",
        "kw": ["upload", "document", "file", "photo"],
        "blocks": ["header", "upload", "list"],
        "complexity": "M",
    },
    "profile": {
        "name": "Profile",
        "kw": ["profile", "settings", "preferences"],
        "blocks": ["header", "avatar", "input", "input", "button"],
        "complexity": "S",
    },
    "dashboard": {
        "name": "Admin dashboard",
        "kw": ["dashboard", "admin", "analytics", "overview", "kpi"],
        "blocks": ["header", "cards", "chart", "table"],
        "complexity": "L",
    },
    "reports": {
        "name": "Reports",
        "kw": ["report", "revenue", "utilization", "utilisation", "export"],
        "blocks": ["header", "input", "chart", "table"],
        "complexity": "L",
    },
}

# Person-days per screen by complexity: (frontend, backend)
EFFORT: dict[Complexity, tuple[float, float]] = {"S": (2.5, 2.0), "M": (4.0, 3.5), "L": (6.0, 6.5)}

PERSONA_WORDS = ["patient", "customer", "user", "client", "guest", "member", "student"]
ADMIN_WORDS = ["admin", "staff", "manager", "operator", "clinic"]


def match_patterns(text: str) -> list[str]:
    t = text.lower()
    keys = [k for k, p in PATTERNS.items() if p.get("always") or any(w in t for w in p["kw"])]
    if "browse" in keys and "detail" not in keys:
        keys.append("detail")
    if "login" not in keys and re.search(r"admin|patient|user|customer|member", t):
        keys.append("login")
    order = list(PATTERNS)
    return sorted(set(keys), key=order.index)


def heuristic_spec(text: str) -> RequirementSpec:
    t = text.lower()
    personas = [w for w in PERSONA_WORDS if w in t][:2] or ["end user"]
    if any(w in t for w in ADMIN_WORDS if w != "clinic"):
        personas.append("admin")
    features = [
        Feature(name=PATTERNS[k]["name"], description=f"{PATTERNS[k]['name']} capability")
        for k in match_patterns(text)
    ]
    first = text.strip().split(".")[0]
    return RequirementSpec(
        summary=first[:200],
        personas=personas,
        features=features,
        non_functional=["GDPR compliant data handling", "WCAG 2.2 AA accessibility"],
    )


def heuristic_screens(text: str) -> list[Screen]:
    keys = match_patterns(text)
    screens = [
        Screen(
            id=k,
            name=PATTERNS[k]["name"],
            purpose=f"{PATTERNS[k]['name']} screen",
            persona="admin" if k in ("dashboard", "reports") else "",
            blocks=PATTERNS[k]["blocks"],
        )
        for k in keys
    ]
    for a, b in zip(screens, screens[1:], strict=False):
        a.links_to = [b.id]
    return screens


def catalog_prompt() -> str:
    lines = [f"- {k}: {p['name']} (blocks: {', '.join(p['blocks'])})" for k, p in PATTERNS.items()]
    return "\n".join(lines)
