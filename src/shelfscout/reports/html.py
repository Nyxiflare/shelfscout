"""Self-contained HTML report (no scripts, no external requests). All text is escaped."""
from __future__ import annotations

import html

from ..profiles.loader import DIMENSION_LABELS

COLOURS = {"ELIGIBLE": "ok", "PROVISIONAL": "warn", "INSUFFICIENT_EVIDENCE": "muted", "SAFETY_HOLD": "bad", "EXCLUDED": "bad"}


def render(result: dict) -> str:
    e = html.escape
    ev = {x["product_id"]: x for x in result["evaluations"]}
    cards = []
    for i, pid in enumerate(result["rankings"]["overall"], 1):
        x = ev[pid]
        bars = []
        for d in result["weights"]:
            if result["weights"][d] <= 0:
                continue
            v = x["dimensions"].get(d)
            if v:
                bars.append(f'<div class="bar"><span>{e(DIMENSION_LABELS[d])}</span><i style="width:{v["score"]:.0f}%;'
                            f'opacity:{0.35 + v["confidence"] / 154:.2f}"></i><b>{v["score"]:.0f}</b></div>')
            else:
                bars.append(f'<div class="bar unknown"><span>{e(DIMENSION_LABELS[d])}</span><i></i><b>?</b></div>')
        url = x.get("url") or ""
        link = f'<a href="{e(url)}" rel="noopener noreferrer">listing</a>' if url.startswith(("http://", "https://")) else ""
        reasons = f'<p class="why">{e("; ".join(x["eligibility_reasons"]))}</p>' if x["eligibility_reasons"] else ""
        score = "–" if x["overall_score"] is None else f'{x["overall_score"]:.0f}'
        cards.append(f'<article><h2>#{i} {e(x["name"])}</h2><p class="meta">{e(x["price"] or "price not recorded")} · '
                     f'confidence {e(str(x["confidence"]))} · coverage {x["coverage"] * 100:.0f}% · '
                     f'<span class="tag {COLOURS[x["eligibility"]]}">{e(x["eligibility"].replace("_", " ").lower())}</span></p>'
                     f'<p class="score">{score}</p>{reasons}{"".join(bars)}{link}</article>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShelfScout evaluation</title><style>
:root{{--bg:#f6f5f1;--card:#fff;--ink:#1b1b1b;--muted:#6b6b6b;--accent:#2f6f4f;--warn:#9a6b00;--bad:#b5442f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--card:#1f1f1f;--ink:#eee;--muted:#a0a0a0;--accent:#6cc49a;--warn:#e0b44a;--bad:#ef8a74}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}}
h1{{font-size:20px;margin:0 0 4px}}.sub{{color:var(--muted);margin:0 0 20px;font-size:13px}}
main{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
article{{background:var(--card);border-radius:12px;padding:16px;position:relative}}
h2{{font-size:16px;margin:0 56px 4px 0}}.meta{{color:var(--muted);margin:0 0 8px;font-size:12px}}
.score{{position:absolute;top:12px;right:14px;font-size:26px;font-weight:700;margin:0;color:var(--accent)}}
.why{{font-size:12px;color:var(--warn);margin:0 0 8px}}
.bar{{display:grid;grid-template-columns:120px 1fr 26px;align-items:center;gap:8px;font-size:12px;margin:3px 0}}
.bar i{{display:block;height:6px;border-radius:3px;background:var(--accent)}}.bar b{{text-align:right}}
.bar.unknown span,.bar.unknown b{{color:var(--muted)}}
.tag{{padding:1px 6px;border-radius:8px;border:1px solid currentColor}}.ok{{color:var(--accent)}}.warn{{color:var(--warn)}}.bad{{color:var(--bad)}}.muted{{color:var(--muted)}}
a{{color:var(--accent);font-size:13px}}footer{{color:var(--muted);font-size:12px;margin-top:20px}}</style></head><body>
<h1>ShelfScout: {e(result["category"].replace("_", " "))}</h1>
<p class="sub">{e(result["country"] or "")} · {e(result["currency"])} · as of {e(result["as_of"])} · profile {e(result["profile"])} v{e(result["profile_version"])} · bar opacity shows confidence, ? means unknown</p>
<main>{"".join(cards)}</main>
<footer>{e(result["calibration"])} Unknown means not established, not bad. Not a safety certification or legal advice.</footer>
</body></html>"""
