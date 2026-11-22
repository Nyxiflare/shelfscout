# ShelfScout: a Claude skill for finding good products in online marketplaces

Fake discounts, review farms, look-alike listings, surprise shipping and fees: online marketplaces make it hard to tell a good product from a well-marketed one. ShelfScout does the homework and shows its evidence.

**Two modes:**

### 🛒 Shopper: "which one should I buy?"
> "I want noise-cancelling headphones for my commute, about $100 including shipping. Which one? Is this 65%-off deal real?"

- Compares listings **across marketplaces** (Amazon, eBay, Etsy, Walmart, AliExpress, Temu…) by **true cost to your door**: shipping, tax and import duty included.
- Checks whether a **discount is real** against the prices actually charged before.
- Flags **unreliable reviews**: bursts, near-identical wording, uniform 5-stars, unverified purchases. It reads the 1–3★ reviews so you know how a product actually fails.
- Checks **seller trust**: who really sells it, return policy, counterfeit and scam red flags.
- Recommends **best overall, best value, and what to avoid**, with an optional visual comparison page.

### 📦 Seller: "is this worth selling?"
> "Leak-proof bento box on Amazon with FBA. Supplier $4.80, sells for $24.99. Worth it?"

- **Profit per unit** after marketplace fees, fulfilment, ads and returns, plus the most ads can cost before you lose money.
- **Demand and competition** from visible signals, clearly labelled as proxies.
- **The improvement angle:** recurring complaints in competitors' bad reviews that a better product could fix.
- **Risk flags:** trademarks and patents, gated categories, safety certifications, batteries, fragility, return-prone sizing, price wars.
- A **go / test small / skip** verdict, and the cheapest way to test.

## Install

```bash
npx skills add Nyxiflare/shelfscout
```

Or copy this folder to `~/.claude/skills/shelfscout`.

## How it gets its data

ShelfScout uses what your Claude session can see: product pages and details you share, and web search or a browser if your setup has them. It reads listings the way a careful shopper would. It doesn't bulk-scrape marketplaces or get around logins or CAPTCHAs, and it **never invents** prices, ratings or sales numbers. Anything it can't see, it says it can't see.

The math (landed cost, unit price, deal check, review signals, ranking, seller margins) runs in a small local Python script, so the numbers are exact. Fee presets are typical published rates with the date they were checked; ShelfScout asks Claude to confirm current fees before quoting final numbers.

## Requirements

- Claude Code (or any agent that supports skills)
- Python 3.9+ (standard library only)
- Optional: web search or browser tools, for finding listings itself

## Tests

```bash
python -m unittest discover -s tests
```

Sample cases for both modes are in [`examples/`](examples/).

## Limits

- Prices, stock and sellers change constantly: confirm at checkout.
- Review checks are **warning signs, not proof** that reviews are fake.
- Seller numbers are estimates of unit economics, not financial advice. Real sales volume and search demand need dedicated tools.
- Compliance notes point to the relevant rules; they aren't legal or certification advice.
- No affiliate links.

## License

MIT. See [LICENSE](LICENSE).
