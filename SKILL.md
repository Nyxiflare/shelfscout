---
name: shelfscout
description: Finds genuinely good products in online marketplaces (Amazon, eBay, Etsy, Walmart, AliExpress, Temu and similar), in two modes. Shopper mode compares listings across marketplaces by true cost to the door, fit to the person's needs, seller trust, review reliability and whether a "deal" is real, then recommends what to buy and what to avoid. Seller mode checks whether a product is worth selling, with demand and competition signals, profit after marketplace fees, fulfilment, ads and returns, and risk flags (brand/IP, restricted categories, compliance, fragility, seasonality). Use this whenever someone wants to buy something online and asks which one, whether a deal or reviews are trustworthy, or compares listings; and whenever a seller, dropshipper or e-commerce founder asks what to sell, whether a product is profitable, or wants product research, even if they never say "ShelfScout".
---

# ShelfScout

Online marketplaces make it hard to tell a good product from a well-marketed one: fake discounts,
review farms, look-alike listings, hidden shipping and fees. ShelfScout does the homework and shows
its evidence, so the person can decide in a few minutes and trust the answer.

You do the research and judgement. `scripts/shelf.py` does the math (landed cost, unit price, deal
check, review signals, scoring, seller margins), so numbers are exact and repeatable. Call it by its
full path in this skill's folder (the folder you were given when the skill loaded), for example
`python "<skill folder>/scripts/shelf.py" margin ...`. Below, `SS` stands for that command.

| Command | Use it to |
|---|---|
| `SS landed --price 49.99 --shipping 5 --tax-pct 8.25 [--duty-pct 6]` | True cost to the door |
| `SS unit --price 12.99 --qty 24 --unit-name can [--per 100]` | Compare packs of different sizes fairly |
| `SS deal --price 79 --was 129 [--history prices.json]` | Is the "discount" real? |
| `SS reviews reviews.json` | Warning signs of unreliable reviews |
| `SS compare listings.json [--weights fit=40,value=25,trust=20,reviews=15] [--html out.html]` | Rank listings for a shopper |
| `SS margin --sell 29.99 --cost 6.50 --inbound 1.20 --marketplace amazon-us --fulfil 5.40 --ads-pct 10 --returns-pct 5` | Seller profit per unit (`--inbound` = shipping per unit to you or the warehouse) |
| `SS fees` | Fee presets and when they were checked |

## Pick the mode

- **Shopper:** "which one should I buy", "is this a good deal", "are these reviews real", "find me
  the best X under $Y". Go to the shopper workflow.
- **Seller:** "what should I sell", "is this profitable", "product research", "dropshipping", "FBA".
  Go to the seller workflow.
- If it's unclear, ask one question: *"Are you buying this, or thinking of selling it?"*

## Where the data comes from (read this first)

Use what the session can actually do, in this order:
1. **Pages and details the user gives you:** links, screenshots, pasted listings or reviews.
2. **Web search and page reading tools,** if available, to find listings across marketplaces and read
   product pages, the marketplace's own price history where shown, and independent reviews.
3. **A browser tool,** if available, to open the listing pages a person would open.

Rules that keep this honest and within the sites' terms:
- Look at listings the way a careful shopper would. Never mass-download a marketplace, get around a
  login, CAPTCHA, rate limit or robots rule, or use a bot account. If a site blocks you, say so and ask
  the user to paste the details instead.
- **Never invent** prices, ratings, review counts, sales numbers or fees. If a number isn't observed,
  say "not visible" and work without it. Estimates are labelled as estimates, with how you made them.
- Prices and stock change by the hour. Give the time you checked, and tell the user to confirm the price
  at checkout.
- Sales volume and search demand usually aren't visible to you. For sellers, use visible proxies
  (review counts and how fast they grow, number of competing listings, "bought in past month" badges
  where the marketplace shows them) and say they're proxies. Point to dedicated tools for real numbers.

## Shopper workflow

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

## Seller workflow

1. **Understand the seller:** marketplace(s) and country, budget per order, fulfilment (FBA/WFS/own/
   dropship), whether they need a brand, and what they already sell. Ask only what's missing.
2. **Generate or take candidates.** For "what should I sell", propose 5–10 product ideas tied to a real
   demand signal you can point to (rising searches, many reviews with recurring complaints a better
   product could fix, a gap between marketplaces), not generic "trending products" lists.
3. **For each candidate, look at:**
   - Demand (proxy): review counts of the top listings, how fast they grow, "bought in past month"
     badges if shown, seasonality.
   - Competition: how many serious listings, whether the top results are dominated by big brands or by
     the marketplace itself, how strong their listings are (photos, reviews, price).
   - **The improvement angle:** what recurring 1–3 star complaints a better product could fix. This is
     usually the real opportunity, and the one free skills miss.
   - Margin: run `SS margin` with real or clearly estimated numbers. If the user gives no return rate,
     use about 5% for general goods, 8–10% for electronics, and 15%+ for clothing, shoes and anything
     sized, and say you assumed it. Also run one stress test (a lower price and higher ads), since that's
     where marketplace products usually end up. Check the marketplace's current fee
     page for the category first if you can. The presets are typical rates and can be out of date.
   - Risk flags (see `references/seller-risks.md`): trademarks and patents, restricted or gated
     categories, safety certifications (CE, FCC, UL, UKCA, CPSIA for children's products), batteries and
     liquids, fragile or oversized items, high return rates, and very low prices that invite a price war.
4. **Score each idea** for demand, competition, margin, risk and the strength of its improvement angle
   (low / medium / high, with the reason), then rank them. Be willing to say "none of these is worth it".
5. **Never help** copy a competitor's listing, photos or brand, sell counterfeits or knock-offs of a
   protected design, write fake reviews, or game the marketplace's rules. Suggest the legitimate route
   instead (a better product, original photos, real early reviews through the marketplace's own programs).

### Seller output format

```
## Product check: [idea], [marketplace], checked [date]

| | Signal | Evidence |
|---|---|---|
| Demand | medium | top 5 listings have 1.2K–8K reviews, +~300/month on the leader |
| Competition | high | 3 of the top 5 are big brands; 40+ similar listings |
| Improvement angle | strong | 22% of 1–2★ reviews mention the lid cracking |
| Margin | medium (24%) | $5.90 profit/unit, ROI 110%; ads can reach 37% before a loss |
| Margin, stress test | thin (15%) | at $19.99 with 20% ads |
| Risk | high | food-contact: FDA testing needed; "microwave safe" needs proof |

**Verdict:** go / test small / skip, and why in two lines.
**Cheapest way to test:** [e.g. 100-unit order, one variant, one marketplace]
**What I couldn't see:** [real sales, search volume, supplier quality…]
```

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

## Boundaries

- Recommendations, not guarantees: prices, stock and sellers change.
- Not financial advice for sellers: it estimates unit economics. The user decides what to invest.
- Review signals are heuristics: "warning signs", never "these are fake".
- Product safety and compliance notes are pointers to the right regulation, not certification advice.
