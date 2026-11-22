"""Product, listing and evaluation-request models, built from the JSON the agent writes.

The evaluation request ("bundle") format is documented in skills/evaluate.md and docs/DATA_FORMAT.md.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from .errors import ValidationError
from .evidence import Claim, EvidenceSource, make_claim, parse_date
from .money import Money, currency_code


def new_id() -> str:
    return str(uuid.uuid4())


_GTIN = re.compile(r"^\d{8}$|^\d{12,14}$")


@dataclass(frozen=True)
class Listing:
    marketplace: str
    price: Money
    shipping: Money
    url: str = ""
    seller: str = ""
    observed_at: object = None
    condition: str = "new"
    source_id: str | None = None

    def total(self) -> Money:
        return (self.price + self.shipping).rounded()


@dataclass
class Review:
    rating: int
    text: str = ""
    date: object = None
    verified: bool | None = None
    aspects: list = field(default_factory=list)   # [{"aspect": "cushion", "sentiment": "negative", "severity": 3, "quote": ".."}]


@dataclass
class SafetyRecord:
    requirement_id: str
    outcome: str            # pass | fail | unknown | not_applicable
    claim_id: str | None = None
    note: str = ""


@dataclass
class Product:
    id: str
    name: str
    brand: str = ""
    model_number: str = ""
    gtin: str = ""
    variant: dict = field(default_factory=dict)     # {"size": "M", "storage": "256GB", "colour": "black"}
    listing: Listing | None = None
    claims: list = field(default_factory=list)       # list[Claim]
    reviews: list = field(default_factory=list)      # list[Review]
    review_source: str | None = None
    safety: list = field(default_factory=list)       # list[SafetyRecord]
    criteria: list = field(default_factory=list)     # agent-rated criteria, see scoring.dimensions
    recalls: list = field(default_factory=list)      # [{"id": "...", "status": "active|closed", "source": "s9"}]

    def claims_of(self, prefix: str) -> list:
        return [c for c in self.claims if c.claim_type == prefix or c.claim_type.startswith(prefix + ".")]

    def claim(self, claim_type: str) -> Claim | None:
        known = [c for c in self.claims if c.claim_type == claim_type and c.is_known()]
        rank = {"exact": 0, "other_variant": 1, "product_family": 2, "brand": 3}
        return sorted(known, key=lambda c: rank.get(c.variant_match, 9))[0] if known else None


@dataclass
class Request:
    category: str
    country: str
    currency: str
    sources: dict
    products: list
    budget_min: Money | None = None
    budget_max: Money | None = None
    priorities: dict = field(default_factory=dict)
    user: dict = field(default_factory=dict)          # body measurements, must-have features, use case
    as_of: object = None


def _money(v, cur, what):
    try:
        return Money(v, cur)
    except Exception as e:  # noqa: BLE001 - re-raised with context
        raise ValidationError(f"{what}: {e}") from None


def parse_request(data: dict) -> Request:
    if not isinstance(data, dict):
        raise ValidationError("The evaluation request must be a JSON object.")
    category = str(data.get("category") or "").strip()
    if not category:
        raise ValidationError("The request needs a 'category' (for example 'office_chair').")
    market = data.get("market") or {}
    currency = currency_code(market.get("currency") or "USD")
    country = str(market.get("country") or "").upper()
    sources = {}
    for s in data.get("sources") or []:
        src = EvidenceSource.from_dict(s)
        if src.id in sources:
            raise ValidationError(f"Source id '{src.id}' is used twice.")
        sources[src.id] = src
    products, seen = [], set()
    for i, p in enumerate(data.get("products") or [], 1):
        pid = str(p.get("id") or f"p{i}")
        if pid in seen:
            raise ValidationError(f"Product id '{pid}' is used twice.")
        seen.add(pid)
        name = str(p.get("name") or "").strip()
        if not name:
            raise ValidationError(f"Product {pid} needs a name.")
        gtin = str(p.get("gtin") or "").strip()
        if gtin and not _GTIN.match(gtin):
            raise ValidationError(f"Product {pid}: gtin '{gtin}' should be 8, 12, 13 or 14 digits.")
        listing = None
        if p.get("listing"):
            l = p["listing"]
            lcur = l.get("currency") or currency
            if currency_code(lcur) != currency:
                raise ValidationError(f"Product {pid}: listing is in {lcur} but the market currency is {currency}. "
                                      "Convert it first (with a dated exchange rate) or change the market.")
            if l.get("price") is None:
                raise ValidationError(f"Product {pid}: listing needs a price.")
            src = l.get("source")
            if src is not None and src not in sources:
                raise ValidationError(f"Product {pid}: listing source '{src}' isn't in the sources list.")
            listing = Listing(marketplace=str(l.get("marketplace") or ""), price=_money(l["price"], lcur, f"{pid} price"),
                              shipping=_money(l.get("shipping", 0), lcur, f"{pid} shipping"), url=str(l.get("url") or ""),
                              seller=str(l.get("seller") or ""), observed_at=parse_date(l.get("observed_at")),
                              condition=str(l.get("condition") or "new"), source_id=src)
        claims = [make_claim(c, sources, f"{pid}-c{j}") for j, c in enumerate(p.get("claims") or [], 1)]
        ids = [c.id for c in claims]
        if len(set(ids)) != len(ids):
            raise ValidationError(f"Product {pid}: claim ids must be unique.")
        rv = p.get("reviews") or {}
        rsrc = rv.get("source") if isinstance(rv, dict) else None
        items = rv.get("items", []) if isinstance(rv, dict) else rv
        if items and rsrc is None:
            raise ValidationError(f"Product {pid}: reviews need a 'source' (where they were collected).")
        if rsrc is not None and rsrc not in sources:
            raise ValidationError(f"Product {pid}: review source '{rsrc}' isn't in the sources list.")
        reviews = []
        for k, r in enumerate(items, 1):
            try:
                rating = int(r["rating"])
            except (KeyError, TypeError, ValueError):
                raise ValidationError(f"Product {pid} review {k}: needs a rating 1-5.") from None
            if not 1 <= rating <= 5:
                raise ValidationError(f"Product {pid} review {k}: rating must be 1-5.")
            reviews.append(Review(rating=rating, text=str(r.get("text") or ""), date=parse_date(r.get("date")),
                                  verified=r.get("verified"), aspects=list(r.get("aspects") or [])))
        safety = [SafetyRecord(requirement_id=str(s["requirement"]), outcome=str(s.get("outcome", "unknown")).lower(),
                               claim_id=s.get("claim"), note=str(s.get("note") or ""))
                  for s in (p.get("safety") or [])]
        for s in safety:
            if s.outcome not in ("pass", "fail", "unknown", "not_applicable"):
                raise ValidationError(f"Product {pid}: safety outcome must be pass, fail, unknown or not_applicable.")
            if s.outcome in ("pass", "fail") and not s.claim_id:
                raise ValidationError(f"Product {pid}: a safety {s.outcome} for '{s.requirement_id}' needs the claim id "
                                      "that shows it.")
            if s.claim_id and s.claim_id not in ids:
                raise ValidationError(f"Product {pid}: safety record points to claim '{s.claim_id}', which doesn't exist.")
        products.append(Product(id=pid, name=name, brand=str(p.get("brand") or ""),
                                model_number=str(p.get("model_number") or ""), gtin=gtin,
                                variant=dict(p.get("variant") or {}), listing=listing, claims=claims,
                                reviews=reviews, review_source=rsrc, safety=safety,
                                criteria=list(p.get("criteria") or []), recalls=list(p.get("recalls") or [])))
    if not products:
        raise ValidationError("The request has no products.")
    user = data.get("user") or {}
    budget = user.get("budget") or {}
    bmin = _money(budget["min"], currency, "budget min") if budget.get("min") is not None else None
    bmax = _money(budget["max"], currency, "budget max") if budget.get("max") is not None else None
    if bmin and bmax and bmin > bmax:
        raise ValidationError("Budget min is above budget max.")
    return Request(category=category, country=country, currency=currency, sources=sources, products=products,
                   budget_min=bmin, budget_max=bmax, priorities=dict(user.get("priorities") or {}), user=dict(user),
                   as_of=parse_date(data.get("as_of")))
