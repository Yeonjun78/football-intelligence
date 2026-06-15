# Football Intelligence Data Sources

Version: v0.1

Status: Active

---

# Purpose

This document defines the football data sources used by Football Intelligence.

The goal is to establish a scalable data strategy that supports MVP 1 through MVP 7.

---

# Data Strategy

Current Strategy:

Single Primary Data Source

Reason:

* Faster development
* Simpler architecture
* Easier maintenance
* Better data consistency

Future Strategy:

Primary Data Source

*

Advanced Analytics Data Source

---

# MVP 1 Data Source

## Selected Source

FBref (via Kaggle dataset)

## Season

2025-26

## Acquisition Method

Kaggle dataset by hubertsidorowicz:
Football Players Stats (2025-2026)

File downloaded once and stored as a static file at:
data/raw/players_data_raw_2025_26.csv

See Decision 014.

## Status

Primary Data Source — Downloaded and Inspected

## Confirmed File Structure

Data rows: 2,839
Total columns: 102
Header rows: 1 (ETL pipeline pre-resolved FBref two-row header)

## Confirmed Present (MVP 1)

* Player (player_name)
* Nation (nationality)
* Pos (position)
* Squad (club)
* Comp (competition)
* Age (age)
* MP (appearances)
* Min (minutes_played)
* Gls (goals)
* Ast (assists)
* G-PK (non_penalty_goals)

## Confirmed Absent (MVP 2 Deferred)

* xG — not in file
* npxG — not in file
* xAG — not in file
* Cmp% — not in file
* PrgP — not in file
* PrgC — not in file
* player_id — not captured by ETL pipeline

## Reason

FBref provides:

* Player Information
* Season Statistics
* League Coverage
* Historical Data

Suitable for MVP 1:

* Player Profiles
* Player Search
* Basic Season Statistics
* AI Analysis

---

# MVP 1 Required Data

## Player Information

* Name
* Age
* Nationality
* Club
* Position
* Preferred Foot

## Performance Statistics

* Appearances
* Minutes Played
* Goals
* Assists
* xG
* xA
* Pass Completion %
* Progressive Passes
* Progressive Carries

---

# Alternative Sources Evaluated

## Understat

Strengths:

* xG
* xA
* Shooting Data

Weaknesses:

* Limited scope
* Less suitable as primary source

Decision:

Not selected for MVP 1

---

## StatsBomb Open Data

Strengths:

* Event Data
* Professional Analytics
* Scouting Applications

Weaknesses:

* Limited competition coverage
* Higher complexity

Decision:

Reserved for future MVPs

---

## Transfermarkt

Strengths:

* Market Value
* Transfer Information
* Contract Information

Weaknesses:

* Limited performance analytics

Decision:

Future supplementary source

---

# Future Expansion Plan

## MVP 1

FBref — Season 2025-26 (Kaggle static dataset, Decision 014)

---

## MVP 2

FBref

---

## MVP 2.1

FBref

---

## MVP 3

FBref

*

StatsBomb Open Data

---

## MVP 4+

FBref

*

StatsBomb Open Data

*

Transfermarkt

---

# Risks

## Risk 1

FBref does not provide an official public API.

Mitigation:

Build a dedicated data ingestion layer.

---

## Risk 2

Data structure changes.

Mitigation:

Normalize all data before use.

---

## Risk 3

Data availability issues.

Mitigation:

Support multiple future providers.

---

# Long-Term Vision

Football Intelligence should not depend on a single provider.

Future architecture should support:

* FBref
* StatsBomb
* Transfermarkt
* Additional providers

through a unified data layer.

---

END OF DOCUMENT
