# ShelfScout V2 architecture

**Status:** proposal for approval (Phase 0). Nothing here is built yet.

## Goal

Evolve ShelfScout from "a calculator plus agent instructions" into an **evidence-based product evaluation engine**. It judges products on how they perform to own (materials, durability, ergonomics, safety, service, real customer experience, value), and every number carries its evidence and confidence. Seller mode stays.

## Key decisions

### ADR-1: Two layers, and the installed skill stays dependency-free
- **Layer 1 (skill + core engine):** pure Python standard library: `dataclasses`, `decimal`, `sqlite3`, `json`. This is what `npx skills add Nyxiflare/shelfscout` installs, so it runs on any machine with Python 3.9+.
- **Layer 2 (platform, optional):** Pydantic API schemas, FastAPI, SQLAlchemy/Alembic and PostgreSQL. These are installed with `pip install shelfscout[platform]` for people who want the API or a shared database.
- **Why:** the specification asks for Pydantic, PostgreSQL and Docker. Making them required for the skill would stop most users from running it, and none of them are on the development machine today. Keeping the core in the standard library means one engine serves both layers. The platform wraps the core; it never re-implements it.

### ADR-2: Local storage is SQLite with the same schema; PostgreSQL later
- The core engine writes evaluations, evidence and product profiles to a local SQLite file (`./shelfscout-data/shelfscout.db`), using a schema that maps one-to-one to the PostgreSQL tables in the specification. UUIDs are text, JSONB becomes JSON text, and timestamps are ISO-8601 in UTC.
- PostgreSQL arrives in the platform phase through Alembic migrations generated from the same table definitions.
- **Why:** persistence and reproducible evaluations are useful now; database servers aren't.

### ADR-3: The engine owns every rule and number; the agent supplies extracted evidence
| Deterministic engine (Python, tested) | Agent (Claude or Codex) |
|---|---|
| Unit conversion, currency minor units | Finding listings, specs, reviews, manuals and recalls within site terms |
| Scores, weights, confidence, coverage | Extracting claims from text into evidence records |
| Eligibility and safety gates | Classifying review aspects and complaints |
| Rankings (overall, per price band, per use case, personalised) | Judging fit to a person's needs, with a reason |
| Material suitability from stored properties | Explaining results in plain language |
| Price, deal, TCO, seller margins | |

The agent never writes a score directly. It writes **evidence**, and the engine turns evidence into scores. An agent summary is never stored as evidence.

### ADR-4: Evidence is the unit of truth
Every value used in a score is an `EvidenceClaim` with these fields:
- claim type
- value and unit
- variant ID
- status: `VERIFIED`, `INDEPENDENTLY_TESTED`, `MANUFACTURER_REPORTED`, `CUSTOMER_REPORTED`, `ESTIMATED` or `UNKNOWN`
- source (type, URL, independence)
- observed date
- limitations
- a content hash of the raw source

Raw evidence never changes after it's stored. A dimension with no qualifying evidence has **no score**. It's reported as unknown and lowers coverage and eligibility, never the average. This replaces today's neutral defaults (audit G-01).

### ADR-5: Scoring in four layers, all versioned
1. **Dimension scores, 0–100:** only from evidence, using category-specific scoring functions.
2. **Weighted overall score:** over dimensions that have scores, with weights renormalised and missing dimensions listed.
3. **Confidence per dimension:** 0.30 source quality + 0.25 directness + 0.20 variant relevance + 0.15 independence + 0.10 freshness. The coefficients are config, not constants.
4. **Eligibility:** `ELIGIBLE`, `PROVISIONAL`, `INSUFFICIENT_EVIDENCE`, `SAFETY_HOLD` or `EXCLUDED`. Mandatory safety gates per category override any score and any user weights.

Every evaluation stores `algorithm_version` and `profile_version`, so old rankings can be reproduced.

### ADR-6: Category profiles are data files
`profiles/<category>.json` holds the dimension weights (they must sum to 100), mandatory gates, relevant properties, ergonomic criteria and standards references. The specification's tables are version `0.1` and labelled "uncalibrated hypothesis" in the profile and in every report.

### ADR-7: Product identity is conservative
Variants are separate unless matched by model number or GTIN/EAN/UPC, or confirmed by the agent with recorded evidence. A variant never silently inherits another variant's reviews or specs. Borrowing has to be explicit and is shown in the report (this generalises today's `same_product_as`).

### ADR-8: Backward compatibility
`scripts/shelf.py` keeps all seven current commands and their JSON formats. They become thin wrappers over the engine. `compare` gains new output (dimension scores, confidence, eligibility) and stops using neutral defaults, behind a documented scoring version. A `--legacy-scoring` flag keeps v1 behaviour for one release.

### ADR-9: Data sources through adapters, user data first
- Adapter interface: `search`, `get_product`, `get_reviews`, `get_price_history` and `capabilities()`. Each adapter declares only the capabilities it really has.
- The first adapters are **user-provided data** (pasted JSON and files) and **agent-collected data**.
- Official APIs (for example Keepa or marketplace partner APIs) are optional adapters that need the user's own keys.
- No scraping that bypasses terms, logins or CAPTCHAs. Mock adapters are used for tests.
- Retrieved pages and reviews are untrusted data: instructions inside them are never followed.

## Package layout (target)

```
shelfscout/
├── SKILL.md                      # router: shopper, evaluate, seller
├── skills/                       # internal workflow guides the router points to (not separately installed)
│   ├── evaluate.md  reviews.md  materials.md  ergonomics.md  safety.md  seller.md
├── scripts/shelf.py              # backward-compatible CLI → engine
├── src/shelfscout/               # stdlib-only core engine
│   ├── core/       models.py units.py money.py evidence.py errors.py
│   ├── profiles/   loader.py  *.json (category profiles)
│   ├── scoring/    dimensions.py confidence.py eligibility.py ranking.py
│   ├── intelligence/ reviews.py materials.py durability.py ergonomics.py safety.py service.py price.py
│   ├── identity/   matching.py
│   ├── store/      sqlite.py schema.sql
│   ├── adapters/   base.py userdata.py mock.py
│   ├── reports/    markdown.py json_report.py html.py
│   └── seller/     margin.py opportunity.py
├── platform/                     # optional extras: API, Postgres, Docker (later phase)
├── data/materials/               # seed material families with sourced typical ranges
├── references/                   # methodology docs (public scoring methodology)
├── evals/                        # labelled cases for judgement quality
├── examples/ office-chair/ smartphone/ running-shoes/ headphones/ seller-lunchbox/
└── tests/ unit/ regression/ fixtures/
```

## First demonstration categories
Office chairs (ergonomics-led), smartphones (electronics and engineering), and running shoes (human fit and wear). They test three different evaluation approaches against one pipeline.
