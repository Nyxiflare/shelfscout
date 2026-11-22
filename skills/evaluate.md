# Deep evaluation

For considered purchases where the question is "which is actually good to own": build quality,
durability, fit to the body, safety, service and value. You collect and label evidence; the engine
turns it into scores, confidence, eligibility and rankings. You never type a score into a report
yourself.

## Workflow

1. **Understand the person (1–3 questions at most):**
   - what it's for and how heavily it will be used
   - country, which sets the safety rules and currency
   - budget
   - what matters most (these become `priorities`)
   - must-have features

   For chairs, also ask their height or, better, their seat measurements. For shoes, ask foot width
   and preferred drop. If the message already says, don't ask.
2. **Pick the profile.** Run `SS profile` and choose the most specific one (`office_chair`,
   `smartphone`, `running_shoes`, otherwise the top-level category such as `home_appliances` or
   `baby_children`). Run `SS profile <name>` to see its weights, safety gates and the requirements for
   the person's country.
3. **Find 2–6 candidates** within the budget, plus at most one just outside it if it's a notable
   alternative. Pin down each one's exact model and variant (model number, GTIN/EAN, size, storage,
   colour). Variants are different products.
4. **Collect evidence** from, in order of strength:
   - independent tests
   - government registries and recall databases
   - the manufacturer's spec sheet and manual
   - the listing
   - owner reviews

   Read reviews across all star ratings. Stay within each site's terms (see SKILL.md). Write down what
   each source actually says, with the exact quote where you can.
5. **Write the request file** (format below) in the user's working folder. Every fact is a *claim*
   with a status and a source. Anything you looked for and couldn't find is an `UNKNOWN` claim. That
   isn't a failure: it's information the person deserves.
6. **Run** `SS evaluate request.json --md report.md --html report.html`, and add `--save` to keep it in
   the local history.
7. **Present the result**, verdict first, using the report: what's recommended and its status, then
   the best per dimension if different, what to avoid and why, the key trade-offs, and what's unknown.
   Offer the HTML report. Don't round a provisional result up into a confident one.

## Labelling evidence honestly

| Status | Use for | Never use for |
|---|---|---|
| `INDEPENDENTLY_TESTED` | An independent lab or reviewer measured it with a stated method | A brand's own test results |
| `VERIFIED` | Confirmed in an independent primary record (FCC ID lookup, BIS registry, recall database) | A logo on a listing or a box |
| `MANUFACTURER_REPORTED` | The brand, its manual, or the seller says so | — |
| `CUSTOMER_REPORTED` | Owners report it (reviews, forums) | — |
| `ESTIMATED` | You inferred it with a method you can state | Guesses |
| `UNKNOWN` | You looked and couldn't establish it (no value) | — |

The engine refuses a `VERIFIED` or `INDEPENDENTLY_TESTED` claim whose source isn't independent, and
refuses any non-`UNKNOWN` claim without a source. An AI-written summary is never a source.

`variant_match` says how closely the evidence fits this exact variant: `exact` (the default),
`other_variant` (same model, different size or storage), `product_family`, or `brand`. Less exact
evidence counts with less confidence. Never copy another variant's reviews or specs without marking it.

## Request format

```json
{
  "category": "office_chair",
  "as_of": "2026-11-22",
  "market": {"country": "IN", "currency": "INR"},
  "user": {
    "budget": {"min": 8000, "max": 12000},
    "priorities": {"ergonomics": 35, "durability": 30, "materials_build": 20, "safety": 15},
    "body": {"popliteal_height_cm": 44, "buttock_popliteal_cm": 48, "hip_breadth_cm": 38, "weight_kg": 82},
    "must_have": ["headrest"],
    "use": "8+ hours a day"
  },
  "sources": [
    {"id": "brand", "name": "Brand spec page", "type": "manufacturer", "url": "https://…"},
    {"id": "lab", "name": "Independent test", "type": "independent_lab", "published_at": "2026-06-10"},
    {"id": "rv", "name": "Marketplace reviews, 40 sampled", "type": "customer_reviews"}
  ],
  "products": [{
    "id": "a", "name": "Example Chair", "brand": "Example", "model_number": "EX-2", "gtin": "",
    "variant": {"colour": "black"},
    "listing": {"marketplace": "…", "price": 10499, "shipping": 0, "url": "https://…", "observed_at": "2026-11-22", "source": "brand"},
    "claims": [
      {"id": "c1", "claim_type": "material.frame", "status": "MANUFACTURER_REPORTED", "value": "aluminium alloy",
       "source": "brand", "quote": "Frame: aluminium alloy", "limitations": ["grade not disclosed"]},
      {"id": "c2", "claim_type": "ergonomics.seat_height", "status": "MANUFACTURER_REPORTED",
       "value": {"min": 430, "max": 530}, "unit": "mm", "source": "brand"},
      {"id": "c3", "claim_type": "material.frame_grade", "status": "UNKNOWN"}
    ],
    "safety": [{"requirement": "us-fcc", "outcome": "pass", "claim": "c9"}],
    "recalls": [{"id": "…", "status": "active", "source": "gov"}],
    "reviews": {"source": "rv", "items": [
      {"rating": 2, "date": "2026-05-01", "verified": true, "text": "Cushion went flat after six months",
       "aspects": [{"aspect": "cushion", "category": "durability", "sentiment": "negative", "severity": 3,
                    "quote": "went flat", "ownership_months": 6}]}
    ]},
    "criteria": [{"dimension": "aesthetics", "criterion": "finish quality", "score": 80, "claims": ["c7"], "basis": "close-up photos show even welds"}]
  }]
}
```

- **Source types:** `independent_lab`, `government_record`, `standards_body`, `expert_review`,
  `manufacturer`, `marketplace_listing`, `customer_reviews`, `forum`, `reference_data`,
  `user_provided`, `model`. Set `independence` (`independent`, `manufacturer`, `seller`,
  `affiliated`, `unknown`) when it isn't obvious, especially for review sites with affiliate links.
- **Units:** mm, cm, m, in, g, kg, lb, MPa, GPa, psi, kg/m3, g/cm3, W/m.K, h, W, kWh, mAh, %.
  Ranges are `{"min": …, "max": …}`.
- **Listing currency** must match the market currency. Convert first with a dated rate and say so.
- **Review aspects:** tag what each review is about. Use `category` from defect, failure,
  durability, comfort, fit, quality, performance, service, design, assembly, value, safety, other.
  `severity` (1–5) is for negatives: 5 is dangerous or product-ending, 1 is cosmetic. Add
  `ownership_months` when the reviewer says how long they've owned it. Duplicated texts count once.
- **Criteria** are your judgements, allowed for any dimension except safety and price-to-value, and
  only when tied to known claims. They count with lower confidence than a computed criterion.
  Prefer claims the engine can score itself.

## Claim types the engine scores

| Claim type | Value | Dimension |
|---|---|---|
| `material.frame` / `material.midsole` | material name or grade (see `SS materials`) | Materials & build |
| `property.<name>` | measured value + unit, independently tested (e.g. `property.yield_strength`) | replaces catalogue ranges |
| `warranty.years` | number | Durability, Service |
| `repair.spare_parts_available` · `repair.repairability_index` (0–10) | true/false · number | Durability |
| `service.network_in_country` · `service.typical_repair_days` | true/false · number | Service |
| `brand.years_in_market` · `brand.recalls_last_5_years` · `brand.publishes_full_specs` | number · number · true/false | Brand trust |
| `test.failure_rate_pct` | number, independent | Reliability |
| `test.safety.<name>` | true/false, independent | Safety |
| `certification.<name>` + a `safety` record | text | Safety (requirement met) |
| `feature.<name>` | true/false (matched against `must_have`) | Features |
| `performance.<name>` + `test.<name>` | advertised vs. tested value, same unit | Features (tested ÷ advertised) |
| **Office chair:** `ergonomics.seat_height` / `seat_depth` / `seat_width` (mm), `ergonomics.lumbar` (adjustable/fixed/none), `ergonomics.armrest_adjustments` (0–4), `ergonomics.recline_lock`, `construction.gas_lift_class`, `construction.seat_foam_density` (kg/m3), `construction.weight_capacity` (kg) | | Ergonomics, Materials, Durability |
| **Smartphone:** `construction.ip_rating`, `software.update_years`, `ergonomics.width` (mm), `ergonomics.weight` (g) | | Materials, Durability, Ergonomics |
| **Running shoes:** `fit.widths_available` (list), `fit.heel_toe_drop` (mm), `ergonomics.weight` (g), `construction.outsole_rubber_coverage_pct` | | Ergonomics, Materials |

Categories without their own subprofile still use the common rules, reviews, safety requirements and
your evidence-tied criteria. They'll usually come out *provisional*, which is honest.

## How to read the result

- **Score:** weighted over the dimensions that have evidence. **Coverage:** the share of the
  category's weight that has evidence. **Confidence:** how strong that evidence is.
- **Status:**
  - `ELIGIBLE`: enough strong evidence and no safety problem.
  - `PROVISIONAL`: recommendable, but with gaps.
  - `INSUFFICIENT_EVIDENCE`: can't be ranked fairly.
  - `SAFETY_HOLD`: a required safety check is missing or weak.
  - `EXCLUDED`: an active recall or a failed mandatory requirement. No score or preference overrides it.
- Over-budget products never win the budget ranking. "Unknown" means not established, not bad.

## Never

- Never invent specs, grades, certifications, test results, prices, reviews or lifespans.
- Never present typical material ranges as measurements of the product. Never call reviews "fake":
  report warning signs.
- Never call a product safe or certified because of a logo, or legally compliant at all. Point to
  the requirement and its evidence status.
- Never let affiliate links, sponsorship or brand popularity affect what you record.
