# ShelfScout V2 migration plan

- **Status:** approved 2026-11-22. Phases 1-7 done in 2.0.0a1 (see CHANGELOG). Phase 8 not started: it needs PostgreSQL/Docker, which aren't installed, and real-user validation first, as the plan says.
- **Scope notes for 2.0.0a1:** the eval set starts with 12 evidence-labelling cases and 3 synthetic engine examples, not 30 judgement cases. Phase 5 safety requirements cover US, EU, UK and India for electronics, appliances, kitchen and baby products, plus the three demo categories.
- **Branch:** `feature/shelfscout-v2`. `main` stays as released v1 until V2 passes its release checks.

Each phase ends with: implementation, tests passing, docs updated, limitations written down, and a short report (files changed, test counts, what's left). Nothing is called complete on placeholder code.

## Phase 1: Core foundation (stdlib engine)
**Builds:** `src/shelfscout/core` (dataclass models for Product, Variant, Listing, EvidenceSource, EvidenceItem, EvidenceClaim, DimensionScore, Evaluation), units (length, mass, pressure, temperature, MPa/GPa…), money (all ISO 4217 minor units, FX with a source and date), the evidence statuses, and the category profile loader with 12 top-level profiles from the specification (v0.1, marked uncalibrated).

**Acceptance criteria:**
- Every profile's weights sum to 100. This is tested.
- Comparing incompatible units raises an error.
- Every claim needs a status and a source; `UNKNOWN` is explicit.
- Existing 31 tests still pass, unchanged.

## Phase 2: Scoring, confidence, eligibility (fixes audit G-01, G-02, G-06)
**Builds:**
- dimension scoring from evidence only
- weight renormalisation with missing dimensions listed
- the confidence model (config coefficients)
- coverage
- eligibility states and mandatory safety gates
- rankings: overall, per price band (in the user's currency), best-per-dimension and personalised (gates stay on)
- `algorithm_version` and `profile_version` on every result

**Acceptance criteria:**
- A missing dimension never produces a score.
- A failed or missing mandatory safety check never yields `ELIGIBLE`.
- Over-budget products never win a budget ranking.
- Personal weights can't override a gate.
- All scores stay within 0–100.
- `compare` keeps working: the new output plus `--legacy-scoring`.

## Phase 3: Review intelligence (G-08)
**Builds:**
- a structure for aspects and complaints: the agent extracts `{aspect, sentiment, severity, quote}` per review, and the engine aggregates
- positive and negative experience scores and complaint recurrence, with a correct denominator
- severity and recency trends
- long-term ownership signals
- the existing authenticity heuristics kept as a separate, explainable "review confidence"

**Acceptance criteria:**
- Duplicate reviews count once.
- Complaint shares state their denominator.
- Authenticity is always phrased as warning signs.
- Labelled fixtures pass.

## Phase 4: Materials and engineering
**Builds:**
- a material catalogue with seed families (steels, aluminium alloys, ABS, PC, PP, nylon, EVA/TPU foams, MDF/plywood, leather/textiles, glass)
- **typical property ranges with a source per value, licence permitting**
- application-specific suitability (office-chair frame, phone housing, shoe midsole and outsole, cookware)
- a construction checklist (thickness, joining, fasteners, finish) that only scores what evidence states

**Acceptance criteria:**
- No grade is assumed from a family name.
- Suitability returns "incomplete" when key properties are missing.
- Every value carries its source and test conditions.

## Phase 5: Durability, ergonomics, safety, service
**Builds:**
- **Durability evidence streams:** manufacturer claim, independent test, customer-reported ownership time, and repairability and parts, with no point lifespans.
- **Ergonomics profiles:**
  - chairs: seat height and depth, lumbar, armrests, recline, size range against user dimensions
  - shoes: fit, drop, cushioning, toe box
  - phones: weight, size, reach
- **Safety:** jurisdiction-aware requirements (US, EU/UK, India first), certification records with verification status, and a recall-check step.
- **Service:** warranty terms and coverage evidence.

**Acceptance criteria:**
- Ergonomic fit is computed from the user's measurements when given.
- Subjective comfort is reported separately.
- A certification logo alone is `MANUFACTURER_REPORTED`, not `VERIFIED`.

## Phase 6: Identity, price, TCO, reports, persistence
**Builds:**
- conservative variant matching (model number or GTIN, otherwise an agent-confirmed match with evidence)
- TCO (purchase + maintenance + repairs + consumables + energy where evidenced)
- SQLite store with immutable evaluations and product profiles
- Markdown, JSON and HTML reports (overall verdict first, then dimensions with evidence, unknowns and trade-offs)

**Acceptance criteria:**
- Different variants never merge without evidence.
- Re-running an old evaluation reproduces it.
- Every displayed technical claim links to evidence.

## Phase 7: Agent skill integration and evaluation set (G-13)
**Builds:**
- SKILL.md as a router for shopper / evaluate / seller, with internal workflow guides
- three worked examples (office chair, smartphone, running shoes), with synthetic fixtures labelled as synthetic
- an `evals/` set (start with 30 cases, grow toward 100)
- a fresh-agent end-to-end run per category
- Codex compatibility check (instructions only; no Claude-specific tools required)

**Acceptance criteria:**
- Three categories run through the same pipeline with three profiles.
- Zero invented specs or certifications in the eval runs.
- Seller mode is unchanged and still passes its tests.

## Phase 8 (optional, after validation): platform
**Builds:**
- `pip install shelfscout[platform]`: Pydantic API schemas, FastAPI endpoints from the specification, PostgreSQL through SQLAlchemy/Alembic with the same schema, Docker compose, and CI on 3 operating systems
- later, a Next.js frontend

**Only after:** Phases 1–7 are released and real users have tried the evaluations.

## Release plan
| Release | Contains | Proves |
|---|---|---|
| v2.0-alpha | Phases 1–2 | Evidence, profiles, gates and honest scoring |
| v2.0-beta | + Phases 3–5 | Reviews and engineering dimensions |
| v2.0 | + Phases 6–7 | Full shopper evaluation on 3 categories, persistence, skill router |
| v2.1+ | Phase 8, more categories and adapters | Platform and API |

Each release is merged from `feature/shelfscout-v2` into `main` only after: all tests pass, `git diff` is reviewed, a clean `npx skills add` install works, and the CHANGELOG is updated.

## Rough effort (planning estimate, not a commitment)
Phases 1–2: 1–2 sessions · Phase 3: 1 session · Phase 4: 1–2 sessions (mostly sourcing material data) · Phase 5: 2 sessions · Phase 6: 1–2 sessions · Phase 7: 1–2 sessions · Phase 8: 2–4 sessions.

## Decisions needed before Phase 1
1. **ADR-1:** keep the installed skill free of extra Python packages, with Pydantic, FastAPI and PostgreSQL as an optional platform layer later. *(Recommended.)*
2. **ADR-2:** SQLite locally first, PostgreSQL in Phase 8. *(Recommended.)*
3. **Jurisdictions for the first safety profiles:** US, EU/UK and India. *(Recommended, matching the global scope.)*
4. **First categories:** office chairs, smartphones and running shoes. *(As the specification suggests.)*
