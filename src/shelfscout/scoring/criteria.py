"""Criteria: the building blocks of dimension scores.

A dimension score is the weighted mean of its criteria. Each criterion says how it was scored
(computed from evidence, from reviews, or an agent's judgement tied to evidence), which claims it
used, and its confidence. A dimension with no criteria has no score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..core.evidence import Status
from ..core.units import Quantity, Range, parse_value
from ..core.errors import UnitError
from .confidence import claim_confidence

METHODS = ("computed", "reviews", "agent_judgement", "reference_data")
# Agent judgement is weaker than a computation from the same evidence.
AGENT_JUDGEMENT_FACTOR = 0.7
# Dimensions an agent may not score by judgement: they must come from records and calculations.
NO_JUDGEMENT = {"safety", "price_value"}


@dataclass
class Criterion:
    dimension: str
    name: str
    score: float
    confidence: float
    weight: float = 1.0
    claims: tuple = ()
    basis: str = ""
    method: str = "computed"

    def __post_init__(self):
        self.score = max(0.0, min(100.0, float(self.score)))
        self.confidence = max(0.0, min(100.0, float(self.confidence)))


@dataclass
class Context:
    request: object
    profile: dict
    coeffs: dict
    as_of: object
    notes: dict = field(default_factory=dict)   # product id -> list of notes for the report

    def note(self, pid: str, text: str) -> None:
        self.notes.setdefault(pid, []).append(text)

    def conf(self, claim) -> float:
        src = self.request.sources.get(claim.source_id) if claim.source_id else None
        return claim_confidence(claim, src, self.as_of, self.coeffs)["confidence"]


def linear(value: float, poor: float, good: float) -> float:
    """0 at `poor`, 100 at `good`, clamped. Works whichever direction is better."""
    if good == poor:
        return 100.0 if value >= good else 0.0
    return max(0.0, min(100.0, (value - poor) / (good - poor) * 100.0))


def numeric(claim, unit: str | None):
    """Claim value as a float in `unit`. Ranges use their midpoint. Raises UnitError on mismatch."""
    v = parse_value(claim.value, claim.unit) if claim.unit else claim.value
    if isinstance(v, Range):
        v = v.mid()
    if isinstance(v, Quantity):
        if unit is None:
            raise UnitError(f"Claim {claim.id} has unit {v.unit} but the rule has none.")
        return float(v.to(unit).value)
    if unit is not None:
        raise UnitError(f"Claim {claim.id} ({claim.claim_type}) has no unit; the rule expects {unit}.")
    if isinstance(v, bool):
        raise UnitError(f"Claim {claim.id} is true/false, not a number.")
    return float(Decimal(str(v)))


def apply_rules(product, rules: dict, ctx: Context) -> list:
    """Profile 'spec_rules': deterministic scoring of documented specs, e.g. warranty years, IP rating."""
    out = []
    for dimension, items in (rules or {}).items():
        for r in items:
            c = product.claim(r["claim"])
            if c is None:
                continue
            kind = r.get("kind", "linear")
            try:
                if kind == "linear":
                    score = linear(numeric(c, r.get("unit")), float(r["poor"]), float(r["good"]))
                elif kind == "map":
                    key = str(c.value).strip().lower()
                    table = {str(k).lower(): v for k, v in r["map"].items()}
                    if key not in table:
                        ctx.note(product.id, f"'{c.value}' for {c.claim_type} isn't in the scoring table, so it wasn't scored.")
                        continue
                    score = float(table[key])
                elif kind == "bool":
                    if not isinstance(c.value, bool):
                        ctx.note(product.id, f"{c.claim_type} should be true or false; not scored.")
                        continue
                    score = float(r.get("true", 100) if c.value else r.get("false", 0))
                else:
                    continue
            except (UnitError, ValueError, ArithmeticError) as e:
                ctx.note(product.id, f"{c.claim_type}: {e}")
                continue
            out.append(Criterion(dimension, r.get("label", c.claim_type), score, ctx.conf(c),
                                 float(r.get("weight", 1)), (c.id,), r.get("basis", f"from {c.claim_type} = {c.value}")))
    return out


def agent_criteria(product, ctx: Context) -> list:
    """Judgements the agent made about a product, allowed only when tied to known evidence."""
    out = []
    by_id = {c.id: c for c in product.claims}
    for i, j in enumerate(product.criteria, 1):
        dim = j.get("dimension")
        if dim in NO_JUDGEMENT:
            ctx.note(product.id, f"Judgement '{j.get('criterion')}' on {dim} ignored: {dim} must come from records, not judgement.")
            continue
        ids = [x for x in j.get("claims", []) if x in by_id and by_id[x].is_known()]
        if not ids:
            ctx.note(product.id, f"Judgement '{j.get('criterion', i)}' ignored: it isn't tied to any known claim.")
            continue
        try:
            score = float(j["score"])
        except (KeyError, TypeError, ValueError):
            ctx.note(product.id, f"Judgement '{j.get('criterion', i)}' has no numeric score.")
            continue
        conf = sum(ctx.conf(by_id[x]) for x in ids) / len(ids) * AGENT_JUDGEMENT_FACTOR
        out.append(Criterion(dim, str(j.get("criterion", f"judgement {i}")), score, conf, float(j.get("weight", 1)),
                             tuple(ids), str(j.get("basis", "")), "agent_judgement"))
    return out


def estimated_status(claims) -> Status:
    return Status.ESTIMATED if any(c.status is Status.ESTIMATED for c in claims) else Status.MANUFACTURER_REPORTED
