"""Ergonomics: measured fit and adjustability, separate from reported comfort.

Fit rules are simplified, commonly cited workplace-ergonomics guidance (for example, seat height
close to the sitter's popliteal height plus a shoe allowance; enough clearance between the seat
front and the back of the knee). They are approximations for comparison, labelled as such in every
basis, not a substitute for trying the product. Subjective comfort from reviews is scored by the
reviews module as a separate criterion.
"""
from __future__ import annotations

from ..core.errors import UnitError
from ..core.units import Quantity, Range, parse_value
from ..scoring.criteria import Criterion, linear

APPROX = "approximate ergonomic guidance, not a fitting"


def _range(claim, unit):
    v = parse_value(claim.value, claim.unit) if claim.unit else None
    if isinstance(v, Quantity):
        v = Range(v, v)
    if not isinstance(v, Range):
        raise UnitError(f"{claim.claim_type} needs a value with a unit.")
    return v.to(unit)


def _distance_score(r: Range, target: float, per_unit_penalty: float) -> float:
    lo, hi = float(r.low.value), float(r.high.value)
    if lo <= target <= hi:
        return 100.0
    gap = lo - target if target < lo else target - hi
    return max(0.0, 100.0 - gap * per_unit_penalty)


def office_chair(product, ctx) -> list:
    out = []
    body = ctx.request.user.get("body") or {}
    sh = product.claim("ergonomics.seat_height")
    if sh:
        try:
            r = _range(sh, "mm")
            if body.get("popliteal_height_cm") is not None:
                target = float(body["popliteal_height_cm"]) * 10 + 25     # +25 mm shoe allowance
                out.append(Criterion("ergonomics", "seat height fits you", _distance_score(r, target, 1.5), ctx.conf(sh),
                                     2.0, (sh.id,), f"seat {r.low.value:.0f}-{r.high.value:.0f} mm vs about {target:.0f} mm for "
                                     f"your popliteal height ({APPROX})"))
            else:
                span = float(r.high.value - r.low.value)
                out.append(Criterion("ergonomics", "seat height adjustment range", linear(span, 40, 120), ctx.conf(sh), 1.0,
                                     (sh.id,), f"{span:.0f} mm of height adjustment; add your popliteal height for a "
                                     f"personal fit check ({APPROX})"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    sd = product.claim("ergonomics.seat_depth")
    if sd:
        try:
            r = _range(sd, "mm")
            if body.get("buttock_popliteal_cm") is not None:
                bp = float(body["buttock_popliteal_cm"]) * 10
                ideal = Range.of(bp - 150, bp - 50, "mm")       # leave a hand's width or so behind the knee
                lo, hi = float(r.low.value), float(r.high.value)
                overlap = not (hi < float(ideal.low.value) or lo > float(ideal.high.value))
                score = 100.0 if overlap else max(0.0, 100 - min(abs(lo - float(ideal.high.value)),
                                                                 abs(hi - float(ideal.low.value))) * 1.5)
                out.append(Criterion("ergonomics", "seat depth fits you", score, ctx.conf(sd), 1.5, (sd.id,),
                                     f"seat depth {lo:.0f}-{hi:.0f} mm vs {ideal.low.value:.0f}-{ideal.high.value:.0f} mm "
                                     f"for your thigh length ({APPROX})"))
            else:
                adjustable = float(r.high.value - r.low.value) > 0
                out.append(Criterion("ergonomics", "seat depth adjustable", 85 if adjustable else 45, ctx.conf(sd), 1.0,
                                     (sd.id,), "adjustable seat depth suits more body sizes" if adjustable else "fixed seat depth"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    sw = product.claim("ergonomics.seat_width")
    if sw and body.get("hip_breadth_cm") is not None:
        try:
            w = float(_range(sw, "mm").low.value)
            need = float(body["hip_breadth_cm"]) * 10 + 25
            out.append(Criterion("ergonomics", "seat width fits you", 100 if w >= need else max(0, 100 - (need - w) * 3),
                                 ctx.conf(sw), 1.0, (sw.id,), f"seat {w:.0f} mm wide vs {need:.0f} mm needed ({APPROX})"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    lum = product.claim("ergonomics.lumbar")
    if lum:
        table = {"adjustable": 100, "height_adjustable": 100, "fixed": 60, "none": 15}
        key = str(lum.value).strip().lower()
        if key in table:
            out.append(Criterion("ergonomics", "lumbar support", table[key], ctx.conf(lum), 1.0, (lum.id,), f"lumbar: {lum.value}"))
    arm = product.claim("ergonomics.armrest_adjustments")
    if arm:
        try:
            n = int(arm.value)
            out.append(Criterion("ergonomics", "armrest adjustability", {0: 20, 1: 45, 2: 65, 3: 85}.get(n, 100),
                                 ctx.conf(arm), 1.0, (arm.id,), f"{n}D armrests"))
        except (TypeError, ValueError):
            ctx.note(product.id, "ergonomics.armrest_adjustments should be a number (e.g. 4 for 4D).")
    rec = product.claim("ergonomics.recline_lock")
    if rec and isinstance(rec.value, bool):
        out.append(Criterion("ergonomics", "recline with lock", 90 if rec.value else 50, ctx.conf(rec), 0.5, (rec.id,),
                             "recline locks in position" if rec.value else "no recline lock"))
    cap = product.claim("construction.weight_capacity")
    if cap and body.get("weight_kg") is not None:
        try:
            kg = float(_range(cap, "kg").low.value)
            need = float(body["weight_kg"]) * 1.2
            out.append(Criterion("durability", "weight capacity margin", linear(kg, need * 0.8, need), ctx.conf(cap), 1.0,
                                 (cap.id,), f"rated {kg:.0f} kg vs your weight plus a 20% margin ({need:.0f} kg)"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    return out


def smartphone(product, ctx) -> list:
    out = []
    width = product.claim("ergonomics.width")
    if width:
        try:
            w = float(_range(width, "mm").low.value)
            out.append(Criterion("ergonomics", "one-hand width", linear(w, 80, 70), ctx.conf(width), 1.0, (width.id,),
                                 f"{w:.1f} mm wide; narrower is easier to use one-handed ({APPROX})"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    weight = product.claim("ergonomics.weight")
    if weight:
        try:
            g = float(_range(weight, "g").low.value)
            out.append(Criterion("ergonomics", "weight in the hand", linear(g, 240, 160), ctx.conf(weight), 1.0, (weight.id,),
                                 f"{g:.0f} g; lighter is less tiring to hold ({APPROX})"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    return out


def running_shoe(product, ctx) -> list:
    out = []
    user = ctx.request.user
    widths = product.claim("fit.widths_available")
    if widths and user.get("foot_width"):
        avail = [str(x).lower() for x in (widths.value if isinstance(widths.value, list) else [widths.value])]
        ok = str(user["foot_width"]).lower() in avail
        out.append(Criterion("ergonomics", "available in your width", 100 if ok else 20, ctx.conf(widths), 2.0, (widths.id,),
                             f"widths {', '.join(avail)}; you need {user['foot_width']}"))
    drop = product.claim("fit.heel_toe_drop")
    pref = user.get("preferred_drop_mm")
    if drop and isinstance(pref, list) and len(pref) == 2:
        try:
            d = float(_range(drop, "mm").low.value)
            out.append(Criterion("ergonomics", "heel-to-toe drop matches your preference",
                                 _distance_score(Range.of(pref[0], pref[1], "mm"), d, 15), ctx.conf(drop), 1.0, (drop.id,),
                                 f"{d:.0f} mm drop vs your preferred {pref[0]}-{pref[1]} mm"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    weight = product.claim("ergonomics.weight")
    if weight:
        try:
            g = float(_range(weight, "g").low.value)
            out.append(Criterion("ergonomics", "shoe weight", linear(g, 340, 210), ctx.conf(weight), 1.0, (weight.id,),
                                 f"{g:.0f} g per shoe (reference size)"))
        except UnitError as e:
            ctx.note(product.id, str(e))
    return out


MODELS = {"office_chair": office_chair, "smartphone": smartphone, "running_shoe": running_shoe}


def criteria(product, ctx) -> list:
    model = MODELS.get(ctx.profile.get("ergonomics_model"))
    return model(product, ctx) if model else []
