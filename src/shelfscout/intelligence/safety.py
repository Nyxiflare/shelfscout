"""Safety: jurisdiction-aware requirements, verification status, recalls and eligibility signals.

- A requirement counts as met only through a claim. A manufacturer's statement or a logo on a
  listing is "declared" (MANUFACTURER_REPORTED). Only an independent record or test is "verified".
- A failed mandatory requirement or an active recall excludes the product, whatever its score.
- A mandatory requirement with no evidence is "unresolved", and the category gate decides whether
  that means a safety hold or a provisional result.
- No requirement list here is legal advice. Profiles record when requirements were last reviewed.
"""
from __future__ import annotations

from ..core.evidence import Status
from ..profiles.loader import requirements_for
from ..scoring.criteria import Criterion

VERIFIED = {Status.VERIFIED, Status.INDEPENDENTLY_TESTED}


def assess(product, ctx) -> dict:
    reqs = requirements_for(ctx.profile, ctx.request.country)
    records = {s.requirement_id: s for s in product.safety}
    claims = {c.id: c for c in product.claims}
    result = {"requirements": [], "failed_mandatory": [], "unresolved_mandatory": [], "active_recalls": [],
              "closed_recalls": [], "criteria": []}
    for r in reqs:
        rec = records.get(r["id"])
        entry = {"id": r["id"], "name": r["name"], "jurisdiction": r["jurisdiction"], "mandatory": r["mandatory"],
                 "outcome": "unknown", "evidence": None, "verification": "none"}
        if rec and rec.outcome == "not_applicable":
            entry["outcome"] = "not_applicable"
        elif rec and rec.outcome in ("pass", "fail"):
            c = claims.get(rec.claim_id)
            entry.update(outcome=rec.outcome, evidence=c.id if c else None,
                         verification="verified" if c and c.status in VERIFIED else "declared")
            if rec.outcome == "pass":
                score = 100.0 if entry["verification"] == "verified" else 60.0
                result["criteria"].append(Criterion("safety", r["name"], score, ctx.conf(c), 2.0 if r["mandatory"] else 0.5,
                                                    (c.id,), f"{r['name']}: {'verified' if score == 100 else 'declared by the seller or brand, not verified'}"))
            elif r["mandatory"]:
                result["failed_mandatory"].append(r["name"])
                result["criteria"].append(Criterion("safety", r["name"], 0.0, ctx.conf(c), 3.0, (c.id,),
                                                    f"{r['name']}: failed"))
        if r["mandatory"] and entry["outcome"] == "unknown":
            result["unresolved_mandatory"].append(r["name"])
            # Some mandatory requirements are rarely checkable from public information (for example
            # battery transport tests); profiles can mark them so a gap makes a result provisional
            # rather than holding every product in the category.
            if r.get("on_unresolved"):
                result.setdefault("unresolved_outcomes", {})[r["name"]] = r["on_unresolved"]
        result["requirements"].append(entry)
    unknown_records = set(records) - {r["id"] for r in reqs}
    for rid in unknown_records:
        ctx.note(product.id, f"Safety record '{rid}' doesn't match a requirement for {ctx.request.country or 'this market'}.")
    for rc in product.recalls:
        status = str(rc.get("status", "")).lower()
        (result["active_recalls"] if status == "active" else result["closed_recalls"]).append(str(rc.get("id") or rc.get("title") or "recall"))
    # Independent safety tests (claim type test.safety.*) add evidence beyond certifications.
    for c in product.claims_of("test.safety"):
        if c.is_known() and isinstance(c.value, bool):
            result["criteria"].append(Criterion("safety", c.claim_type.split(".", 2)[-1].replace("_", " "),
                                                100.0 if c.value else 0.0, ctx.conf(c), 1.0, (c.id,),
                                                f"safety test {'passed' if c.value else 'failed'}"))
            if not c.value and c.status in VERIFIED:
                result["failed_mandatory"].append(c.claim_type)
    return result


def criteria(product, ctx) -> list:
    res = assess(product, ctx)
    ctx.notes.setdefault("_safety", {})[product.id] = res
    return res["criteria"]
