"""Total cost of ownership: what owning the product costs over a period, not just the sticker price.

TCO = purchase (to the door) + maintenance + repairs + consumables + energy, over `years`.
Each part needs evidence; missing parts are listed, never assumed to be zero.
"""
from __future__ import annotations

from decimal import Decimal

from ..core.money import Money


def tco(purchase: Money, years: float, *, maintenance_per_year=None, consumables_per_year=None, expected_repairs=None,
        energy_kwh_per_year=None, energy_price_per_kwh=None) -> dict:
    y = Decimal(str(years))
    if y <= 0:
        raise ValueError("years must be positive")
    cur = purchase.currency
    parts = {"purchase": purchase}
    missing = []
    for name, v in (("maintenance", maintenance_per_year), ("consumables", consumables_per_year)):
        if v is None:
            missing.append(name)
        else:
            parts[name] = Money(v, cur).times(y)
    if expected_repairs is None:
        missing.append("repairs")
    else:
        parts["repairs"] = Money(expected_repairs, cur)
    if energy_kwh_per_year is None or energy_price_per_kwh is None:
        missing.append("energy")
    else:
        parts["energy"] = Money(energy_price_per_kwh, cur).times(Decimal(str(energy_kwh_per_year)) * y)
    total = Money(0, cur)
    for v in parts.values():
        total = total + v
    return {"years": float(y), "parts": {k: v.rounded() for k, v in parts.items()}, "total": total.rounded(),
            "per_year": total.times(Decimal(1) / y).rounded(), "missing": missing}
