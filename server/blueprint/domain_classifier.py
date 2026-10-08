"""Rules-based domain classifier.

Classifies a requirement into one of the business domains that have reference
screenshots (``screenshots/<domain>/``), then picks the reference set inside
that domain. No model or keys needed: every domain has weighted terms, each term
found in the requirement adds its weight once, and the highest score wins.

    "Website for our accounting firm with a contact form"
      → finance: accounting(3) → set 02 (Accounting & consulting)

Terms match at a word start, so "consult" also matches "consulting" and
"consultancy". Edit the tables below to tune the classifier.
"""

from __future__ import annotations

import re

from blueprint.models import DomainMatch

# domain -> display name, weighted terms, and its reference sets (first = default)
DOMAIN_RULES: dict[str, dict] = {
    "finance": {
        "name": "Finance & accounting",
        "terms": {
            "accounting": 3,
            "accountant": 3,
            "bookkeeping": 3,
            "finance": 3,
            "financial": 3,
            "bank": 3,
            "investment": 3,
            "insurance": 3,
            "loan": 3,
            "mortgage": 3,
            "wealth": 3,
            "tax": 2,
            "audit": 2,
            "payroll": 2,
            "fintech": 2,
            "credit": 2,
            "invoice": 1,
            "budget": 1,
        },
        "sets": ["01", "02"],
    },
    "ecommerce": {
        "name": "E-commerce",
        "terms": {
            "e-commerce": 3,
            "ecommerce": 3,
            "online shop": 3,
            "online store": 3,
            "webshop": 3,
            "shop": 2,
            "store": 2,
            "cart": 3,
            "checkout": 3,
            "fashion": 3,
            "clothing": 3,
            "retail": 3,
            "product": 2,
            "catalog": 1,
            "catalogue": 1,
            "order": 1,
            "wishlist": 2,
        },
        "sets": ["03"],
    },
    "hospitality": {
        "name": "Hospitality & travel",
        "terms": {
            "hotel": 3,
            "resort": 3,
            "hostel": 3,
            "restaurant": 3,
            "travel": 3,
            "holiday": 3,
            "vacation": 3,
            "suite": 2,
            "room": 2,
            "check-in": 2,
            "guest": 2,
            "reservation": 2,
            "stay": 1,
            "booking": 1,
            "tourism": 3,
            "spa": 2,
        },
        "sets": ["04"],
    },
    "it-services": {
        "name": "IT services & tech",
        "terms": {
            "software": 3,
            "saas": 3,
            "it services": 3,
            "it support": 3,
            "managed services": 3,
            "cloud": 3,
            "cybersecurity": 3,
            "devops": 3,
            "hosting": 2,
            "tech": 2,
            "technology": 2,
            "platform": 1,
            "api": 2,
            "data": 1,
            "app": 1,
            "digital": 1,
        },
        "sets": ["05"],
    },
}

# Inside a domain with several sets, these terms choose the set (highest score wins).
SET_TERMS: dict[str, dict[str, int]] = {
    "01": {"bank": 3, "investment": 3, "insurance": 3, "loan": 3, "mortgage": 3, "wealth": 3},
    "02": {
        "accounting": 3,
        "accountant": 3,
        "bookkeeping": 3,
        "tax": 2,
        "audit": 2,
        "payroll": 2,
        "consult": 2,
        "advis": 2,
        "compliance": 2,
    },
}

DEFAULT_DOMAIN = "it-services"
MIN_SCORE = 2  # below this, the requirement is too vague and the default domain is used


def _score(text: str, terms: dict[str, int]) -> tuple[int, list[str]]:
    matched: list[str] = []
    # Longest terms first, and blank out what they matched, so "online shop" does not
    # also score "shop".
    for term in sorted(terms, key=len, reverse=True):
        pattern = rf"\b{re.escape(term)}\w*"
        if re.search(pattern, text):
            matched.append(term)
            text = re.sub(pattern, " ", text)
    return sum(terms[t] for t in matched), matched


def classify_domain(requirement: str) -> DomainMatch:
    text = requirement.lower()
    scores = {d: _score(text, r["terms"]) for d, r in DOMAIN_RULES.items()}
    # max() keeps the first domain on a tie, so table order is the tie-breaker.
    domain = max(scores, key=lambda d: scores[d][0])
    score, matched = scores[domain]
    total = sum(s for s, _ in scores.values())
    fallback = score < MIN_SCORE
    if fallback:
        domain, matched = DEFAULT_DOMAIN, []

    sets = DOMAIN_RULES[domain]["sets"]
    set_id = sets[0]
    if len(sets) > 1:
        best = max(sets, key=lambda s: _score(text, SET_TERMS.get(s, {}))[0])
        if _score(text, SET_TERMS.get(best, {}))[0] > 0:
            set_id = best

    return DomainMatch(
        domain=domain,
        name=DOMAIN_RULES[domain]["name"],
        reference_set=set_id,
        score=0 if fallback else score,
        confidence=0.0 if fallback else round(score / total, 2),
        matched=matched,
        fallback=fallback,
    )
