"""Features and performance: must-have features, and advertised vs. independently tested performance."""
from __future__ import annotations

from ..core.evidence import Status
from ..core.errors import UnitError
from ..scoring.criteria import Criterion, numeric

TESTED = {Status.INDEPENDENTLY_TESTED, Status.VERIFIED}


def criteria(product, ctx) -> list:
    out = []
    must = [str(m) for m in ctx.request.user.get("must_have") or []]
    if must:
        met, known, ids = 0, 0, []
        for m in must:
            c = product.claim(f"feature.{m}")
            if c is None:
                continue
            known += 1
            ids.append(c.id)
            if c.value is True:
                met += 1
        unknown = len(must) - known
        if known:
            out.append(Criterion("features_performance", "your must-have features", met / len(must) * 100,
                                 sum(ctx.conf(next(x for x in product.claims if x.id == i)) for i in ids) / len(ids),
                                 2.0, tuple(ids), f"{met} of {len(must)} must-haves confirmed"
                                 + (f"; {unknown} not documented (counted as not met)" if unknown else "")))
    # Advertised vs tested: performance.X (claimed) against test.X (independent)
    for claimed in product.claims_of("performance"):
        if not claimed.is_known():
            continue
        name = claimed.claim_type.split(".", 1)[1]
        tested = product.claim(f"test.{name}")
        if tested is None or tested.status not in TESTED:
            continue
        try:
            a, b = numeric(claimed, claimed.unit), numeric(tested, claimed.unit)
        except (UnitError, ValueError, ArithmeticError) as e:
            ctx.note(product.id, f"Couldn't compare {name}: {e}")
            continue
        if a <= 0:
            continue
        ratio = b / a
        out.append(Criterion("features_performance", f"{name.replace('_', ' ')}: tested vs advertised",
                             min(100.0, ratio * 100), ctx.conf(tested), 1.5, (claimed.id, tested.id),
                             f"tested {b:g} vs advertised {a:g} ({ratio * 100:.0f}% of the claim)"))
    return out
