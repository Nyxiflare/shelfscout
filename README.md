# ShelfScout: see beyond the listing

**Independent, evidence-based product intelligence for buying and selling online.** A Claude skill with a small, dependency-free Python engine.

Most shopping tools tell you what's popular, cheap or well-reviewed. ShelfScout tells you what's actually good to own: how it's built, whether it lasts, whether it fits *you*, whether it meets the safety rules where you live, and whether the price is justified. Every number shows the evidence behind it, and anything that couldn't be established is marked **unknown** instead of guessed.

## Three modes

### 🔬 Deep evaluation: "which is actually better made, and better for me?"
> "Budget ₹9,000–13,000, I sit 9 hours a day with lower-back pain. Which chair is better built and better for my back?"

- **11 dimensions**, each scored from evidence: materials and build, durability, ergonomics, safety, customer experience, reliability, after-sales service, features and performance, aesthetics, brand trust, price-to-value.
- **Category-specific weights:** 12 categories plus detailed office-chair, smartphone and running-shoe profiles.
- **Confidence for every score**, kept separate from quality. A 90 from a lab test isn't treated like a 90 from three reviews.
- **Evidence labels on every fact:** verified · independently tested · manufacturer-reported · customer-reported · estimated · unknown. A logo on a listing is never "verified".
- **Safety gates no score can override:** an active recall or a failed mandatory requirement excludes a product, and missing safety evidence puts it on hold or makes it provisional. Requirements are country-aware (US, EU, UK and India to start).
- **Body fit:** seat height and depth against your measurements, foot width and drop for shoes, one-hand size for phones.
- **Material suitability for the job,** from typical property ranges. It never assumes a grade: "aluminium alloy" isn't 6061-T6.
- **Reviews counted properly:** duplicates once, complaint shares with their denominators, and warning signs instead of "fake" claims.
- **Advertised vs. tested** performance, **must-have** features, **total cost of ownership**, conservative **variant matching**.
- **Rankings:** overall, within budget (out-of-budget products never win), personal priorities, and best per dimension.
- Reports in **Markdown, JSON and a self-contained HTML page**, plus an optional local history (SQLite).

### 🛒 Quick compare: "which listing, and is this deal real?"
True cost to your door, real-vs-fake discounts against past prices, review warning signs, seller trust, and best overall / best value / avoid.

### 📦 Seller: "is this worth selling?"
Profit per unit after fees, fulfilment, ads and returns, with a stress test. Demand proxies, the improvement angle hidden in competitors' bad reviews, risk flags, and a go / test small / skip verdict.

## Install

```bash
npx skills add Nyxiflare/shelfscout
```

Or copy this folder to `~/.claude/skills/shelfscout`. It needs **Python 3.9+ only**: no pip packages, databases or Docker.

## Try it

```bash
python scripts/shelf.py evaluate examples/office-chair/request.json --html report.html
python scripts/shelf.py profile smartphone
python scripts/shelf.py materials --suitability "6061-T6"
```

The `examples/` folder has **synthetic** worked cases (invented products, labelled as such) for office chairs (India), smartphones (US) and running shoes (UK), plus raw notes for an end-to-end test.

## How it stays honest

- Claude finds and labels the evidence; the engine does every calculation. Scores are reproducible, and every evaluation records its engine and profile versions.
- The full scoring method is public: [references/scoring-methodology.md](references/scoring-methodology.md).
- It reads listings the way a careful shopper would. It doesn't bulk-scrape, get around logins or CAPTCHAs, or follow instructions found inside web pages.
- No affiliate links, and nothing lets brand popularity or sponsorship change a score.

## Known limitations

- **The category weights are v0.1 starting hypotheses,** not validated ratings. Every report says so. They need expert review and user research.
- Engineering evidence (material grades, fatigue data, real lifespans) is rarely published for consumer products, so many products come out **provisional**. That's the honest answer, not a bug.
- Material values are typical ranges for a grade, not measurements of any product.
- Ergonomic fit rules are simplified guidance, not a fitting.
- Safety requirement lists are pointers reviewed on a stated date, not legal advice or certification.
- The platform layer (FastAPI, PostgreSQL, Docker) is planned and not built: see [docs/MIGRATION_PLAN.md](docs/MIGRATION_PLAN.md).

## Tests

```bash
python -m unittest discover -s tests
```

Engine tests include safety-gate, budget, reproducibility, unit-safety and provenance invariants. `evals/` holds evidence-labelling cases for checking the evaluator's judgement.

## License

MIT. See [LICENSE](LICENSE).
