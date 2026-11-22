"""Evidence: where every value comes from, and how much it can be trusted.

Rules enforced here (docs/ARCHITECTURE.md, ADR-4):
- every claim has a status; UNKNOWN is explicit and carries no value
- every non-UNKNOWN claim points to a source
- VERIFIED / INDEPENDENTLY_TESTED need an independent source, so a manufacturer's own page or a
  certification logo on a listing can never be "verified"
- an AI-written summary is never a source
- raw evidence items are immutable and carry a content hash
"""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from enum import Enum

from .errors import EvidenceError


class Status(str, Enum):
    VERIFIED = "VERIFIED"                            # confirmed by an independent primary source (registry, government record)
    INDEPENDENTLY_TESTED = "INDEPENDENTLY_TESTED"    # measured by an independent lab or reviewer with a stated method
    MANUFACTURER_REPORTED = "MANUFACTURER_REPORTED"  # the brand or seller says so
    CUSTOMER_REPORTED = "CUSTOMER_REPORTED"          # owners say so (reviews, forums)
    ESTIMATED = "ESTIMATED"                          # inferred with an explicit method
    UNKNOWN = "UNKNOWN"                              # couldn't be established


class SourceType(str, Enum):
    INDEPENDENT_LAB = "independent_lab"
    GOVERNMENT_RECORD = "government_record"          # recall databases, certification registries
    STANDARDS_BODY = "standards_body"
    EXPERT_REVIEW = "expert_review"                  # professional reviewers with test methods
    MANUFACTURER = "manufacturer"                    # brand site, manual, datasheet
    MARKETPLACE_LISTING = "marketplace_listing"
    CUSTOMER_REVIEWS = "customer_reviews"
    FORUM = "forum"                                  # owner communities, repair forums
    REFERENCE_DATA = "reference_data"                # general engineering reference ranges
    USER_PROVIDED = "user_provided"                  # the user told us (their measurements, their receipt)
    MODEL = "model"                                  # an engine calculation from other evidence


class Independence(str, Enum):
    INDEPENDENT = "independent"
    MANUFACTURER = "manufacturer"
    SELLER = "seller"
    AFFILIATED = "affiliated"                        # sponsored or affiliate-funded
    UNKNOWN = "unknown"


# Banned: summaries written by an AI are explanations, not evidence.
BANNED_SOURCE_TYPES = {"agent_summary", "ai_summary", "llm"}
INDEPENDENT_STATUSES = {Status.VERIFIED, Status.INDEPENDENTLY_TESTED}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_date(value) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        raise EvidenceError(f"'{value}' is not a date like 2026-11-22.") from None


@dataclass(frozen=True)
class EvidenceSource:
    id: str
    name: str
    type: SourceType
    independence: Independence = Independence.UNKNOWN
    url: str = ""
    published_at: dt.date | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceSource":
        t = str(d.get("type", "")).strip().lower()
        if t in BANNED_SOURCE_TYPES:
            raise EvidenceError(f"Source '{d.get('id')}': an AI-written summary can't be used as evidence.")
        try:
            stype = SourceType(t)
        except ValueError:
            raise EvidenceError(f"Source '{d.get('id')}': unknown type '{t}'. Use one of "
                                f"{', '.join(s.value for s in SourceType)}.") from None
        indep = d.get("independence")
        if indep is None:
            indep = {SourceType.MANUFACTURER: "manufacturer", SourceType.MARKETPLACE_LISTING: "seller",
                     SourceType.INDEPENDENT_LAB: "independent", SourceType.GOVERNMENT_RECORD: "independent",
                     SourceType.STANDARDS_BODY: "independent", SourceType.USER_PROVIDED: "independent",
                     SourceType.MODEL: "independent", SourceType.REFERENCE_DATA: "independent"}.get(stype, "unknown")
        try:
            independence = Independence(str(indep).lower())
        except ValueError:
            raise EvidenceError(f"Source '{d.get('id')}': unknown independence '{indep}'.") from None
        url = str(d.get("url") or "")
        if url and not url.lower().startswith(("http://", "https://")):
            raise EvidenceError(f"Source '{d.get('id')}': url must start with http:// or https://.")
        if not str(d.get("id") or "").strip():
            raise EvidenceError("Every source needs an id.")
        return cls(id=str(d["id"]), name=str(d.get("name") or d["id"]), type=stype, independence=independence,
                   url=url, published_at=parse_date(d.get("published_at")))


@dataclass(frozen=True)
class EvidenceItem:
    """A piece of raw material as collected (a spec table, a review, a recall notice). Never edited."""
    source_id: str
    content: str
    collected_at: str = field(default_factory=utc_now)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Claim:
    """One structured fact extracted from evidence, about one product variant."""
    id: str
    claim_type: str
    status: Status
    value: object = None
    unit: str | None = None
    source_id: str | None = None
    observed_at: dt.date | None = None
    variant_match: str = "exact"          # exact | other_variant | product_family | brand
    limitations: tuple = ()
    quote: str = ""                       # the exact text the claim was taken from, when there is one

    def is_known(self) -> bool:
        return self.status is not Status.UNKNOWN


VARIANT_MATCHES = ("exact", "other_variant", "product_family", "brand")


def make_claim(d: dict, sources: dict, default_id: str) -> Claim:
    """Build a Claim from agent-supplied JSON and check every provenance rule."""
    cid = str(d.get("id") or default_id)
    ctype = str(d.get("claim_type") or "").strip()
    if not ctype:
        raise EvidenceError(f"Claim {cid}: needs a claim_type.")
    raw_status = str(d.get("status") or "").strip().upper()
    try:
        status = Status(raw_status)
    except ValueError:
        raise EvidenceError(f"Claim {cid} ({ctype}): status must be one of "
                            f"{', '.join(s.value for s in Status)}.") from None
    value = d.get("value")
    src_id = d.get("source")
    if status is Status.UNKNOWN:
        if value not in (None, ""):
            raise EvidenceError(f"Claim {cid} ({ctype}): an UNKNOWN claim can't have a value.")
    else:
        if value in (None, ""):
            raise EvidenceError(f"Claim {cid} ({ctype}): a {status.value} claim needs a value (or use UNKNOWN).")
        if not src_id:
            raise EvidenceError(f"Claim {cid} ({ctype}): a {status.value} claim needs a source.")
    source = None
    if src_id is not None:
        source = sources.get(src_id)
        if source is None:
            raise EvidenceError(f"Claim {cid} ({ctype}): source '{src_id}' isn't in the sources list.")
    if status in INDEPENDENT_STATUSES and source.independence is not Independence.INDEPENDENT:
        raise EvidenceError(f"Claim {cid} ({ctype}): {status.value} needs an independent source, but "
                            f"'{source.name}' is {source.independence.value}. Use MANUFACTURER_REPORTED instead.")
    if status is Status.CUSTOMER_REPORTED and source.type not in (SourceType.CUSTOMER_REVIEWS, SourceType.FORUM,
                                                                     SourceType.USER_PROVIDED):
        raise EvidenceError(f"Claim {cid} ({ctype}): CUSTOMER_REPORTED needs a customer review, forum or user source.")
    match = str(d.get("variant_match") or "exact")
    if match not in VARIANT_MATCHES:
        raise EvidenceError(f"Claim {cid}: variant_match must be one of {', '.join(VARIANT_MATCHES)}.")
    lim = d.get("limitations") or ()
    if isinstance(lim, str):
        lim = (lim,)
    return Claim(id=cid, claim_type=ctype, status=status, value=value, unit=d.get("unit"),
                 source_id=src_id, observed_at=parse_date(d.get("observed_at")), variant_match=match,
                 limitations=tuple(str(x) for x in lim), quote=str(d.get("quote") or ""))
