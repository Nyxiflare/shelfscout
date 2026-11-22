"""Category scoring profiles: weights, safety gates, requirements and engineering models per category.

Profiles are JSON files in profiles/data. A subcategory profile can `extend` a parent and override
parts of it. Every profile is validated: weights must cover the standard dimensions and sum to 100.
Profile versions are recorded on every evaluation so results can be reproduced.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.errors import ProfileError

DIMENSIONS = ("materials_build", "durability", "ergonomics", "safety", "customer_experience", "reliability",
              "after_sales_service", "features_performance", "aesthetics", "brand_trust", "price_value")
DIMENSION_LABELS = {
    "materials_build": "Materials & build", "durability": "Durability", "ergonomics": "Ergonomics",
    "safety": "Safety", "customer_experience": "Customer experience", "reliability": "Reliability",
    "after_sales_service": "After-sales service", "features_performance": "Features & performance",
    "aesthetics": "Aesthetics", "brand_trust": "Brand trust", "price_value": "Price-to-value",
}
GATE_OUTCOMES = ("PROVISIONAL", "SAFETY_HOLD", "INSUFFICIENT_EVIDENCE", "EXCLUDED")
DATA_DIR = Path(__file__).resolve().parent / "data"


def _read(name: str, directory: Path) -> dict:
    p = directory / f"{name}.json"
    if not p.is_file():
        available = ", ".join(sorted(x.stem for x in directory.glob("*.json")))
        raise ProfileError(f"No scoring profile '{name}'. Available: {available}.")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProfileError(f"Profile '{name}' is not valid JSON (line {e.lineno}): {e.msg}") from None


def load_profile(name: str, directory: Path | None = None) -> dict:
    directory = directory or DATA_DIR
    raw = _read(name, directory)
    chain = [raw]
    seen = {name}
    while chain[-1].get("extends"):
        parent = chain[-1]["extends"]
        if parent in seen:
            raise ProfileError(f"Profile '{name}' has a circular 'extends'.")
        seen.add(parent)
        chain.append(_read(parent, directory))
    merged: dict = {}
    for layer in reversed(chain):
        for k, v in layer.items():
            if k == "safety_requirements" and isinstance(v, list):
                merged[k] = merged.get(k, []) + v
            elif k == "spec_rules" and isinstance(v, dict):
                rules = {dim: list(items) for dim, items in merged.get(k, {}).items()}
                for dim, items in v.items():
                    rules[dim] = rules.get(dim, []) + list(items)
                merged[k] = rules
            else:
                merged[k] = v
    merged["id"] = raw.get("id", name)
    merged["lineage"] = [layer.get("id") for layer in chain]
    validate_profile(merged)
    return merged


def validate_profile(p: dict) -> None:
    pid = p.get("id", "?")
    w = p.get("weights")
    if not isinstance(w, dict):
        raise ProfileError(f"Profile '{pid}': weights missing.")
    unknown = set(w) - set(DIMENSIONS)
    if unknown:
        raise ProfileError(f"Profile '{pid}': unknown dimensions {sorted(unknown)}.")
    missing = set(DIMENSIONS) - set(w)
    if missing:
        raise ProfileError(f"Profile '{pid}': weights missing for {sorted(missing)}.")
    for k, v in w.items():
        if not isinstance(v, (int, float)) or v < 0:
            raise ProfileError(f"Profile '{pid}': weight for {k} must be a non-negative number.")
    total = sum(w.values())
    if abs(total - 100) > 1e-9:
        raise ProfileError(f"Profile '{pid}': weights sum to {total}, not 100.")
    if not str(p.get("version") or "").strip():
        raise ProfileError(f"Profile '{pid}': needs a version.")
    for g in p.get("gates", []):
        if g.get("dimension") not in DIMENSIONS:
            raise ProfileError(f"Profile '{pid}': gate '{g.get('id')}' names an unknown dimension.")
        for key in ("on_missing", "on_below"):
            if g.get(key) and g[key] not in GATE_OUTCOMES:
                raise ProfileError(f"Profile '{pid}': gate '{g.get('id')}' {key} must be one of {GATE_OUTCOMES}.")
    for dim, items in (p.get("spec_rules") or {}).items():
        if dim not in DIMENSIONS:
            raise ProfileError(f"Profile '{pid}': spec_rules names an unknown dimension '{dim}'.")
        for r in items:
            if r.get("kind", "linear") not in ("linear", "map", "bool") or not r.get("claim"):
                raise ProfileError(f"Profile '{pid}': a {dim} rule needs a claim and kind linear, map or bool.")
            if r.get("kind", "linear") == "linear" and ("poor" not in r or "good" not in r):
                raise ProfileError(f"Profile '{pid}': linear rule for {r['claim']} needs poor and good.")
    ids = [r.get("id") for r in p.get("safety_requirements", [])]
    if len(set(ids)) != len(ids) or any(not i for i in ids):
        raise ProfileError(f"Profile '{pid}': safety requirement ids must be present and unique.")
    for r in p.get("safety_requirements", []):
        if not isinstance(r.get("mandatory"), bool) or not r.get("jurisdiction"):
            raise ProfileError(f"Profile '{pid}': requirement '{r.get('id')}' needs a jurisdiction and mandatory true/false.")
        if r.get("on_unresolved") and r["on_unresolved"] not in GATE_OUTCOMES:
            raise ProfileError(f"Profile '{pid}': requirement '{r.get('id')}' on_unresolved must be one of {GATE_OUTCOMES}.")


def list_profiles(directory: Path | None = None) -> list:
    directory = directory or DATA_DIR
    return sorted(p.stem for p in directory.glob("*.json"))


def requirements_for(profile: dict, country: str) -> list:
    """Safety requirements that apply in a country. EU rules apply to EU member states; 'ALL' applies everywhere."""
    eu = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
          "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
    c = (country or "").upper()
    out = []
    for r in profile.get("safety_requirements", []):
        j = r["jurisdiction"].upper()
        if j == "ALL" or j == c or (j == "EU" and c in eu):
            out.append(r)
    return out
