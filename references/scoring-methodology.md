# ShelfScout scoring methodology (engine 2.0.0a1, profiles v0.1)

This page is public on purpose: anyone should be able to see how a product is scored, and challenge it.

## 1. Evidence → criteria → dimensions
- Every input is a **claim** with a status, a source and a date (skills/evaluate.md).
- **Criteria** turn claims into 0–100 scores:
  - **Spec rules:** `linear` between a poor and a good value, a lookup `map`, or `bool`. They're
    stored in the category profile.
  - **Calculations:** body fit, material suitability, must-have share, tested ÷ advertised.
  - **Review aggregation.**
  - **The evaluator's judgements:** allowed only when tied to known claims, never for safety or
    price, and counted at 0.7× confidence.
- A **dimension score** is the weighted mean of its criteria. No criteria means no score. The
  dimension is "unknown", not average.

## 2. Overall score and coverage
- Overall = Σ(score × weight) ÷ Σ(weight) over **scored** dimensions only, using the category
  profile's weights.
- Coverage = the scored dimensions' share of total weight. Below 50% the product is
  `INSUFFICIENT_EVIDENCE`; below 80% it's `PROVISIONAL`.
- Price-to-value = (quality score excluding price) ÷ price to the door, relative to the best ratio
  in the comparison. It needs at least two priced products, and its confidence is scaled by the
  quality score's coverage.

## 3. Confidence (separate from quality)
Per claim, from 0 to 100:

> 0.30 × source quality + 0.25 × directness + 0.20 × variant relevance + 0.15 × independence + 0.10 × freshness

| Component | Values |
|---|---|
| Source quality | independent lab 95 · government record 95 · standards body 90 · expert review 75 · user provided 70 · manufacturer 60 · customer reviews 55 · reference data 50 · marketplace listing 45 · forum 40 · model 40 |
| Directness | independently tested 100 · verified 90 · manufacturer-reported 60 · customer-reported 55 · estimated 30 |
| Variant relevance | exact 100 · other variant 60 · product family 40 · brand 20 |
| Independence | independent 100 · unknown 50 · affiliated 30 · seller 25 · manufacturer 20 |
| Freshness | 100 up to 1 year old, falling to 20 at 5 years. 50 when undated |

**Adjustments:**
- Reviews are multiplied by a sample-size factor (≥100: 1.0, ≥30: 0.85, ≥10: 0.65, otherwise 0.4)
  and by a warning-sign factor (low 1.0, medium 0.75, high 0.5).
- Catalogue material ranges are capped at 30, and multiplied by 0.6 when the grade isn't stated.

Mean confidence below 50 makes a result `PROVISIONAL`. The coefficients are configuration and can be
recalibrated.

## 4. Eligibility and safety gates
In order of severity: `EXCLUDED` > `SAFETY_HOLD` > `INSUFFICIENT_EVIDENCE` > `PROVISIONAL` > `ELIGIBLE`.

- **`EXCLUDED`:** an active recall, a failed mandatory safety requirement, or a failed independent
  safety test.
- **Category gate:** no safety evidence → `SAFETY_HOLD` (electronics, appliances, tools, automotive,
  personal care, kitchen, baby and children) or `PROVISIONAL` (other categories). A safety score
  below 40 → `SAFETY_HOLD`.
- A mandatory requirement for the buyer's country that has no evidence gets the same treatment as
  the gate. Requirements rarely checkable from public information (for example UN 38.3 battery
  testing, or REACH) make the result provisional instead.
- A requirement met by a manufacturer's statement scores 60 ("declared"). Only an independent
  record or test scores 100 ("verified").
- Serious safety complaints in reviews make a result at least `PROVISIONAL` until they're checked.
- Personal priorities change the weights for the personal ranking, but never the gates.

## 5. Rankings
- **Overall:** by status, then score.
- **Within budget:** only products inside the budget.
- **Personal:** by the user's priority weights; 10% of the weight stays with unnamed dimensions.
- **Best by dimension:** among recommendable products with dimension confidence of at least 40,
  inside the budget.

## 6. What the scores are not
- Category weights (profiles v0.1) are **uncalibrated hypotheses** from the V2 specification. They
  need expert review and user research before anyone calls them validated.
- Ergonomic fit rules are simplified guidance, not a fitting.
- Safety requirement lists are pointers reviewed on a stated date, not legal advice.
- Review signals are warning signs, not findings of fraud.
