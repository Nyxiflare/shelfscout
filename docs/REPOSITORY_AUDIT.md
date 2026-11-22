# ShelfScout repository audit (Phase 0)

- **Date:** 2026-11-22
- **Audited:** `main` at `37d4719`
- **Branch for V2 work:** `feature/shelfscout-v2`

No existing file was changed for this audit.

## 1. What exists today

| Path | Lines | Role |
|---|---|---|
| `SKILL.md` | 184 | Agent instructions: shopper and seller workflows, data rules, output formats, JSON data formats |
| `scripts/shelf.py` | 549 | Single-file, standard-library-only calculator CLI |
| `tests/test_shelf.py` | 252 | 31 unittest tests, all offline |
| `references/shopper-trust.md` | 48 | Trust signals per marketplace |
| `references/seller-risks.md` | 49 | IP, gated categories, compliance, operational risks, supplier checks |
| `examples/headphones/`, `examples/seller-lunchbox/` | — | Sample inputs for both modes (synthetic, built for testing) |
| `README.md`, `LICENSE` (MIT), `.gitignore` | — | Packaging |

**Test run (2026-11-22, Python 3.11.0):** `python -m unittest discover -s tests` → **31 tests, OK.**

**Local tooling:**
- Pydantic: not installed.
- PostgreSQL: not installed.
- Docker: not installed.
- The skill currently needs only Python. `npx skills add` copies the folder and installs no Python packages.

## 2. Current interfaces (must stay working)

**CLI** (`python scripts/shelf.py <command>`). SKILL.md and the README document these, so they are a public interface:

| Command | Function | Inputs |
|---|---|---|
| `landed` | `landed_cost()` | price, shipping, tax %, duty %, fees, currency |
| `unit` | `cmd_unit()` | price, qty, unit name, per |
| `deal` | `deal_check()` | price, was, `--history` JSON list `{date, price}` |
| `reviews` | `review_signals()` | JSON list `{rating, date, verified, text}` |
| `compare` | `score_listings()`, `write_html()` | listings JSON (see SKILL.md "Data formats"), weights, `--html` |
| `margin` | `margin_calc()` | sell, cost, inbound, marketplace preset or referral %, fixed fee, fulfil, ads %, returns %, other |
| `fees` | `FEE_PRESETS` | none |

**Data formats** documented in SKILL.md: `listings.json` (only `price` is required), `reviews.json`, `prices.json`.

## 3. How the current logic works

- **Money:** `Decimal` throughout. Display rounding to 0 or 2 places, with `ZERO_DECIMAL` covering only JPY, KRW and VND.
- **Landed cost:** duty on price + shipping, then tax on price + shipping + duty, plus fees. There's no currency conversion.
- **Deal check:** median and lowest of the observed history. The price verdict and the discount claim are judged separately, and the claim is "supported" only if the 'was' price was observed within 2%.
- **Review signals:** heuristic points for uniform 5-star ratings, polarisation, short or generic text, unverified share, a 7-day burst, exact duplicates, and near-duplicates (3-word shingle Jaccard ≥ 0.5). The resulting level is low, medium or high.
- **Compare:** one weighted 0–100 score from four sub-scores:
  - **fit:** from the agent, default 5
  - **value:** cheapest total ÷ this total
  - **trust:** from the seller rating, with a default of 6 when it's unknown
  - **reviews:** rating × count factor, with a default of 3 when there's no rating

  Over-budget items rank last. An open-box or resold listing can borrow reviews through `same_product_as`, matched by exact name.
- **Margin:** referral, fixed and fulfilment fees, ads, a returns allowance (50% of landed product cost plus fees, times the return rate), and other costs. Gives net per unit, margin, ROI and the break-even ad share.
- **Fees:** five static presets, labelled "not checked live".

## 4. Gaps against the V2 specification

| # | Gap | Severity for V2 | Notes |
|---|---|---|---|
| G-01 | **Missing data becomes a neutral score** (fit 5, trust 6, reviews 3) | **Critical** | Breaks the V2 rule "missing information must not silently become a neutral or positive score". The README and SKILL.md say so, but the score itself doesn't show it. |
| G-02 | **One combined score** mixes value, trust and reviews | High | V2 asks for separate dimension scores, confidence and eligibility. |
| G-03 | **No evidence model:** no source, timestamp, or observed/estimated/unknown label per value | Critical | The main V2 requirement. Today provenance only lives in Claude's prose. |
| G-04 | No product categories or category-specific weights | High | Everything uses the same four weights. |
| G-05 | No engineering dimensions (materials, durability, ergonomics, safety, service) | High | V2's main differentiator. |
| G-06 | No safety gate or eligibility status | Critical (for V2) | Nothing stops a product with an unresolved safety issue from ranking first. |
| G-07 | Product identity is exact-name `same_product_as` only | Medium | No variant model; the agent has to judge equivalence. |
| G-08 | Review analysis is heuristic only, with no aspect or complaint extraction in code | Medium | SKILL.md asks Claude to read the 1–3★ reviews, but complaints aren't structured or counted. |
| G-09 | No currency conversion; minor units cover only 3 currencies | Medium | Global scope needs ISO 4217 minor units and explicit FX rates with a source and date. |
| G-10 | Static fee presets, not versioned | Medium | Need a version and a checked-on date per preset. |
| G-11 | No persistence | Medium | Every run starts from scratch; no product profiles or evaluation history. |
| G-12 | No package structure (`pyproject.toml`), single 549-line file | Low | Fine today; it becomes a problem as V2 grows. |
| G-13 | Tests are unit-only; no evaluation set for judgement quality | High | No measure of whether verdicts are right on real products. |
| G-14 | Only tested on Windows | Low | No CI. |

## 5. Compatibility risks for V2

1. **Install friction:** today the skill installs with one command and runs on bare Python. If the skill itself requires Pydantic, SQLAlchemy, PostgreSQL or Docker, most people who install it can't use it. That would hurt the stage-one goal of 1,000 installs.
2. **CLI contract:** SKILL.md calls `shelf.py` commands and JSON formats directly. Changing them breaks the skill for anyone on an older copy, and for the agent's instructions.
3. **Score changes:** fixing G-01 will change rankings for the same inputs. That's intended, but it must be versioned and documented.
4. **Seller mode:** the V2 specification centres on shopper and engineering evaluation. Seller mode (`margin`, opportunity checks) must not regress or disappear.

## 6. What's genuinely hard (not code)

- **Evidence availability:** material grades, wall thicknesses, fatigue data, real service-centre performance and lifespans are rarely published for consumer products. Most products will score "unknown" on several engineering dimensions. The system has to make that a useful, honest answer rather than a failure.
- **Material data licensing:** the best property databases (for example MatWeb and Granta) restrict reuse. A seed database needs sources that allow redistribution, with values stored as typical ranges per material family and grade, never presented as measurements of a specific product.
- **Weights:** the proposed category weights are hypotheses. They need calibration before anything is presented as a rating.
- **Liability tone:** engineering and safety conclusions must stay evidence-labelled ("not verified", "manufacturer-reported") to avoid implying certification or testing that didn't happen.
