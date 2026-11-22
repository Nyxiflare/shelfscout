# Quick compare (shopper)

For everyday buying questions: which listing, is the deal real, can I trust the reviews.
For "which is actually best made / will last / fits me", use [evaluate.md](evaluate.md) instead.

## Workflow

1. **Pin down the need (1–3 questions at most):** what it's for, must-haves, budget including
   shipping, where they live (for shipping, tax and import duty), and how soon they need it. If the
   message already says, don't ask.
2. **Find 3–6 real candidates** across marketplaces and brands. Include at least one well-known option
   and one strong value option. Note per listing: marketplace, seller, price, shipping, delivery time,
   return window, rating and count, and whether it's sold by the brand, by the marketplace, or by a
   third-party seller.
3. **Check each candidate:**
   - Fit: score 0–10 against *their* needs, with a one-line reason. This is your judgement; say so.
   - True cost: run `SS landed` (and `SS unit` for consumables) so a cheap item with expensive shipping
     doesn't win by accident. For cross-border orders, estimate duty and tax for their country and say
     it's an estimate.
   - Deal check: when there's a "was" price or a sale badge, run `SS deal` with any price history you
     can see. It judges two things separately: the **price** (good/fair/weak/poor vs. what it usually
     costs) and the **discount claim** (supported/not supported/unverifiable). Report both, e.g. "good
     price, but the 38% discount is fake: the real saving is 11%". A discount from a price that was
     never charged isn't a discount.
   - Reviews: read the 1–3 star reviews (they tell you how it actually fails), and run `SS reviews` on a
     sample when you can collect one. If you have no sample, leave `review_warning` out (it counts as
     neutral) and say the reviews weren't checked. Look for reviews about a different product (listing merges),
     sudden bursts, and identical wording.
   - Seller trust: rating and volume, how long they've been selling, return policy, and red flags
     (brand-new seller with a too-low price, "no returns", off-platform payment requests, a counterfeit
     risk for branded goods sold by unrelated sellers).
   - Look-alikes: many listings are the same factory product under different brand names. Say so when
     you see it. The cheapest identical one is often the right pick, with a trusted seller.
4. **Rank:** write the candidates to a JSON file and run `SS compare`. Put the buyer's `tax_pct` (and
   `duty_pct` for imports) once at the top of the file. An open-box, used or resold copy of a product
   listed elsewhere can borrow that listing's reviews with `"same_product_as": "<other name>"`, and
   should set `"condition"`. Over-budget listings always rank last; mention any that would otherwise
   have won. (`--html` for a visual page the
   user can open). Change the weights if the user said what matters most ("I care about quality, not
   price" means more weight on fit and reviews).
5. **Recommend** in the shopper output format below, including the **Avoid** list with reasons.

### Shopper output format

```
## Best picks: [what], checked [date, and time if you checked live]

**Best overall:** [name] · [marketplace] · [total to door] · [why, in one line]
**Best value:** [name] · … · [why]
**Avoid:** [name] · [the specific reason: fake discount / review burst / no returns / counterfeit risk]

| Listing | Total to door | Fit | Seller trust | Reviews | Deal | Score |
|---|---|---|---|---|---|---|
| … | … | … | … | … | good price · claim fake (real saving 11%) | … |

**Watch out for:** [the 1–3 things to check before paying]
**What I couldn't verify:** [prices not visible, no price history, small review sample…]
```

Links are fine when they're the marketplace's plain product page. Never add affiliate or tracking
parameters, and never claim a commission-free link is one or the other.

## Data formats

`listings.json` (for `compare`):
```json
{"currency": "USD", "budget": 120, "tax_pct": 8.25, "listings": [
  {"name": "Brand A kettle", "marketplace": "Amazon", "url": "https://…", "price": 89.99, "shipping": 0,
   "fit": 8, "rating": 4.6, "review_count": 3400, "review_warning": "low",
   "seller_rating_pct": 98, "returns_days": 30, "sold_by_brand_or_marketplace": true},
  {"name": "Brand A kettle (open box)", "marketplace": "eBay", "price": 61, "shipping": 6, "fit": 8,
   "condition": "open box", "same_product_as": "Brand A kettle", "seller_rating_pct": 99.4, "returns_days": 30}]}
```
Only `price` is required. `fit` (0–10) is your judgement of the user's needs. `review_warning` is the
level from `SS reviews` (low/medium/high). Leave it out when there's no sample. Top-level `tax_pct` and
`duty_pct` apply to every listing that doesn't set its own.

`reviews.json` (for `reviews`): a list of `{"rating": 5, "date": "2026-10-01", "verified": true, "text": "…"}`.

`prices.json` (for `deal --history`): a list of `{"date": "2026-09-01", "price": 99}` from price history
you could actually see.
