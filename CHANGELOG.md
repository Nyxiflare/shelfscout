# Changelog

## 2.0.0a1, 2026-11-22: the evaluation engine

### Added
- **`src/shelfscout`**, a standard-library engine with:
  - units that refuse incompatible comparisons
  - money with ISO 4217 minor units and sourced, dated exchange rates
  - evidence statuses and provenance rules
  - 15 versioned category profiles
  - confidence, coverage, eligibility and safety gates
  - review aggregation, a materials catalogue and application suitability
  - ergonomic fit, jurisdiction-aware safety requirements, features and tested-vs-advertised checks
  - identity matching, TCO, an append-only SQLite history, and Markdown/JSON/HTML reports
- **CLI commands:** `evaluate`, `profile`, `materials`, `identity`, `tco`, `history`.
- **SKILL.md** is now a router for three modes (quick compare, deep evaluation, seller), with guides in `skills/`.
- Public scoring methodology, synthetic examples for three categories, an evidence-labelling eval set, and the Phase 0 audit and architecture docs.

### Unchanged
- The v1 commands (`landed`, `unit`, `deal`, `reviews`, `compare`, `margin`, `fees`), their JSON formats and their 31 tests.
- `compare` keeps its v1 quick scoring. The neutral defaults the audit flagged (G-01) apply only there; `evaluate` never scores missing evidence.

### Known gaps
- Category weights are uncalibrated (v0.1).
- The platform layer (Phase 8: FastAPI, PostgreSQL, Docker, frontend) isn't built.
- No real-user validation yet.
