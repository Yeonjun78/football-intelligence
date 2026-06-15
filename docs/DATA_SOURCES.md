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

FBref

## Status

Primary Data Source

## Reason

FBref provides:

* Player Information
* Season Statistics
* Advanced Statistics
* League Coverage
* Historical Data

Suitable for:

* Player Profiles
* Player Comparison
* Basic Analytics

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

FBref

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
