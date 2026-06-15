# Football Intelligence — Decisions
# Football Intelligence Decisions Log

This document records important technical and product decisions.

---

# Decision 001

Date: 2026-06-15

Status: Accepted

Category: Product

Decision:

Project Name = Football Intelligence

Reason:

The project vision extends beyond scouting.

The platform will eventually include:

* AI Scout
* AI Football Intelligence Agent
* AI Director of Football Assistant

The name supports future expansion.

---

# Decision 002

Date: 2026-06-15

Status: Accepted

Category: Product

Decision:

Development will follow an MVP-first strategy.

Roadmap:

MVP 1
→ MVP 2
→ MVP 2.1
→ MVP 3
→ MVP 4
→ MVP 5
→ MVP 6
→ MVP 7

Reason:

Reduce complexity.

Deliver working products incrementally.

---

# Decision 003

Date: 2026-06-15

Status: Accepted

Category: Product

Decision:

Current Development Target = MVP 1

Reason:

Focus on one problem:

Generate AI-powered player profiles.

Avoid building advanced scouting systems too early.

---

# Decision 004

Date: 2026-06-15

Status: Accepted

Category: Frontend

Decision:

Frontend Framework = Next.js

Reason:

* Strong ecosystem
* Excellent TypeScript support
* Good compatibility with AI-assisted development
* Easy deployment

---

# Decision 005

Date: 2026-06-15

Status: Accepted

Category: Backend

Decision:

Backend Framework = FastAPI

Reason:

* Python ecosystem
* Fast development speed
* Excellent API development experience
* Strong analytics integration

---

# Decision 006

Date: 2026-06-15

Status: Accepted

Category: Database

Decision:

Database = PostgreSQL

Reason:

* Production-ready
* Reliable relational database
* Strong analytics support
* Widely used in industry

---

# Decision 007

Date: 2026-06-15

Status: Accepted

Category: Analytics

Decision:

Analytics Stack

* Pandas
* NumPy
* Scikit-Learn

Reason:

Industry-standard data science stack.

---

# Decision 008

Date: 2026-06-15

Status: Accepted

Category: Visualization

Decision:

Visualization Library = Plotly

Reason:

Interactive charts and football analytics dashboards.

Supports future MVP 2.1 requirements.

---

# Decision 009

Date: 2026-06-15

Status: Accepted

Category: AI

Decision:

Use a model-agnostic AI layer.

Current:

* OpenAI API
* Anthropic API

Future:

* Fine-tuned models
* Local models

Reason:

Avoid vendor lock-in.

---

# Decision 010

Date: 2026-06-15

Status: Accepted

Category: Architecture

Decision:

Documentation-first development.

Order:

1. PROJECT_MASTER.md
2. ROADMAP.md
3. TASKS.md
4. DECISIONS.md
5. ARCHITECTURE.md
6. API_SPEC.md
7. Implementation

Reason:

Reduce architectural mistakes and scope creep.

# Decision 011

Date: 2026-06-15

Status: Accepted

Category: Data Engineering

Decision:

MVP 1 will use a static FBref-based dataset as the primary data source.

The project will not implement automated scraping or a live ingestion pipeline during MVP 1.

Reason:

The primary objective of MVP 1 is to build and validate the AI Player Profile Generator.

Building a production-grade data ingestion pipeline would significantly increase complexity and delay delivery.

Using a curated FBref dataset allows the project to focus on:

* Player Search
* Player Profiles
* Season Statistics
* AI Analysis
* Similar Player Recommendations

Future Plan:

MVP 1:
Static Dataset

MVP 2:
Dataset Refresh Process

MVP 3:
Automated Data Ingestion Layer

Long-Term:
Multi-source football data platform integrating:

* FBref
* StatsBomb
* Transfermarkt

Expected Benefits:

* Faster MVP delivery
* Lower technical complexity
* Easier debugging
* Better learning ROI
* Reduced infrastructure requirements

# Decision 012

Date: 2026-06-15

Status: Accepted

Category: Data

Decision:

Preferred Foot remains part of the MVP 1 player profile specification.

However, the field may be unavailable in the initial MVP 1 dataset.

Reason:

FBref does not provide Preferred Foot in its standard exported datasets.

Removing the field from the specification would create future compatibility issues when additional data providers are introduced.

Future Plan:

MVP 1:

* Preferred Foot may be null
* Preferred Foot may display as "Unknown"

MVP 2+:

* Integrate Transfermarkt or other supplementary sources
* Populate Preferred Foot when available

Impact:

The player profile structure remains stable while allowing gradual data enrichment.

Expected Benefits:

* Avoids schema changes later
* Maintains roadmap consistency
* Supports future Transfermarkt integration

# Decision 013

Date: 2026-06-15

Status: Superseded by Decision 014

Category: Data Engineering

Note:

The original plan was to obtain the MVP 1 dataset via manual CSV export directly
from FBref. After further evaluation, a community-maintained Kaggle dataset sourced
from FBref was identified as a more practical and maintainable alternative. It
eliminates manual per-table export steps, provides a pre-merged file covering all
required statistics, and is already in use across the football analytics community.
This decision is retained for historical record only. See Decision 014.

Decision:

MVP 1 dataset will be obtained via manual CSV export directly from FBref.

The following four FBref stat tables will be exported for Big 5 European Leagues, season 2024-25:

- Standard Stats
- Shooting Stats
- Passing Stats
- Possession Stats

Reason:

- Directly sourced from FBref
- No automated scraping
- No third-party dependency
- Lowest complexity
- Consistent with Decision 011

Future Plan:

MVP 1: Manual export
MVP 2: Manual refresh
MVP 3: Automated ingestion pipeline

---

# Decision 014

Date: 2026-06-15

Status: Accepted

Category: Data Engineering

Decision:

MVP 1 will use the following Kaggle dataset as the static player data source:

Dataset: Football Players Stats (2025-2026)
Maintainer: hubertsidorowicz
URL: https://www.kaggle.com/datasets/hubertsidorowicz/football-players-stats-2025-2026
File: players_data-2025_2026.csv
Stored at: data/raw/players_data_raw_2025_26.csv

The file is downloaded once and committed to the repository.
It is not re-downloaded during MVP 1 development.

Reason:

This dataset satisfies all MVP 1 requirements simultaneously:

* FBref is the original data source — authoritative
* Covers Big 5 European Leagues — confirmed
* Season 2025-26 — confirmed and current
* All required DATA_SCHEMA.md fields are present in a single pre-merged file
* Free, no API key required
* No scraping by this project — consistent with Decision 011
* Community-tested (Kaggle usability score 10.0)

This supersedes Decision 013. Manual FBref CSV export is eliminated for MVP 1.

Season Note:

This decision updates the target season from 2024-25 (referenced in Decision 013
and original DATA_SCHEMA.md) to 2025-26. DATA_SCHEMA.md and DATA_SOURCES.md
are updated accordingly.

Known Limitation:

FBref player_id is not confirmed to be present in the Kaggle dataset.

If player_id is absent after inspection:

* Use player_name + club + season as the composite key for MVP 1
* Address player_id in MVP 2 when the data source is revisited

Future Plan:

MVP 1: Kaggle static download (this decision)
MVP 2: Evaluate direct FBref CSV export or dataset refresh process
MVP 3: Automated data ingestion layer

---

END OF DOCUMENT
