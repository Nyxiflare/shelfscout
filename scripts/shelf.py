#!/usr/bin/env python3
"""
shelf.py - ShelfScout's calculators. Claude does the research and judgement; this does the math,
so totals, margins and review signals are exact and repeatable.

Commands
  landed  --price 49.99 [--shipping 5] [--tax-pct 8.25] [--duty-pct 0] [--fees 0] [--currency USD]
          total cost to the buyer's door
  unit    --price 12.99 --qty 24 [--unit-name can] [--per 1]        price per unit, for fair comparisons
  deal    --price 79 [--was 129] [--history history.json]            is the discount real?
  reviews FILE.json                                                  heuristic signals of unreliable reviews
  compare FILE.json [--weights fit=40,value=25,trust=20,reviews=15] [--html out.html]
          rank listings for a shopper (needs fit scores from Claude)
  margin  --sell 29.99 --cost 6.50 [--inbound 1.20] [--marketplace amazon-us] [--referral-pct N]
          [--fixed-fee N] [--fulfil 5.40] [--ads-pct 10] [--returns-pct 5] [--other 0]
          seller profit per unit after fees, ads and returns
  fees    list the fee presets and when they were last checked

Input files are JSON; see the SKILL.md "Data formats" section. Standard library only, no network.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import statistics
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥", "AUD": "A$", "CAD": "C$"}
ZERO_DECIMAL = {"JPY", "KRW", "VND"}

# Typical published seller fees. They change: SKILL.md tells Claude to check the marketplace's current
# fee page before quoting final numbers, and to override with --referral-pct / --fixed-fee.
FEES_CHECKED = ("typical published rates written into this script in Nov 2026, not checked live; "
                "confirm on the marketplace's current fee page before relying on them")
FEE_PRESETS = {
    "amazon-us": {"referral_pct": "15", "fixed": "0", "note": "Referral fee for most categories (8-17% depending on category, minimums apply). FBA fulfilment fee is separate: pass --fulfil."},
    "ebay-us": {"referral_pct": "13.6", "fixed": "0.40", "note": "Final value fee for most categories plus a per-order fee; varies by category and store level."},
    "etsy": {"referral_pct": "9.5", "fixed": "0.45", "note": "6.5% transaction + ~3% payment processing (US), $0.20 listing + $0.25 processing fixed; offsite-ads fee not included."},
    "walmart-us": {"referral_pct": "15", "fixed": "0", "note": "Referral fee for most categories (6-15%). WFS fulfilment is separate: pass --fulfil."},
    "shopify": {"referral_pct": "2.9", "fixed": "0.30", "note": "Card processing on a basic plan; the monthly plan cost is not included."},
}


def fail(msg: str):
    raise SystemExit(msg)


def out(s: str = "") -> None:
    print(s, flush=True)


def dec(v, name: str, positive: bool = False) -> Decimal:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        fail(f"{name} must be a number, got '{v}'.")
    if not d.is_finite() or d < 0 or (positive and d == 0):
        fail(f"{name} must be a {'positive' if positive else 'non-negative'} number, got '{v}'.")
    return d


def money(v: Decimal, cur: str) -> str:
    cur = cur.upper()
    q = v.quantize(Decimal("1") if cur in ZERO_DECIMAL else Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    text = f"{abs(q):,}"
    sym = SYMBOLS.get(cur)
    return f"{sign}{sym}{text}" if sym else f"{sign}{text} {cur}"


def plain(v: Decimal) -> str:
    """A quantity without scientific notation or trailing zeros: 100, 2.5, 0.75."""
    return format(v.normalize(), "f")


def pct(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def load_json(path: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        fail(f"File not found: {path}")
    except json.JSONDecodeError as e:
        fail(f"{path} is not valid JSON (line {e.lineno}): {e.msg}")


# --------------------------------------------------------------------------- landed cost

def landed_cost(price, shipping=0, tax_pct=0, duty_pct=0, fees=0) -> dict:
    price, shipping = dec(price, "--price"), dec(shipping, "--shipping")
    tax_pct, duty_pct, fees = dec(tax_pct, "--tax-pct"), dec(duty_pct, "--duty-pct"), dec(fees, "--fees")
    duty = (price + shipping) * duty_pct / 100
    tax = (price + shipping + duty) * tax_pct / 100
    total = price + shipping + duty + tax + fees
    return {"price": price, "shipping": shipping, "duty": duty, "tax": tax, "fees": fees, "total": total}


def cmd_landed(a) -> int:
    r = landed_cost(a.price, a.shipping, a.tax_pct, a.duty_pct, a.fees)
    c = a.currency
    out(f"Item {money(r['price'], c)} + shipping {money(r['shipping'], c)}"
        + (f" + import duty {money(r['duty'], c)}" if r["duty"] else "")
        + (f" + tax {money(r['tax'], c)}" if r["tax"] else "")
        + (f" + other fees {money(r['fees'], c)}" if r["fees"] else ""))
    out(f"Total to your door: {money(r['total'], c)}")
    return 0


# --------------------------------------------------------------------------- unit price

def cmd_unit(a) -> int:
    price, qty, per = dec(a.price, "--price"), dec(a.qty, "--qty", positive=True), dec(a.per, "--per", positive=True)
    each = price / qty * per
    label = f"per {plain(per)} {a.unit_name}" if per != 1 else f"per {a.unit_name}"
    out(f"{money(each, a.currency)} {label}  ({money(price, a.currency)} for {plain(qty)})")
    return 0


# --------------------------------------------------------------------------- deal check

def deal_check(price, was=None, history=None) -> dict:
    """Compare the current price with the claimed 'was' price and with prices actually observed."""
    price = dec(price, "--price", positive=True)
    res = {"price": price, "flags": [], "verdict": "unknown"}
    if was is not None:
        was = dec(was, "--was", positive=True)
        res["claimed_discount_pct"] = (was - price) / was * 100
    points = []
    for h in history or []:
        try:
            points.append((dt.date.fromisoformat(str(h["date"])), dec(h["price"], "history price", positive=True)))
        except (KeyError, ValueError):
            fail("History entries need a 'date' (YYYY-MM-DD) and a 'price'.")
    points.sort()
    if points:
        prices = [p for _, p in points]
        median = Decimal(str(statistics.median(prices)))
        low = min(prices)
        res.update(median=median, low=low, observations=len(points),
                   span_days=(points[-1][0] - points[0][0]).days,
                   vs_median_pct=(median - price) / median * 100)
        if was is not None and not any(abs(p - was) / was <= Decimal("0.02") for p in prices):
            res["flags"].append("The claimed 'was' price never appears in the observed history.")
        if price > low:
            res["flags"].append(f"It has been cheaper before ({low}).")
        if res["span_days"] < 30:
            res["flags"].append("Less than 30 days of history: treat the verdict as weak.")
        if price <= low:
            res["verdict"] = "good: at or below the lowest observed price"
        elif res["vs_median_pct"] >= 10:
            res["verdict"] = "fair: clearly below the usual price"
        elif res["vs_median_pct"] >= 0:
            res["verdict"] = "weak: close to the usual price"
        else:
            res["verdict"] = "poor: above the usual price"
        if was is not None:
            seen = any(abs(p - was) / was <= Decimal("0.02") for p in prices)
            res["claim"] = ("supported: the 'was' price was actually charged" if seen else
                            "not supported: the 'was' price was never charged in the observed history")
    elif was is not None:
        res["flags"].append("No price history: the 'was' price can't be checked.")
        res["claim"] = "unverifiable: no price history"
    return res


def cmd_deal(a) -> int:
    hist = load_json(a.history) if a.history else None
    if hist is not None and not isinstance(hist, list):
        fail("--history should be a JSON list of {\"date\": ..., \"price\": ...}.")
    r = deal_check(a.price, a.was, hist)
    c = a.currency
    out(f"Current price: {money(r['price'], c)}")
    if "claimed_discount_pct" in r:
        out(f"Claimed discount: {pct(r['claimed_discount_pct'])} off {money(dec(a.was, '--was'), c)}")
    if "median" in r:
        out(f"Observed: {r['observations']} prices over {r['span_days']} days, usual {money(r['median'], c)}, "
            f"lowest {money(r['low'], c)}. Current is {pct(r['vs_median_pct'])} below the usual price.")
    out(f"Price verdict: {r['verdict']}")
    if "claim" in r:
        real = f"; the real saving vs. the usual price is {pct(r['vs_median_pct'])}" if "vs_median_pct" in r else ""
        out(f"Discount claim: {r['claim']}{real}")
    for f in r["flags"]:
        out(f"  ! {f}")
    return 0


# --------------------------------------------------------------------------- review signals

GENERIC = re.compile(r"^(great|good|nice|excellent|awesome|perfect|love it|amazing|best)( product| item| quality)?[.! ]*$", re.I)


def _shingles(text: str, k: int = 3) -> set:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {" ".join(words[i:i + k]) for i in range(max(len(words) - k + 1, 0))}


def review_signals(reviews: list) -> dict:
    """Heuristic signs that a review set is unreliable. These are warning signs, not proof of fakes."""
    if not reviews:
        fail("No reviews in the file.")
    ratings, dates, texts, verified = [], [], [], []
    for i, r in enumerate(reviews):
        try:
            ratings.append(int(r["rating"]))
        except (KeyError, ValueError, TypeError):
            fail(f"Review {i + 1} needs a 'rating' from 1 to 5.")
        if not 1 <= ratings[-1] <= 5:
            fail(f"Review {i + 1} rating must be 1-5.")
        if r.get("date"):
            try:
                dates.append(dt.date.fromisoformat(str(r["date"])))
            except ValueError:
                fail(f"Review {i + 1} date must be YYYY-MM-DD.")
        texts.append(str(r.get("text", "")).strip())
        if "verified" in r:
            verified.append(bool(r["verified"]))
    n = len(ratings)
    dist = {s: ratings.count(s) for s in range(5, 0, -1)}
    five, one = dist[5] / n * 100, dist[1] / n * 100
    signals = []
    points = 0
    if five >= 85 and n >= 10:
        signals.append(f"{five:.0f}% are 5-star, unusually uniform.")
        points += 2
    mid = (dist[2] + dist[3] + dist[4]) / n * 100
    if five >= 60 and one >= 15 and mid < 20:
        signals.append("Ratings are polarised (many 5-star and 1-star, few in between), a pattern often seen "
                       "with incentivised reviews. Read the 1-star reviews closely.")
        points += 1
    short = sum(1 for t in texts if len(t.split()) < 6 or GENERIC.match(t)) / n * 100
    if short >= 40 and n >= 10:
        signals.append(f"{short:.0f}% of reviews are very short or generic ('Great product!').")
        points += 1
    if verified:
        unv = verified.count(False) / len(verified) * 100
        if unv >= 30:
            signals.append(f"{unv:.0f}% are not marked as verified purchases.")
            points += 1
    if len(dates) >= 10:
        dates.sort()
        best = 0
        for i, d in enumerate(dates):
            j = i
            while j < len(dates) and (dates[j] - d).days <= 7:
                j += 1
            best = max(best, j - i)
        if best / len(dates) >= 0.4:
            signals.append(f"{best} of {len(dates)} dated reviews arrived within one week: a burst.")
            points += 2
    normed = [" ".join(re.findall(r"[a-z0-9']+", t.lower())) for t in texts]
    counts: dict = {}
    for t in normed:
        if t:
            counts[t] = counts.get(t, 0) + 1
    identical = sum(c for c in counts.values() if c > 1)
    sh = [_shingles(t) for t in normed if len(t.split()) >= 6]
    near = 0
    for i in range(len(sh)):
        for j in range(i + 1, len(sh)):
            if sh[i] and sh[j] and sh[i] != sh[j] and len(sh[i] & sh[j]) / len(sh[i] | sh[j]) >= 0.5:
                near += 1
    if identical:
        signals.append(f"{identical} reviews repeat another review's exact text.")
        points += 2 if identical >= 3 else 1
    if near:
        signals.append(f"{near} pair(s) of reviews share much of their wording.")
        points += 2 if near >= 2 else 1
    level = "low" if points <= 1 else "medium" if points <= 3 else "high"
    avg = sum(ratings) / n
    return {"count": n, "average": avg, "distribution": dist, "signals": signals, "level": level,
            "sample_warning": n < 20}


def cmd_reviews(a) -> int:
    data = load_json(a.file)
    reviews = data.get("reviews") if isinstance(data, dict) else data
    if not isinstance(reviews, list):
        fail("Give a JSON list of reviews, or an object with a 'reviews' list.")
    r = review_signals(reviews)
    out(f"{r['count']} reviews, average {r['average']:.2f}. "
        + "  ".join(f"{s}★ {c}" for s, c in r["distribution"].items()))
    out(f"Warning-sign level: {r['level']}")
    for s in r["signals"]:
        out(f"  - {s}")
    if not r["signals"]:
        out("  - No warning signs in this sample.")
    if r["sample_warning"]:
        out("  (Fewer than 20 reviews in the sample: weak evidence either way.)")
    out("These are heuristics, not proof. Weigh them with the seller's history and the 1-3 star reviews.")
    return 0


# --------------------------------------------------------------------------- shopper comparison

DEFAULT_WEIGHTS = {"fit": 40, "value": 25, "trust": 20, "reviews": 15}


def parse_weights(text: str | None) -> dict:
    if not text:
        return dict(DEFAULT_WEIGHTS)
    w = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        k = k.strip()
        if k not in DEFAULT_WEIGHTS:
            fail(f"Unknown weight '{k}'. Use {', '.join(DEFAULT_WEIGHTS)}.")
        w[k] = float(dec(v, f"weight {k}"))
    for k in DEFAULT_WEIGHTS:
        w.setdefault(k, 0.0)
    if sum(w.values()) <= 0:
        fail("Weights must add up to more than 0.")
    return w


def score_listings(listings: list, weights: dict, budget=None, defaults=None) -> list:
    """Score 0-100 per listing. fit (0-10) comes from Claude's reading of the user's needs; value, trust and
    reviews are computed from the listing data so the ranking is consistent."""
    if not listings:
        fail("No listings to compare.")
    defaults = defaults or {}
    listings = [{**{k: v for k, v in defaults.items() if v is not None}, **l} for l in listings]
    by_name = {l.get("name"): l for l in listings}
    for l in listings:  # an open-box or resold copy can borrow the reviews of the same product elsewhere
        src = by_name.get(l.get("same_product_as"))
        if src and l.get("rating") is None:
            for k in ("rating", "review_count", "review_warning"):
                if src.get(k) is not None:
                    l[k] = src[k]
            l["_borrowed_reviews"] = src.get("name")
    rows = []
    for i, l in enumerate(listings):
        name = l.get("name") or f"Listing {i + 1}"
        try:
            total = landed_cost(l["price"], l.get("shipping", 0), l.get("tax_pct", 0), l.get("duty_pct", 0))["total"]
        except KeyError:
            fail(f"{name}: needs a 'price'.")
        fit = dec(l.get("fit", 5), f"{name} fit")
        if fit > 10:
            fail(f"{name}: fit must be 0-10.")
        rows.append({"l": l, "name": name, "total": total, "fit": float(fit)})
    cheapest = min(r["total"] for r in rows)
    for r in rows:
        l = r["l"]
        r["value"] = float(cheapest / r["total"] * 10) if r["total"] else 0.0
        sr = l.get("seller_rating_pct")
        trust = max(0.0, (float(sr) - 80) / 2.5) if sr is not None else 6.0  # 80% -> 0, 100% -> 8; unknown -> 6
        if l.get("sold_by_brand_or_marketplace"):
            trust += 1.5
        if l.get("returns_days") is not None:
            trust += 1 if int(l["returns_days"]) >= 30 else -1 if int(l["returns_days"]) == 0 else 0
        if str(l.get("condition", "new")).lower() in ("used", "open box", "open-box", "refurbished", "renewed"):
            trust -= 1
        r["trust"] = max(0.0, min(10.0, trust))
        rating, count = l.get("rating"), l.get("review_count", 0)
        if rating is None:
            rv = 3.0
        else:
            rv = (float(rating) - 3) / 2 * 10 * min(1.0, (int(count) / 100) ** 0.5)
        if l.get("review_warning") == "high":
            rv *= 0.4
        elif l.get("review_warning") == "medium":
            rv *= 0.7
        r["reviews"] = max(0.0, min(10.0, rv))
        total_w = sum(weights.values())
        r["score"] = sum(r[k] * weights[k] for k in weights) / total_w * 10
        r["over_budget"] = budget is not None and r["total"] > budget
    rows.sort(key=lambda r: (r["over_budget"], -r["score"]))
    return rows


def cmd_compare(a) -> int:
    data = load_json(a.file)
    listings = data.get("listings") if isinstance(data, dict) else data
    if not isinstance(listings, list):
        fail("Give a JSON list of listings, or an object with a 'listings' list.")
    cur = (data.get("currency") if isinstance(data, dict) else None) or a.currency
    budget = dec(data["budget"], "budget") if isinstance(data, dict) and data.get("budget") is not None else None
    w = parse_weights(a.weights)
    defaults = {k: data.get(k) for k in ("tax_pct", "duty_pct")} if isinstance(data, dict) else {}
    rows = score_listings(listings, w, budget, defaults)
    out(f"Weights: " + ", ".join(f"{k} {v:g}" for k, v in w.items()) + (f" | Budget {money(budget, cur)}" if budget else ""))
    out("")
    out("| Rank | Listing | Marketplace | Total cost | Fit | Value | Trust | Reviews | Score |")
    out("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        flag = " (over budget)" if r["over_budget"] else ""
        out(f"| {i} | {r['name']}{flag} | {r['l'].get('marketplace', '-')} | {money(r['total'], cur)} | "
            f"{r['fit']:.0f} | {r['value']:.1f} | {r['trust']:.1f} | {r['reviews']:.1f} | **{r['score']:.0f}** |")
    if any(r["over_budget"] for r in rows):
        out("\nOver-budget listings are ranked last, whatever their score.")
    for r in rows:
        if r["l"].get("_borrowed_reviews"):
            out(f"{r['name']}: reviews taken from '{r['l']['_borrowed_reviews']}' (same product, listed elsewhere).")
    if a.html:
        write_html(rows, w, cur, budget, a.html)
        out(f"\nVisual comparison saved to {a.html}")
    return 0


def write_html(rows, weights, cur, budget, path) -> None:
    e = html.escape
    cards = []
    for i, r in enumerate(rows, 1):
        bars = "".join(f'<div class="bar"><span>{k}</span><i style="width:{r[k] * 10:.0f}%"></i><b>{r[k]:.1f}</b></div>'
                       for k in ("fit", "value", "trust", "reviews"))
        url = r["l"].get("url")
        link = f'<a href="{e(url)}" rel="noopener noreferrer">open listing</a>' if url and str(url).startswith("http") else ""
        cards.append(f'<article class="{"over" if r["over_budget"] else ""}"><h2>#{i} {e(r["name"])}</h2>'
                     f'<p class="meta">{e(str(r["l"].get("marketplace", "")))} · {e(money(r["total"], cur))} to your door'
                     f'{" · over budget" if r["over_budget"] else ""}</p><p class="score">{r["score"]:.0f}</p>{bars}{link}</article>')
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShelfScout comparison</title><style>
:root{{--bg:#f6f5f1;--card:#fff;--ink:#1b1b1b;--muted:#6b6b6b;--accent:#2f6f4f;--warn:#b5442f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--card:#1f1f1f;--ink:#eee;--muted:#a0a0a0;--accent:#6cc49a;--warn:#ef8a74}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}}
h1{{font-size:20px;margin:0 0 4px}}.sub{{color:var(--muted);margin:0 0 20px}}
main{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
article{{background:var(--card);border-radius:12px;padding:16px;position:relative}}article.over{{opacity:.6}}
h2{{font-size:16px;margin:0 52px 4px 0}}.meta{{color:var(--muted);margin:0 0 10px;font-size:13px}}
.score{{position:absolute;top:12px;right:14px;font-size:26px;font-weight:700;margin:0;color:var(--accent)}}
.bar{{display:grid;grid-template-columns:60px 1fr 30px;align-items:center;gap:8px;font-size:12px;margin:4px 0}}
.bar i{{display:block;height:6px;border-radius:3px;background:var(--accent)}}.bar b{{text-align:right}}
a{{color:var(--accent);font-size:13px}}</style></head><body>
<h1>ShelfScout comparison</h1><p class="sub">Weights: {e(", ".join(f"{k} {v:g}" for k, v in weights.items()))}
{e(f" · budget {money(budget, cur)}") if budget else ""}. Scores are 0-100; fit is judged against your needs.</p>
<main>{"".join(cards)}</main></body></html>"""
    try:
        Path(path).write_text(doc, encoding="utf-8")
    except OSError as err:
        fail(f"Couldn't write {path} ({err.strerror}).")


# --------------------------------------------------------------------------- seller margin

def margin_calc(sell, cost, inbound=0, marketplace=None, referral_pct=None, fixed_fee=None, fulfil=0,
                ads_pct=0, returns_pct=0, other=0) -> dict:
    sell = dec(sell, "--sell", positive=True)
    cost, inbound, fulfil, other = (dec(cost, "--cost"), dec(inbound, "--inbound"), dec(fulfil, "--fulfil"),
                                    dec(other, "--other"))
    ads_pct, returns_pct = dec(ads_pct, "--ads-pct"), dec(returns_pct, "--returns-pct")
    preset = FEE_PRESETS.get(marketplace) if marketplace else None
    if marketplace and not preset:
        fail(f"Unknown marketplace '{marketplace}'. Use {', '.join(FEE_PRESETS)}, or give --referral-pct.")
    ref_pct = dec(referral_pct, "--referral-pct") if referral_pct is not None else Decimal(preset["referral_pct"]) if preset else Decimal(0)
    fixed = dec(fixed_fee, "--fixed-fee") if fixed_fee is not None else Decimal(preset["fixed"]) if preset else Decimal(0)
    referral = sell * ref_pct / 100
    ads = sell * ads_pct / 100
    # Returns: a returned unit usually loses its fees and handling and often can't be resold. Assume half
    # the landed product cost is lost on a return; it's a simple, stated assumption.
    returns = (cost + inbound) * Decimal("0.5") * returns_pct / 100 + (referral + fixed + fulfil) * returns_pct / 100
    costs = cost + inbound + referral + fixed + fulfil + ads + returns + other
    profit = sell - costs
    return {"sell": sell, "product": cost, "inbound": inbound, "referral": referral, "ref_pct": ref_pct,
            "fixed": fixed, "fulfil": fulfil, "ads": ads, "returns": returns, "other": other, "costs": costs,
            "profit": profit, "margin_pct": profit / sell * 100,
            "roi_pct": profit / (cost + inbound) * 100 if cost + inbound else None,
            "breakeven_ads_pct": (profit + ads) / sell * 100, "preset": preset}


def cmd_margin(a) -> int:
    r = margin_calc(a.sell, a.cost, a.inbound, a.marketplace, a.referral_pct, a.fixed_fee, a.fulfil,
                    a.ads_pct, a.returns_pct, a.other)
    c = a.currency
    out(f"Selling price                   {money(r['sell'], c)}")
    for label, key in (("Product cost", "product"), ("Shipping to you / warehouse", "inbound"),
                       (f"Marketplace fee ({pct(r['ref_pct'])})", "referral"), ("Fixed fees", "fixed"),
                       ("Fulfilment", "fulfil"), ("Ads", "ads"), ("Returns allowance", "returns"), ("Other", "other")):
        if r[key]:
            out(f"- {label:<30}{money(r[key], c)}")
    out(f"= Profit per unit               {money(r['profit'], c)}   margin {pct(r['margin_pct'])}"
        + (f", ROI {pct(r['roi_pct'])}" if r["roi_pct"] is not None else ""))
    out(f"Ads can take up to {pct(r['breakeven_ads_pct'])} of the price before you lose money.")
    verdict = ("Not viable: it loses money." if r["profit"] <= 0 else
               "Thin: under 15% margin leaves no room for price drops or fee changes." if r["margin_pct"] < 15 else
               "Workable: 15-30% margin." if r["margin_pct"] < 30 else "Strong: 30%+ margin.")
    out(f"Verdict: {verdict}")
    if r["preset"]:
        out(f"Fee preset '{a.marketplace}': {r['preset']['note']} These are {FEES_CHECKED}.")
    return 0


def cmd_fees(a) -> int:
    out(f"Fee presets ({FEES_CHECKED}):")
    for k, v in FEE_PRESETS.items():
        out(f"- {k}: {v['referral_pct']}% + {v['fixed']} per order. {v['note']}")
    return 0


# --------------------------------------------------------------------------- main

def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="ShelfScout calculators for shoppers and sellers.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("landed")
    p.add_argument("--price", required=True)
    p.add_argument("--shipping", default="0")
    p.add_argument("--tax-pct", default="0")
    p.add_argument("--duty-pct", default="0")
    p.add_argument("--fees", default="0")
    p.add_argument("--currency", default="USD")
    p = sub.add_parser("unit")
    p.add_argument("--price", required=True)
    p.add_argument("--qty", required=True)
    p.add_argument("--unit-name", default="unit")
    p.add_argument("--per", default="1")
    p.add_argument("--currency", default="USD")
    p = sub.add_parser("deal")
    p.add_argument("--price", required=True)
    p.add_argument("--was")
    p.add_argument("--history")
    p.add_argument("--currency", default="USD")
    p = sub.add_parser("reviews")
    p.add_argument("file")
    p = sub.add_parser("compare")
    p.add_argument("file")
    p.add_argument("--weights")
    p.add_argument("--html")
    p.add_argument("--currency", default="USD")
    p = sub.add_parser("margin")
    p.add_argument("--sell", required=True)
    p.add_argument("--cost", required=True)
    p.add_argument("--inbound", default="0")
    p.add_argument("--marketplace", choices=sorted(FEE_PRESETS))
    p.add_argument("--referral-pct")
    p.add_argument("--fixed-fee")
    p.add_argument("--fulfil", default="0")
    p.add_argument("--ads-pct", default="0")
    p.add_argument("--returns-pct", default="0")
    p.add_argument("--other", default="0")
    p.add_argument("--currency", default="USD")
    sub.add_parser("fees")
    a = ap.parse_args(argv)
    return {"landed": cmd_landed, "unit": cmd_unit, "deal": cmd_deal, "reviews": cmd_reviews,
            "compare": cmd_compare, "margin": cmd_margin, "fees": cmd_fees}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
