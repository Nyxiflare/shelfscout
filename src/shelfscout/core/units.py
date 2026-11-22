"""Physical quantities with dimension-safe conversion.

Every measured value in ShelfScout carries a unit. Values are converted to a dimension's base unit
before any comparison, and comparing different dimensions (say MPa with mm) raises UnitError.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .errors import UnitError

# unit -> (dimension, factor to base unit). Base units: m, kg, N, Pa, J, W, s, m3, kg/m3, W/m.K, ratio.
_LINEAR = {
    # length (base m)
    "mm": ("length", Decimal("0.001")), "cm": ("length", Decimal("0.01")), "m": ("length", Decimal(1)),
    "in": ("length", Decimal("0.0254")), "ft": ("length", Decimal("0.3048")),
    # mass (base kg)
    "g": ("mass", Decimal("0.001")), "kg": ("mass", Decimal(1)),
    "lb": ("mass", Decimal("0.45359237")), "oz": ("mass", Decimal("0.028349523125")),
    # force (base N)
    "N": ("force", Decimal(1)), "kN": ("force", Decimal(1000)), "lbf": ("force", Decimal("4.4482216152605")),
    # pressure / stress (base Pa)
    "Pa": ("stress", Decimal(1)), "kPa": ("stress", Decimal(1000)), "MPa": ("stress", Decimal(10) ** 6),
    "GPa": ("stress", Decimal(10) ** 9), "psi": ("stress", Decimal("6894.757293168")),
    "ksi": ("stress", Decimal("6894757.293168")),
    # energy (base J)
    "J": ("energy", Decimal(1)), "kJ": ("energy", Decimal(1000)), "Wh": ("energy", Decimal(3600)),
    "kWh": ("energy", Decimal(3600000)),
    # power (base W)
    "W": ("power", Decimal(1)), "kW": ("power", Decimal(1000)),
    # time (base s)
    "s": ("time", Decimal(1)), "min": ("time", Decimal(60)), "h": ("time", Decimal(3600)),
    "day": ("time", Decimal(86400)), "year": ("time", Decimal(31557600)),
    # volume (base m3)
    "ml": ("volume", Decimal("0.000001")), "l": ("volume", Decimal("0.001")), "m3": ("volume", Decimal(1)),
    # density (base kg/m3)
    "kg/m3": ("density", Decimal(1)), "g/cm3": ("density", Decimal(1000)),
    # thermal conductivity (base W/m.K)
    "W/m.K": ("thermal_conductivity", Decimal(1)),
    # impact energy per area (base J/m2)
    "J/m2": ("impact_area", Decimal(1)), "kJ/m2": ("impact_area", Decimal(1000)),
    # dimensionless
    "ratio": ("ratio", Decimal(1)), "%": ("ratio", Decimal("0.01")),
    # battery charge (base mAh)
    "mAh": ("charge", Decimal(1)), "Ah": ("charge", Decimal(1000)),
    # hardness scales are not interconvertible: each is its own dimension
    "HB": ("hardness_brinell", Decimal(1)), "HV": ("hardness_vickers", Decimal(1)),
    "HRC": ("hardness_rockwell_c", Decimal(1)), "ShoreA": ("hardness_shore_a", Decimal(1)),
    "ShoreD": ("hardness_shore_d", Decimal(1)),
}
_TEMPERATURE = {"C", "F", "K"}
BASE_UNITS = {"length": "m", "mass": "kg", "force": "N", "stress": "Pa", "energy": "J", "power": "W",
              "time": "s", "volume": "m3", "density": "kg/m3", "thermal_conductivity": "W/m.K",
              "impact_area": "J/m2", "ratio": "ratio", "charge": "mAh", "temperature": "K"}
_ALIASES = {"millimetre": "mm", "millimeter": "mm", "inch": "in", "inches": "in", "kilogram": "kg",
            "gram": "g", "grams": "g", "pound": "lb", "lbs": "lb", "°C": "C", "degC": "C", "°F": "F",
            "N/mm2": "MPa", "N/mm^2": "MPa", "kg/m^3": "kg/m3", "g/cc": "g/cm3", "W/mK": "W/m.K",
            "W/(m.K)": "W/m.K", "percent": "%", "hr": "h", "hours": "h", "years": "year", "yr": "year"}


def normalise_unit(unit: str) -> str:
    u = (unit or "").strip()
    u = _ALIASES.get(u, u)
    if u not in _LINEAR and u not in _TEMPERATURE:
        raise UnitError(f"Unknown unit '{unit}'.")
    return u


def dimension_of(unit: str) -> str:
    u = normalise_unit(unit)
    return "temperature" if u in _TEMPERATURE else _LINEAR[u][0]


def _to_decimal(value) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise UnitError(f"'{value}' is not a number.") from None
    if not d.is_finite():
        raise UnitError(f"'{value}' is not a finite number.")
    return d


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str

    def __init__(self, value, unit: str):
        object.__setattr__(self, "value", _to_decimal(value))
        object.__setattr__(self, "unit", normalise_unit(unit))

    @property
    def dimension(self) -> str:
        return dimension_of(self.unit)

    def to(self, unit: str) -> "Quantity":
        target = normalise_unit(unit)
        if dimension_of(target) != self.dimension:
            raise UnitError(f"Can't convert {self.unit} ({self.dimension}) to {target} ({dimension_of(target)}).")
        if self.dimension == "temperature":
            return Quantity(_temp_from_k(_temp_to_k(self.value, self.unit), target), target)
        base = self.value * _LINEAR[self.unit][1]
        return Quantity(base / _LINEAR[target][1], target)

    def base(self) -> Decimal:
        """Value in the dimension's base unit."""
        return self.to(BASE_UNITS[self.dimension]).value

    def _check(self, other: "Quantity") -> None:
        if not isinstance(other, Quantity):
            raise UnitError("Can only compare a Quantity with another Quantity.")
        if other.dimension != self.dimension:
            raise UnitError(f"Can't compare {self.unit} ({self.dimension}) with {other.unit} ({other.dimension}).")

    def __lt__(self, other): self._check(other); return self.base() < other.base()
    def __le__(self, other): self._check(other); return self.base() <= other.base()
    def __gt__(self, other): self._check(other); return self.base() > other.base()
    def __ge__(self, other): self._check(other); return self.base() >= other.base()

    def equals(self, other: "Quantity") -> bool:
        self._check(other)
        return self.base() == other.base()

    def __str__(self) -> str:
        return f"{format(self.value.normalize(), 'f')} {self.unit}"


def _temp_to_k(v: Decimal, u: str) -> Decimal:
    if u == "K":
        return v
    if u == "C":
        return v + Decimal("273.15")
    return (v - 32) * 5 / 9 + Decimal("273.15")


def _temp_from_k(k: Decimal, u: str) -> Decimal:
    if u == "K":
        return k
    if u == "C":
        return k - Decimal("273.15")
    return (k - Decimal("273.15")) * 9 / 5 + 32


@dataclass(frozen=True)
class Range:
    """A measured or typical range, such as a seat height of 420-520 mm."""
    low: Quantity
    high: Quantity

    def __post_init__(self):
        self.low._check(self.high)
        if self.low > self.high:
            raise UnitError(f"Range low {self.low} is above high {self.high}.")

    @classmethod
    def of(cls, low, high, unit: str) -> "Range":
        return cls(Quantity(low, unit), Quantity(high, unit))

    def contains(self, q: Quantity) -> bool:
        return self.low <= q <= self.high

    def mid(self) -> Quantity:
        return Quantity((self.low.value + self.high.to(self.low.unit).value) / 2, self.low.unit)

    def to(self, unit: str) -> "Range":
        return Range(self.low.to(unit), self.high.to(unit))


def parse_value(value, unit: str | None):
    """Turn a claim value into a Quantity or Range when it has a unit; leave other values alone.
    Accepts a number, a {"min": .., "max": ..} mapping or a [low, high] list."""
    if unit is None:
        return value
    if isinstance(value, dict) and {"min", "max"} <= set(value):
        return Range.of(value["min"], value["max"], unit)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return Range.of(value[0], value[1], unit)
    return Quantity(value, unit)
