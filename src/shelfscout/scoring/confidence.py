"""Evidence confidence, kept separate from product quality.

confidence = 0.30 source quality + 0.25 directness + 0.20 variant relevance + 0.15 independence
           + 0.10 freshness  (each 0-100)

The coefficients are configuration (a profile may override them under "confidence"), not constants,
and are versioned with the algorithm. They are starting assumptions to be calibrated.
"""
from __future__ import annotations

import datetime as dt

from ..core.evidence import Claim, EvidenceSource, Independence, SourceType, Status

DEFAULT_COEFFICIENTS = {"source_quality": 0.30, "directness": 0.25, "relevance": 0.20,
                        "independence": 0.15, "freshness": 0.10}
SOURCE_QUALITY = {
    SourceType.INDEPENDENT_LAB: 95, SourceType.GOVERNMENT_RECORD: 95, SourceType.STANDARDS_BODY: 90,
    SourceType.EXPERT_REVIEW: 75, SourceType.MANUFACTURER: 60, SourceType.USER_PROVIDED: 70,
    SourceType.CUSTOMER_REVIEWS: 55, SourceType.MARKETPLACE_LISTING: 45, SourceType.FORUM: 40,
    SourceType.REFERENCE_DATA: 50, SourceType.MODEL: 40,
}
DIRECTNESS = {Status.INDEPENDENTLY_TESTED: 100, Status.VERIFIED: 90, Status.MANUFACTURER_REPORTED: 60,
              Status.CUSTOMER_REPORTED: 55, Status.ESTIMATED: 30, Status.UNKNOWN: 0}
RELEVANCE = {"exact": 100, "other_variant": 60, "product_family": 40, "brand": 20}
INDEPENDENCE = {Independence.INDEPENDENT: 100, Independence.UNKNOWN: 50, Independence.AFFILIATED: 30,
                Independence.SELLER: 25, Independence.MANUFACTURER: 20}


def coefficients(profile: dict | None) -> dict:
    c = dict(DEFAULT_COEFFICIENTS)
    c.update((profile or {}).get("confidence", {}))
    total = sum(c.values())
    return {k: v / total for k, v in c.items()}


def freshness(date: dt.date | None, as_of: dt.date) -> float:
    if date is None:
        return 50.0
    age = (as_of - date).days
    if age <= 365:
        return 100.0
    if age >= 1825:
        return 20.0
    return 100.0 - (age - 365) / (1825 - 365) * 80.0


def claim_confidence(claim: Claim, source: EvidenceSource | None, as_of: dt.date, coeffs: dict) -> dict:
    """Return the 0-100 confidence and its components, so a report can explain it."""
    if not claim.is_known() or source is None:
        return {"confidence": 0.0, "components": {}}
    parts = {
        "source_quality": SOURCE_QUALITY.get(source.type, 40),
        "directness": DIRECTNESS[claim.status],
        "relevance": RELEVANCE.get(claim.variant_match, 20),
        "independence": INDEPENDENCE.get(source.independence, 50),
        "freshness": freshness(claim.observed_at or source.published_at, as_of),
    }
    value = sum(parts[k] * coeffs[k] for k in coeffs)
    return {"confidence": round(value, 1), "components": parts}


def sample_factor(n: int) -> float:
    """Reviews: confidence grows with sample size."""
    if n >= 100:
        return 1.0
    if n >= 30:
        return 0.85
    if n >= 10:
        return 0.65
    return 0.4
