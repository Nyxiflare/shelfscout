"""Material intelligence: a catalogue of typical property ranges and application-specific suitability.

- A material is matched only by an exact designation or alias. "Aluminium alloy" matches the generic
  aluminium entry (grade unknown, wide ranges), never 6061-T6. A grade is never assumed.
- Suitability is scored for an application (an office-chair frame, a phone frame, a shoe midsole),
  not as a universal ranking. If a required property is missing, the result is "incomplete" and no
  score is given.
- Catalogue values are ESTIMATED reference data. A product's own independently tested property
  (claim type "property.<name>") replaces the catalogue range.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..core.evidence import Status
from ..core.units import Quantity, Range
from ..scoring.criteria import Criterion, linear

DATA = Path(__file__).resolve().parent / "materials_data.json"
REFERENCE_CONFIDENCE = 30.0          # catalogue ranges describe a grade in general, not this product
GRADE_UNKNOWN_FACTOR = 0.6


@lru_cache(maxsize=1)
def catalogue() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    index = {}
    for m in data["materials"]:
        for alias in [m["id"], m["name"]] + m.get("aliases", []):
            key = alias.strip().lower()
            if key in index and index[key]["id"] != m["id"]:
                raise ValueError(f"Material alias '{alias}' is used twice.")
            index[key] = m
    return {"materials": data["materials"], "index": index, "applications": data["applications"],
            "version": data["version"], "about": data["about"]}


def find(name: str):
    """Exact alias lookup. Returns None when the material isn't in the catalogue."""
    return catalogue()["index"].get((name or "").strip().lower())


def search(text: str) -> list:
    t = (text or "").strip().lower()
    return [m for m in catalogue()["materials"] if t in m["name"].lower() or any(t in a for a in m.get("aliases", []))]


def property_range(material: dict, name: str):
    p = material.get("properties", {}).get(name)
    if not p:
        return None
    return Range.of(p[0], p[1], p[2])


def suitability(material: dict, application: str, measured: dict | None = None) -> dict:
    """Score how suitable a material is for an application, using range midpoints.
    `measured` maps property name -> Quantity from independent tests of the actual product."""
    app = catalogue()["applications"][application]
    measured = measured or {}
    parts, used, missing = [], [], []          # (score at low end, mid, high end, weight)
    for spec in app["properties"]:
        if "name" in spec:
            name = spec["name"]
            if name in measured:
                q = measured[name].to(spec["unit"])
                s = linear(float(q.value), spec["poor"], spec["good"])
                parts.append((s, s, s, spec["weight"]))
                used.append(f"{name} {q} (measured)")
                continue
            r = property_range(material, name)
            if r is None:
                missing.append(name)
                continue
            r = r.to(spec["unit"])
            lo = linear(float(r.low.value), spec["poor"], spec["good"])
            hi = linear(float(r.high.value), spec["poor"], spec["good"])
            parts.append((min(lo, hi), linear(float(r.mid().value), spec["poor"], spec["good"]), max(lo, hi), spec["weight"]))
            used.append(f"{name} {r.low.value.normalize():f}-{r.high.value.normalize():f} {spec['unit']} (typical range)")
        else:
            name = spec["rating"]
            value = material.get("ratings", {}).get(name)
            if value is None:
                missing.append(name)
                continue
            s = linear(value, spec["poor"], spec["good"])
            parts.append((s, s, s, spec["weight"]))
            used.append(f"{name} rating {value}/5")
    required_missing = [r for r in app.get("required", []) if r in missing and r not in measured]
    total_w = sum(p[3] for p in parts)
    if required_missing or total_w == 0:
        return {"complete": False, "missing": missing, "required_missing": required_missing, "used": used}
    score = sum(p[1] * p[3] for p in parts) / total_w
    spread = (round(sum(p[0] * p[3] for p in parts) / total_w, 1), round(sum(p[2] * p[3] for p in parts) / total_w, 1))
    return {"complete": True, "score": round(score, 1), "missing": missing, "used": used, "spread": spread,
            "grade_unknown": bool(material.get("grade_unknown"))}


def criteria(product, ctx) -> list:
    app_id = ctx.profile.get("material_application")
    if not app_id:
        return []
    app = catalogue()["applications"][app_id]
    claim = product.claim(f"material.{app['component']}")
    if claim is None:
        ctx.note(product.id, f"The {app['label']} material isn't documented, so material suitability wasn't scored.")
        return []
    material = find(str(claim.value))
    if material is None:
        ctx.note(product.id, f"Material '{claim.value}' isn't in the catalogue; add it with sourced values to score it.")
        return []
    measured = {}
    for c in product.claims_of("property"):
        if c.is_known() and c.status in (Status.INDEPENDENTLY_TESTED, Status.VERIFIED) and c.unit:
            measured[c.claim_type.split(".", 1)[1]] = Quantity(c.value, c.unit)
    res = suitability(material, app_id, measured)
    if not res["complete"]:
        ctx.note(product.id, f"Material suitability for {material['name']} is incomplete: missing "
                             f"{', '.join(res['required_missing'] or res['missing'])}.")
        return []
    conf = min(ctx.conf(claim), REFERENCE_CONFIDENCE if not measured else ctx.conf(claim))
    if res["grade_unknown"]:
        conf *= GRADE_UNKNOWN_FACTOR
    article = "an" if app["label"][:1].lower() in "aeiou" else "a"
    basis = (f"{material['name']} as {article} {app['label']}: " + "; ".join(res["used"])
             + (f". Grade not stated, so the plausible score spans {res['spread'][0]}-{res['spread'][1]}." if res["grade_unknown"] and res["spread"] else ".")
             + " Typical catalogue values, not measurements of this product.")
    return [Criterion("materials_build", "material suitability", res["score"], conf, 1.0, (claim.id,), basis,
                      "reference_data")]
