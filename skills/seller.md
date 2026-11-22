# Seller mode

For sellers, dropshippers and e-commerce founders deciding what to sell.

## Workflow

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
