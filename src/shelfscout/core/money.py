"""Money in any ISO 4217 currency, with currency-correct rounding and sourced exchange rates.

Amounts in different currencies never mix silently: converting needs an FxRate that records where
the rate came from and when.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .errors import CurrencyError

# ISO 4217 minor units for currencies that don't use 2 decimal places. Everything else uses 2.
MINOR_UNITS = {
    **{c: 0 for c in ("BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX",
                      "UYI", "VND", "VUV", "XAF", "XOF", "XPF")},
    **{c: 3 for c in ("BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND")},
    "CLF": 4, "UYW": 4,
}
SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥", "AUD": "A$", "CAD": "C$",
           "CNY": "¥", "KRW": "₩", "BRL": "R$", "MXN": "MX$", "SGD": "S$", "NZD": "NZ$", "CHF": "CHF ",
           "AED": "AED ", "SAR": "SAR ", "ZAR": "R", "PHP": "₱", "NGN": "₦", "IDR": "Rp", "THB": "฿"}
_CODE = re.compile(r"^[A-Z]{3}$")


def currency_code(code: str) -> str:
    c = (code or "").strip().upper()
    if not _CODE.match(c):
        raise CurrencyError(f"'{code}' isn't an ISO 4217 currency code (three letters, like USD).")
    return c


def minor_units(code: str) -> int:
    return MINOR_UNITS.get(currency_code(code), 2)


def _dec(v, what="amount") -> Decimal:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise CurrencyError(f"{what} '{v}' is not a number.") from None
    if not d.is_finite():
        raise CurrencyError(f"{what} '{v}' is not a finite number.")
    return d


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __init__(self, amount, currency: str):
        object.__setattr__(self, "currency", currency_code(currency))
        object.__setattr__(self, "amount", _dec(amount))

    def rounded(self) -> "Money":
        q = Decimal(1).scaleb(-minor_units(self.currency))
        return Money(self.amount.quantize(q, rounding=ROUND_HALF_UP), self.currency)

    def _same(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise CurrencyError("Can only combine Money with Money.")
        if other.currency != self.currency:
            raise CurrencyError(f"Can't combine {self.currency} and {other.currency} without an exchange rate.")

    def __add__(self, other): self._same(other); return Money(self.amount + other.amount, self.currency)
    def __sub__(self, other): self._same(other); return Money(self.amount - other.amount, self.currency)
    def __lt__(self, other): self._same(other); return self.amount < other.amount
    def __le__(self, other): self._same(other); return self.amount <= other.amount
    def __gt__(self, other): self._same(other); return self.amount > other.amount
    def __ge__(self, other): self._same(other); return self.amount >= other.amount

    def times(self, factor) -> "Money":
        return Money(self.amount * _dec(factor, "factor"), self.currency)

    def convert(self, rate: "FxRate") -> "Money":
        if rate.base != self.currency:
            raise CurrencyError(f"Rate is for {rate.base}->{rate.quote}, but the amount is in {self.currency}.")
        return Money(self.amount * rate.rate, rate.quote).rounded()

    def format(self) -> str:
        r = self.rounded()
        places = minor_units(self.currency)
        text = f"{abs(r.amount):,.{places}f}"
        sign = "-" if r.amount < 0 else ""
        sym = SYMBOLS.get(self.currency)
        return f"{sign}{sym}{text}" if sym else f"{sign}{text} {self.currency}"

    def __str__(self) -> str:
        return self.format()


@dataclass(frozen=True)
class FxRate:
    """1 unit of base = rate units of quote, observed from a named source on a date."""
    base: str
    quote: str
    rate: Decimal
    source: str
    as_of: dt.date

    def __init__(self, base: str, quote: str, rate, source: str, as_of):
        object.__setattr__(self, "base", currency_code(base))
        object.__setattr__(self, "quote", currency_code(quote))
        r = _dec(rate, "rate")
        if r <= 0:
            raise CurrencyError("An exchange rate must be positive.")
        object.__setattr__(self, "rate", r)
        if not (source or "").strip():
            raise CurrencyError("An exchange rate needs a source (where the rate came from).")
        object.__setattr__(self, "source", source.strip())
        if isinstance(as_of, str):
            try:
                as_of = dt.date.fromisoformat(as_of[:10])
            except ValueError:
                raise CurrencyError(f"as_of '{as_of}' must be a date like 2026-11-22.") from None
        object.__setattr__(self, "as_of", as_of)

    def age_days(self, today: dt.date | None = None) -> int:
        return ((today or dt.date.today()) - self.as_of).days
