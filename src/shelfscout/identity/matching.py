"""Product identity: deciding whether two listings are the same product variant.

Conservative by design (ADR-7): listings match only on a shared GTIN, or the same brand and model
number with no conflicting variant attribute. Similar titles alone never merge products; they are
reported as "possible match, needs confirmation".
"""
from __future__ import annotations

import re


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def compare(a: dict, b: dict) -> dict:
    """a and b: {"name", "brand", "model_number", "gtin", "variant": {...}}."""
    va, vb = a.get("variant") or {}, b.get("variant") or {}
    conflicts = sorted(k for k in set(va) & set(vb) if _norm(str(va[k])) != _norm(str(vb[k])))
    ga, gb = _norm(a.get("gtin", "")), _norm(b.get("gtin", ""))
    if ga and gb:
        if ga == gb:
            return {"verdict": "same_variant", "basis": "same GTIN/EAN/UPC", "conflicts": conflicts}
        if _norm(a.get("model_number", "")) and _norm(a.get("model_number", "")) == _norm(b.get("model_number", "")):
            return {"verdict": "same_product_other_variant", "basis": "same model number, different GTIN", "conflicts": conflicts}
        return {"verdict": "different", "basis": "different GTINs", "conflicts": conflicts}
    ma, mb = _norm(a.get("model_number", "")), _norm(b.get("model_number", ""))
    same_brand = _norm(a.get("brand", "")) and _norm(a.get("brand", "")) == _norm(b.get("brand", ""))
    if ma and mb and same_brand:
        if ma != mb:
            return {"verdict": "different", "basis": "same brand, different model numbers", "conflicts": conflicts}
        if conflicts:
            return {"verdict": "same_product_other_variant", "basis": f"same model, different {', '.join(conflicts)}",
                    "conflicts": conflicts}
        return {"verdict": "same_variant", "basis": "same brand and model number, no conflicting variant details",
                "conflicts": conflicts}
    ta, tb = _tokens(a.get("name", "")), _tokens(b.get("name", ""))
    sim = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    if sim >= 0.6:
        return {"verdict": "possible_match", "basis": f"similar titles ({sim:.0%} shared words) but no model number or GTIN "
                "to confirm. Don't merge reviews or specs until confirmed", "conflicts": conflicts}
    return {"verdict": "different", "basis": "no shared identifiers", "conflicts": conflicts}
