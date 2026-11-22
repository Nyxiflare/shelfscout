"""The evaluation engine: evidence in, explainable scores, eligibility and rankings out.

Layers (docs/ARCHITECTURE.md, ADR-5):
1. dimension scores 0-100, only from criteria backed by evidence
2. overall score: weighted mean over scored dimensions (weights renormalised; missing ones listed)
3. confidence per dimension, and evidence coverage (share of weight that has a score)
4. eligibility: ELIGIBLE / PROVISIONAL / INSUFFICIENT_EVIDENCE / SAFETY_HOLD / EXCLUDED,
   with safety gates that no score or personal weighting can override
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from .. import ALGORITHM_VERSION
from ..core.models import parse_request
from ..intelligence import ergonomics, features, materials, reviews, safety
from ..profiles.loader import DIMENSIONS, DIMENSION_LABELS, load_profile
from .confidence import coefficients
from .criteria import Context, Criterion, agent_criteria, apply_rules

STATUS_ORDER = {"ELIGIBLE": 0, "PROVISIONAL": 1, "INSUFFICIENT_EVIDENCE": 2, "SAFETY_HOLD": 3, "EXCLUDED": 4}
RECOMMENDABLE = {"ELIGIBLE", "PROVISIONAL"}
MIN_COVERAGE = 0.5          # below this share of the weight scored: insufficient evidence
FULL_COVERAGE = 0.8         # below this: provisional
MIN_CONFIDENCE = 50.0       # mean confidence below this: provisional
BEST_IN_MIN_CONFIDENCE = 40.0


def _aggregate(criteria: list) -> dict:
    dims = {}
    for c in criteria:
        dims.setdefault(c.dimension, []).append(c)
    out = {}
    for d, items in dims.items():
        w = sum(c.weight for c in items)
        out[d] = {"score": round(sum(c.score * c.weight for c in items) / w, 1),
                  "confidence": round(sum(c.confidence * c.weight for c in items) / w, 1),
                  "criteria": [vars(c) for c in items]}
    return out


def _overall(dims: dict, weights: dict, exclude=()) -> tuple:
    scored = {d: v for d, v in dims.items() if d in weights and d not in exclude and weights[d] > 0}
    wsum = sum(weights[d] for d in scored)
    if not wsum:
        return None, 0.0, None
    score = sum(dims[d]["score"] * weights[d] for d in scored) / wsum
    conf = sum(dims[d]["confidence"] * weights[d] for d in scored) / wsum
    coverage = wsum / sum(w for d, w in weights.items() if d not in exclude)
    return round(score, 1), round(coverage, 3), round(conf, 1)


def _eligibility(product, dims: dict, coverage: float, mean_conf, profile: dict, safety_res: dict, notes: list) -> tuple:
    reasons, status = [], "ELIGIBLE"

    def worse(s, why):
        nonlocal status
        reasons.append(why)
        if STATUS_ORDER[s] > STATUS_ORDER[status]:
            status = s

    if safety_res["active_recalls"]:
        worse("EXCLUDED", "active recall: " + ", ".join(safety_res["active_recalls"]))
    if safety_res["failed_mandatory"]:
        worse("EXCLUDED", "failed a mandatory safety requirement: " + ", ".join(safety_res["failed_mandatory"]))
    for g in profile.get("gates", []):
        d = g["dimension"]
        if d not in dims:
            worse(g.get("on_missing", "PROVISIONAL"), f"no {DIMENSION_LABELS[d].lower()} evidence ({g['id']})")
        elif g.get("min_score") is not None and dims[d]["score"] < g["min_score"]:
            worse(g.get("on_below", "SAFETY_HOLD"), f"{DIMENSION_LABELS[d].lower()} score {dims[d]['score']} is below "
                                                    f"{g['min_score']} ({g['id']})")
    if safety_res["unresolved_mandatory"]:
        hold = next((g.get("on_missing") for g in profile.get("gates", []) if g["dimension"] == "safety"), "PROVISIONAL")
        special = safety_res.get("unresolved_outcomes", {})
        for name in safety_res["unresolved_mandatory"]:
            worse(special.get(name, hold), f"mandatory requirement not evidenced: {name}"
                  + (" (rarely verifiable publicly)" if name in special else ""))
    severe = [n for n in notes if "safety complaint" in n]
    if severe:
        if any("worst severity 5" in n for n in severe):
            worse("SAFETY_HOLD", "an owner reports a dangerous safety incident; check it before buying")
        else:
            worse("PROVISIONAL", "serious safety complaints in reviews need checking")
    if coverage < MIN_COVERAGE:
        worse("INSUFFICIENT_EVIDENCE", f"only {coverage * 100:.0f}% of the scoring weight has evidence")
    elif coverage < FULL_COVERAGE:
        worse("PROVISIONAL", f"{coverage * 100:.0f}% of the scoring weight has evidence")
    if mean_conf is not None and mean_conf < MIN_CONFIDENCE:
        worse("PROVISIONAL", f"mean evidence confidence {mean_conf:.0f} is below {MIN_CONFIDENCE:.0f}")
    return status, reasons


def _priority_weights(base: dict, priorities: dict) -> dict:
    """Personal priorities replace the profile weights for the dimensions they name; the rest keep a
    small share, so nothing disappears. Gates are unaffected."""
    if not priorities:
        return base
    named = {d: float(v) for d, v in priorities.items() if d in DIMENSIONS and float(v) > 0}
    if not named:
        return base
    rest = {d: w for d, w in base.items() if d not in named}
    rest_total = sum(rest.values())
    share = 10.0  # 10% of the weight stays with unnamed dimensions
    total_named = sum(named.values())
    out = {d: v / total_named * (100 - share) for d, v in named.items()}
    out.update({d: (w / rest_total * share if rest_total else 0.0) for d, w in rest.items()})
    return out


def evaluate(data: dict, profile_dir=None) -> dict:
    request = parse_request(data)
    profile = load_profile(request.category, profile_dir)
    as_of = request.as_of or dt.date.today()
    ctx = Context(request=request, profile=profile, coeffs=coefficients(profile), as_of=as_of)
    weights = dict(profile["weights"])
    results = []
    for p in request.products:
        crit = []
        crit += apply_rules(p, profile.get("spec_rules"), ctx)
        crit += reviews.criteria(p, ctx)
        crit += materials.criteria(p, ctx)
        crit += ergonomics.criteria(p, ctx)
        crit += safety.criteria(p, ctx)
        crit += features.criteria(p, ctx)
        crit += agent_criteria(p, ctx)
        results.append({"product": p, "criteria": crit})
    # Price-to-value needs the other dimensions first: quality per unit of money, relative to the best.
    for r in results:
        r["dims"] = _aggregate(r["criteria"])
        r["quality"], r["quality_cov"], r["quality_conf"] = _overall(r["dims"], weights, exclude=("price_value",))
    priced = [r for r in results if r["product"].listing and r["quality"] is not None]
    if len(priced) >= 2:
        ratios = {id(r): r["quality"] / float(r["product"].listing.total().amount) for r in priced
                  if r["product"].listing.total().amount > 0}
        best = max(ratios.values()) if ratios else 0
        for r in priced:
            if id(r) in ratios and best > 0:
                total = r["product"].listing.total()
                # A ratio is only as good as the quality score behind it: scale by its evidence coverage.
                conf = min(r["quality_conf"] or 0, 70.0) * (r["quality_cov"] or 0)
                r["criteria"].append(Criterion("price_value", "quality per unit of price", ratios[id(r)] / best * 100, conf, 1.0, (),
                                               f"quality score excluding price {r['quality']} for {total.format()} (to the door, before tax), "
                                               "relative to the best ratio in this comparison", "computed"))
                r["dims"] = _aggregate(r["criteria"])
    elif priced:
        ctx.note(priced[0]["product"].id, "Price-to-value needs at least two priced products to compare.")
    bundle_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    evaluations = []
    for r in results:
        p = r["product"]
        score, coverage, mean_conf = _overall(r["dims"], weights)
        notes = ctx.notes.get(p.id, [])
        sres = ctx.notes.get("_safety", {}).get(p.id, {"active_recalls": [], "failed_mandatory": [],
                                                       "unresolved_mandatory": [], "requirements": []})
        status, reasons = _eligibility(p, r["dims"], coverage, mean_conf, profile, sres, notes)
        within = None
        if p.listing and (request.budget_min or request.budget_max):
            t = p.listing.total()
            within = (request.budget_min is None or t >= request.budget_min) and (request.budget_max is None or t <= request.budget_max)
        personal = None
        if request.priorities:
            personal, _, _ = _overall(r["dims"], _priority_weights(weights, request.priorities))
        evaluations.append({
            "product_id": p.id, "name": p.name, "brand": p.brand, "model_number": p.model_number, "variant": p.variant,
            "price": p.listing.total().format() if p.listing else None,
            "price_amount": str(p.listing.total().amount) if p.listing else None,
            "marketplace": p.listing.marketplace if p.listing else None, "url": p.listing.url if p.listing else "",
            "overall_score": score, "personal_score": personal, "coverage": coverage, "confidence": mean_conf,
            "eligibility": status, "eligibility_reasons": reasons, "within_budget": within,
            "dimensions": {d: r["dims"][d] for d in DIMENSIONS if d in r["dims"]},
            "missing_dimensions": [d for d in DIMENSIONS if d not in r["dims"] and weights.get(d, 0) > 0],
            "safety": sres, "reviews": ctx.notes.get("_reviews", {}).get(p.id), "notes": notes,
            "unknown_claims": [c.claim_type for c in p.claims if not c.is_known()],
            "limitations": [f"{c.claim_type}: {'; '.join(c.limitations)}" for c in p.claims if c.limitations],
            "unscored_claims": sorted({c.claim_type for c in p.claims if c.is_known()} - {
                cl.claim_type for crit in r["criteria"] for cid in crit.claims for cl in p.claims if cl.id == cid}),
        })
    return {"algorithm_version": ALGORITHM_VERSION, "profile": profile["id"], "profile_version": profile["version"],
            "profile_lineage": profile["lineage"], "calibration": profile.get("calibration", ""),
            "category": request.category, "country": request.country, "currency": request.currency, "as_of": as_of.isoformat(),
            "input_hash": bundle_hash, "weights": weights, "priorities": request.priorities,
            "budget": {"min": request.budget_min.format() if request.budget_min else None,
                       "max": request.budget_max.format() if request.budget_max else None},
            "evaluations": evaluations, "rankings": rankings(evaluations, request)}


def _key(e, field="overall_score"):
    return (STATUS_ORDER[e["eligibility"]], -(e[field] if e[field] is not None else -1))


def rankings(evals: list, request) -> dict:
    out = {"overall": [e["product_id"] for e in sorted(evals, key=_key)]}
    if request.budget_min or request.budget_max:
        inside = [e for e in evals if e["within_budget"]]
        out["within_budget"] = [e["product_id"] for e in sorted(inside, key=_key)]
        out["over_or_under_budget"] = [e["product_id"] for e in evals if e["within_budget"] is False]
    if request.priorities:
        out["personal"] = [e["product_id"] for e in sorted(evals, key=lambda e: _key(e, "personal_score"))]
    best = {}
    for d in DIMENSIONS:
        cands = [e for e in evals if e["eligibility"] in RECOMMENDABLE and d in e["dimensions"]
                 and e["dimensions"][d]["confidence"] >= BEST_IN_MIN_CONFIDENCE]
        if request.budget_min or request.budget_max:
            cands = [e for e in cands if e["within_budget"]]
        if cands:
            top = max(cands, key=lambda e: e["dimensions"][d]["score"])
            best[d] = top["product_id"]
    out["best_by_dimension"] = best
    field = "personal_score" if request.priorities else "overall_score"
    recommendable = [e for e in sorted(evals, key=lambda e: _key(e, field)) if e["eligibility"] in RECOMMENDABLE
                     and (e["within_budget"] is not False)]
    out["recommended_by"] = "your priorities" if request.priorities else "the category weights"
    out["recommended"] = recommendable[0]["product_id"] if recommendable else None
    out["avoid"] = [e["product_id"] for e in evals if e["eligibility"] in ("EXCLUDED", "SAFETY_HOLD")]
    return out
