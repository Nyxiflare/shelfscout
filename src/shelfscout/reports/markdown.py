"""Markdown report: the verdict first, then the evidence behind every number."""
from __future__ import annotations

from ..profiles.loader import DIMENSION_LABELS

STATUS_TEXT = {
    "ELIGIBLE": "eligible", "PROVISIONAL": "provisional (limited evidence)",
    "INSUFFICIENT_EVIDENCE": "insufficient evidence to rank", "SAFETY_HOLD": "safety hold", "EXCLUDED": "excluded",
}


def _cell(text) -> str:
    return " ".join(str(text if text is not None else "-").split()).replace("|", "\\|")


def render(result: dict) -> str:
    ev = {e["product_id"]: e for e in result["evaluations"]}
    rk = result["rankings"]
    lines = [f"# ShelfScout evaluation: {result['category'].replace('_', ' ')}", ""]
    lines.append(f"Market {result['country'] or '-'} · {result['currency']} · as of {result['as_of']} · "
                 f"profile {result['profile']} v{result['profile_version']} · engine {result['algorithm_version']}")
    if result["budget"]["min"] or result["budget"]["max"]:
        lines.append(f"Budget: {result['budget']['min'] or 'any'} to {result['budget']['max'] or 'any'}")
    lines += ["", "## Verdict", ""]
    rec = rk.get("recommended")
    if rec:
        e = ev[rec]
        lines.append(f"**Recommended:** {e['name']}, score {e['overall_score']} "
                     f"({STATUS_TEXT[e['eligibility']]}), {e['price'] or 'price not recorded'}")
        if e["eligibility"] != "ELIGIBLE":
            lines.append(f"Why it isn't fully eligible: {'; '.join(e['eligibility_reasons'])}.")
    else:
        lines.append("**No product can be recommended** on the evidence available.")
    for d, pid in rk.get("best_by_dimension", {}).items():
        if pid != rec:
            lines.append(f"- Best {DIMENSION_LABELS[d].lower()}: {ev[pid]['name']} ({ev[pid]['dimensions'][d]['score']})")
    if rk.get("avoid"):
        lines.append("")
        for pid in rk["avoid"]:
            lines.append(f"**Avoid:** {ev[pid]['name']}: {'; '.join(ev[pid]['eligibility_reasons'])}")
    if rk.get("over_or_under_budget"):
        lines.append("")
        lines.append("Outside your budget (not ranked in it): " + ", ".join(ev[p]["name"] for p in rk["over_or_under_budget"]))
    lines += ["", "## Comparison", "", "| Rank | Product | Price | Score | Confidence | Evidence coverage | Status |",
              "|---|---|---|---|---|---|---|"]
    for i, pid in enumerate(rk["overall"], 1):
        e = ev[pid]
        lines.append(f"| {i} | {_cell(e['name'])} | {_cell(e['price'])} | {_cell(e['overall_score'])} | "
                     f"{_cell(e['confidence'])} | {e['coverage'] * 100:.0f}% | {STATUS_TEXT[e['eligibility']]} |")
    dims = [d for d in result["weights"] if result["weights"][d] > 0]
    lines += ["", "### By dimension (score / confidence)", "",
              "| Dimension | Weight | " + " | ".join(_cell(ev[p]["name"]) for p in rk["overall"]) + " |",
              "|---|---|" + "---|" * len(rk["overall"])]
    for d in dims:
        row = []
        for p in rk["overall"]:
            x = ev[p]["dimensions"].get(d)
            row.append(f"{x['score']:.0f} / {x['confidence']:.0f}" if x else "unknown")
        lines.append(f"| {DIMENSION_LABELS[d]} | {result['weights'][d]:g} | " + " | ".join(row) + " |")
    for pid in rk["overall"]:
        e = ev[pid]
        lines += ["", f"## {e['name']}", ""]
        if e["marketplace"]:
            lines.append(f"{e['marketplace']} · {e['price']}" + (f" · {e['url']}" if e["url"] else ""))
        lines.append(f"Status: **{STATUS_TEXT[e['eligibility']]}**" +
                     (f" ({'; '.join(e['eligibility_reasons'])})" if e["eligibility_reasons"] else ""))
        for d, x in e["dimensions"].items():
            lines.append(f"- **{DIMENSION_LABELS[d]} {x['score']:.0f}** (confidence {x['confidence']:.0f})")
            for c in x["criteria"]:
                lines.append(f"  - {c['name']}: {c['score']:.0f} [{c['method']}] {c['basis']}"
                             + (f" (evidence: {', '.join(c['claims'])})" if c["claims"] else ""))
        if e["missing_dimensions"]:
            lines.append("- **Unknown:** " + ", ".join(DIMENSION_LABELS[d] for d in e["missing_dimensions"]))
        s = e.get("safety") or {}
        unresolved = s.get("unresolved_mandatory") or []
        if unresolved:
            lines.append("- **Safety not evidenced:** " + "; ".join(unresolved))
        rv = e.get("reviews")
        if rv:
            top = sorted(rv["aspects"].items(), key=lambda kv: -kv[1]["negative"])[:4]
            if top and top[0][1]["negative"]:
                lines.append(f"- **Top complaints** (share of {rv['analysed']} unique reviews): " +
                             "; ".join(f"{k} {v['negative_share_of_reviews']}%" for k, v in top if v["negative"]))
            lines.append(f"- Review warning signs: {rv['authenticity']['level']}" +
                         (f" ({'; '.join(rv['authenticity']['signals'])})" if rv["authenticity"]["signals"] else ""))
        for n in e["notes"]:
            lines.append(f"- Note: {n}")
    lines += ["", "---", "", f"*{result['calibration']} Scores reflect only the evidence listed; 'unknown' means "
              "not established, not bad. Not a safety certification or legal advice.*"]
    return "\n".join(lines) + "\n"
