"""Review intelligence: positive and negative experiences, complaints, reliability and review confidence.

The agent tags each review's aspects ({"aspect": "cushion", "category": "durability", "sentiment":
"negative", "severity": 1-5, "quote": "..."}); this module aggregates them deterministically.
Rules:
- identical review texts count once
- every complaint share states its denominator (unique reviews analysed)
- authenticity is reported as warning signs, never as "these reviews are fake"
- sentiment is subjective evidence; it never stands in for engineering tests
"""
from __future__ import annotations

import datetime as dt
import re

from ..core.evidence import Claim, Status
from ..scoring.confidence import claim_confidence, sample_factor
from ..scoring.criteria import Criterion

CATEGORIES = ("defect", "failure", "durability", "comfort", "fit", "quality", "performance", "service",
              "design", "assembly", "value", "safety", "other")
FAILURE = {"defect", "failure"}
GENERIC = re.compile(r"^(great|good|nice|excellent|awesome|perfect|love it|amazing|best)( product| item| quality)?[.! ]*$", re.I)


def _norm(t: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", (t or "").lower()))


def unique_reviews(reviews: list) -> tuple:
    """Drop exact duplicate texts (keeping the first). Empty texts are kept: they can't be compared."""
    seen, out, dupes = set(), [], 0
    for r in reviews:
        key = _norm(r.text)
        if key and key in seen:
            dupes += 1
            continue
        if key:
            seen.add(key)
        out.append(r)
    return out, dupes


def _shingles(t: str, k: int = 3) -> set:
    w = t.split()
    return {" ".join(w[i:i + k]) for i in range(max(len(w) - k + 1, 0))}


def authenticity(reviews: list, duplicates: int) -> dict:
    """Heuristic warning signs. Returns level low/medium/high with the reasons."""
    n = len(reviews) + duplicates
    signals, points = [], 0
    if n == 0:
        return {"level": "unknown", "signals": [], "points": 0}
    ratings = [r.rating for r in reviews]
    five = ratings.count(5) / len(ratings) * 100
    if five >= 85 and n >= 10:
        signals.append(f"{five:.0f}% of unique reviews are 5-star.")
        points += 2
    if duplicates:
        signals.append(f"{duplicates} review(s) repeat another review's exact text (counted once).")
        points += 2 if duplicates >= 3 else 1
    short = sum(1 for r in reviews if len(r.text.split()) < 6 or GENERIC.match(r.text or "")) / len(reviews) * 100
    if short >= 40 and n >= 10:
        signals.append(f"{short:.0f}% are very short or generic.")
        points += 1
    flagged = [r.verified for r in reviews if r.verified is not None]
    if flagged and flagged.count(False) / len(flagged) >= 0.3:
        signals.append(f"{flagged.count(False) / len(flagged) * 100:.0f}% aren't marked as verified purchases.")
        points += 1
    dates = sorted(r.date for r in reviews if r.date)
    if len(dates) >= 10:
        best = max(sum(1 for d2 in dates if 0 <= (d2 - d).days <= 7) for d in dates)
        if best / len(dates) >= 0.4:
            signals.append(f"{best} of {len(dates)} dated reviews arrived within one week.")
            points += 2
    sh = [_shingles(_norm(r.text)) for r in reviews if len(r.text.split()) >= 6]
    near = sum(1 for i in range(len(sh)) for j in range(i + 1, len(sh))
               if sh[i] and sh[j] and len(sh[i] & sh[j]) / len(sh[i] | sh[j]) >= 0.5)
    if near:
        signals.append(f"{near} pair(s) of reviews share much of their wording.")
        points += 2 if near >= 2 else 1
    level = "low" if points <= 1 else "medium" if points <= 3 else "high"
    return {"level": level, "signals": signals, "points": points}


def analyse(product) -> dict:
    """Aggregate a product's reviews into an explainable summary."""
    reviews, dupes = unique_reviews(product.reviews)
    n = len(reviews)
    summary = {"analysed": n, "duplicates_removed": dupes, "aspects": {}, "positive": 0, "negative": 0, "neutral": 0,
               "authenticity": authenticity(reviews, dupes), "long_term": {"reports": 0, "positive": 0},
               "safety_complaints": []}
    for r in reviews:
        bucket = "positive" if r.rating >= 4 else "negative" if r.rating <= 2 else "neutral"
        summary[bucket] += 1
        months = None
        for a in r.aspects:
            cat = str(a.get("category", "other")).lower()
            cat = cat if cat in CATEGORIES else "other"
            name = str(a.get("aspect") or cat)
            sent = str(a.get("sentiment", "neutral")).lower()
            sev = int(a.get("severity", 3)) if sent == "negative" else 0
            entry = summary["aspects"].setdefault(name, {"category": cat, "mentions": 0, "negative": 0,
                                                        "positive": 0, "severity_total": 0, "quotes": []})
            entry["mentions"] += 1
            if sent == "negative":
                entry["negative"] += 1
                entry["severity_total"] += sev
                if cat == "safety" and sev >= 4:
                    summary["safety_complaints"].append(str(a.get("quote") or name))
            elif sent == "positive":
                entry["positive"] += 1
            if a.get("quote") and len(entry["quotes"]) < 3:
                entry["quotes"].append(str(a["quote"]))
            if a.get("ownership_months") is not None:
                months = a["ownership_months"]
        if months is not None and float(months) >= 6:
            summary["long_term"]["reports"] += 1
            summary["long_term"]["positive"] += 1 if r.rating >= 4 else 0
    for e in summary["aspects"].values():
        e["share_of_reviews"] = round(e["mentions"] / n * 100, 1) if n else 0.0
        e["negative_share_of_reviews"] = round(e["negative"] / n * 100, 1) if n else 0.0
    return summary


def _review_confidence(product, ctx, n: int, level: str) -> float:
    src = ctx.request.sources.get(product.review_source)
    if src is None:
        return 0.0
    pseudo = Claim(id="reviews", claim_type="reviews", status=Status.CUSTOMER_REPORTED, value=n,
                   source_id=src.id, observed_at=None)
    base = claim_confidence(pseudo, src, ctx.as_of, ctx.coeffs)["confidence"]
    factor = {"low": 1.0, "medium": 0.75, "high": 0.5}.get(level, 0.8)
    return base * sample_factor(n) * factor


def criteria(product, ctx) -> list:
    if not product.reviews:
        return []
    s = analyse(product)
    ctx.notes.setdefault("_reviews", {})[product.id] = s
    n = s["analysed"]
    if n < 5:
        ctx.note(product.id, f"Only {n} unique reviews: too few to score customer experience.")
        return []
    conf = _review_confidence(product, ctx, n, s["authenticity"]["level"])
    basis = f"{n} unique reviews ({s['duplicates_removed']} duplicates removed)"
    out = [Criterion("customer_experience", "positive experience", s["positive"] / n * 100, conf, 1.0, (),
                     f"{s['positive']} of {basis} are 4-5 stars", "reviews")]
    # Negative issue index: severity-weighted share of reviews reporting a problem.
    burden = 0.0
    for r in unique_reviews(product.reviews)[0]:
        sev = max([int(a.get("severity", 3)) for a in r.aspects if str(a.get("sentiment")) == "negative"] or
                  ([3] if r.rating <= 2 else [0]))
        burden += sev / 5
    out.append(Criterion("customer_experience", "problems reported", 100 * (1 - burden / n), conf, 1.0, (),
                         f"severity-weighted problem rate across {basis}", "reviews"))
    fails = sum(1 for r in unique_reviews(product.reviews)[0]
                if any(str(a.get("category")).lower() in FAILURE and str(a.get("sentiment")) == "negative" for a in r.aspects))
    out.append(Criterion("reliability", "reported defects and failures", 100 * max(0.0, 1 - 2 * fails / n), conf, 1.0, (),
                         f"{fails} of {n} unique reviews report a defect or failure (this is a complaint rate, "
                         "not a population failure rate)", "reviews"))
    lt = s["long_term"]
    if lt["reports"] >= 3:
        out.append(Criterion("durability", "long-term owner reports", lt["positive"] / lt["reports"] * 100, conf * 0.9, 1.0, (),
                             f"{lt['positive']} of {lt['reports']} reviews after 6+ months of ownership are positive", "reviews"))
    for dim, cats, label in (("aesthetics", {"design"}, "design opinions"), ("after_sales_service", {"service"}, "service experiences"),
                             ("ergonomics", {"comfort", "fit"}, "reported comfort and fit (subjective)")):
        pos = neg = 0
        for e in s["aspects"].values():
            if e["category"] in cats:
                pos += e["positive"]
                neg += e["negative"]
        if pos + neg >= 3:
            out.append(Criterion(dim, label, pos / (pos + neg) * 100, conf * 0.8, 0.5, (),
                                 f"{pos} positive vs {neg} negative mentions", "reviews"))
    if s["safety_complaints"]:
        ctx.note(product.id, f"{len(s['safety_complaints'])} serious safety complaint(s) in reviews need checking: "
                             + "; ".join(s["safety_complaints"][:3]))
    return out
