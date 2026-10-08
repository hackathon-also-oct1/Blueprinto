"""Reference screenshots used in place of the drawn block wireframes.

``screenshots/`` (repo root) holds five reference websites grouped by business
domain, one folder per domain (``finance/``, ``ecommerce/``, ``hospitality/``,
``it-services/``). Each site is captured for the same six page categories, named
``"<domain>/<set> -- <Category>.png"``. The Domain Classifier picks the domain and
set for a run (see blueprint/domain_classifier.py), so the whole flow shares one
look; the Wireframe Builder gives every screen the screenshot of its category.
Screens that fit no category keep the block wireframe.
"""

from __future__ import annotations

import re

from blueprint.models import PageCategory, Screen

# Category -> the name used in the screenshot file
CATEGORY_FILES: dict[PageCategory, str] = {
    "home": "HomePage",
    "about": "About_Us",
    "services": "Services_Index",
    "service_detail": "Services_Details",
    "contact": "Contact",
    "error_404": "Error_404",
}

CATEGORY_LABELS: dict[PageCategory, str] = {
    "home": "Home page",
    "about": "About us",
    "services": "Services / listing",
    "service_detail": "Service / item detail",
    "contact": "Contact",
    "error_404": "Error 404",
}

# Reference sets: one captured website each, stored in screenshots/<domain>/.
REFERENCE_SETS: dict[str, dict] = {
    "01": {"name": "Corporate finance", "domain": "finance"},
    "02": {"name": "Accounting & consulting", "domain": "finance"},
    "03": {"name": "Minimal e-commerce", "domain": "ecommerce"},
    "04": {"name": "Hospitality", "domain": "hospitality"},
    "05": {"name": "Tech / IT services", "domain": "it-services"},
}

# Keywords that place a screen in a category, checked in this order.
CATEGORY_KW: list[tuple[PageCategory, list[str]]] = [
    ("error_404", ["404", "not found", "error page"]),
    ("contact", ["contact", "support", "chat", "message", "location", "map", "get in touch"]),
    ("about", ["about", "team", "company", "our story", "history"]),
    ("service_detail", ["detail", "product page", "book", "appointment", "item"]),
    ("services", ["services", "browse", "catalog", "catalogue", "list", "search", "directory"]),
    ("home", ["home", "landing", "welcome"]),
]

# Fallback for screens built from the pattern catalog (catalog.PATTERNS keys).
PATTERN_CATEGORY: dict[str, PageCategory] = {
    "home": "home",
    "browse": "services",
    "detail": "service_detail",
    "booking": "service_detail",
    "chat": "contact",
    "map": "contact",
}


def _mentions(text: str, words: list[str]) -> bool:
    """True if any word appears at a word start (so "consult" matches "consulting")."""
    return any(re.search(rf"\b{re.escape(w)}", text) for w in words)


# What each category's screen holds. Flows only use these categories, so every
# screen has a reference screenshot; blocks still feed the estimate and Miro/Figma.
CATEGORY_RECIPES: dict[PageCategory, dict] = {
    "home": {
        "name": "Home",
        "purpose": "Hero with the main promise and call to action, then highlights",
        "blocks": ["header", "image", "title", "text", "button", "cards"],
        "complexity": "M",
    },
    "about": {
        "name": "About us",
        "purpose": "Company story, values and team",
        "blocks": ["header", "title", "text", "image", "cards"],
        "complexity": "S",
    },
    "services": {
        "name": "Services",
        "purpose": "Overview of every offering, each linking to its detail page",
        "blocks": ["header", "title", "text", "cards"],
        "complexity": "M",
    },
    "service_detail": {
        "name": "Service detail",
        "purpose": "One offering in depth with a call to action",
        "blocks": ["header", "image", "title", "text", "list", "button"],
        "complexity": "M",
    },
    "contact": {
        "name": "Contact",
        "purpose": "Contact channels and a message form",
        "blocks": ["header", "cards", "input", "input", "button", "map"],
        "complexity": "S",
    },
    "error_404": {
        "name": "Error 404",
        "purpose": "Page not found, with a way back home",
        "blocks": ["header", "title", "text", "button"],
        "complexity": "S",
    },
}

# Domain-specific names for the listing and detail pages.
DOMAIN_NAMES: dict[str, dict[PageCategory, str]] = {
    "ecommerce": {"services": "Shop", "service_detail": "Product detail"},
    "hospitality": {"services": "Rooms & suites", "service_detail": "Room detail"},
}


def category_screens(domain: str) -> list[Screen]:
    """The default flow: one screen per category, in the order a visitor meets them."""
    names = DOMAIN_NAMES.get(domain, {})
    screens = [
        Screen(
            id=category.replace("_", "-"),
            name=names.get(category, recipe["name"]),
            purpose=recipe["purpose"],
            blocks=recipe["blocks"],
            category=category,
        )
        for category, recipe in CATEGORY_RECIPES.items()
    ]
    by_cat = {s.category: s for s in screens}
    by_cat["home"].links_to = ["about", "services", "contact"]
    by_cat["services"].links_to = ["service-detail"]
    by_cat["service_detail"].links_to = ["contact"]
    by_cat["error_404"].links_to = ["home"]
    return screens


def screen_category(screen: Screen) -> PageCategory | None:
    if screen.category:
        return screen.category
    if screen.id in PATTERN_CATEGORY:
        return PATTERN_CATEGORY[screen.id]
    text = f"{screen.id.replace('-', ' ')} {screen.name} {screen.purpose}".lower()
    for category, words in CATEGORY_KW:
        if _mentions(text, words):
            return category
    return None


def screenshot_file(set_id: str, category: PageCategory) -> str:
    domain = REFERENCE_SETS[set_id]["domain"]
    return f"{domain}/{set_id} -- {CATEGORY_FILES[category]}.png"


def categories_prompt() -> str:
    return ", ".join(f"{k} ({v})" for k, v in CATEGORY_LABELS.items())
