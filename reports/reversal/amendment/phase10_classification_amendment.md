# Phase 10 — Exhaustive Classification Amendment

> **POST-OUTCOME AMENDMENT**  
> **CREATED AFTER THE 2026-07-20 THROUGH 2026-09-11 CONFIRMATION WAS OBSERVED**  
> **CANNOT RETROACTIVELY CONVERT THAT SAMPLE INTO PRISTINE VALIDATION**

Created: 2026-09-16T15:29:56Z  
Original preregistration SHA256: `fb0976eeea5dc524f4bb9a22dad98b6b0ec6fc42507dcc90f9d5f16d52da6995`  
Blocker report SHA256: `a22db930294f54032d98036926ef0d71d74fa12748beae84be6d645d0a755567`  
Corporate-action extension build: `8ad77b280031a1f9d99f6ce85a2078e6f6457a3ffdc39a9a0c6e9857225abc13`

## Purpose and untouched boundary

This amendment closes the classification gap without changing REV05, REV20, their signs, universes, outcomes, ranks, interval safety, bootstrap, non-overlap sampling, or leave-one-date method. It applies only to new signals strictly after **2026-09-11**, after corporate-action and price coverage are independently extended to every admitted endpoint.

## Candidate hierarchy

Evaluation is ordered: `INSUFFICIENT SAMPLE`; `CONTRADICTORY`; `MIXED`; `DIRECTIONALLY POSITIVE BUT UNSTABLE`; `SUPPORTIVE BUT SHORT SAMPLE`; `SUPPORTED`. The complete executable conditions are in `phase10_complete_classification_table.csv`.

The full enumerated state space contains 8,232 states. Every state maps once to one class. Class counts are {'INSUFFICIENT SAMPLE': 2744, 'DIRECTIONALLY POSITIVE BUT UNSTABLE': 2298, 'CONTRADICTORY': 1568, 'MIXED': 1568, 'SUPPORTIVE BUT SHORT SAMPLE': 27, 'SUPPORTED': 27}. The historical discovery requirement remains fixed at six positive REV-oriented horizons for these two candidates.

## Overall decisions

All 36 ordered candidate-class pairs map exactly once. Pair counts are {'RESEARCH FURTHER': 23, 'CONDITIONAL PASS': 11, 'FAIL': 1, 'PASS FOR COMPLEMENTARITY RESEARCH': 1}. Both `SUPPORTED` gives `PASS FOR COMPLEMENTARITY RESEARCH`; at least one `SUPPORTED`, or both `SUPPORTIVE BUT SHORT SAMPLE`, gives `CONDITIONAL PASS`; both `CONTRADICTORY` gives `FAIL`; all remaining pairs give `RESEARCH FURTHER`.

## Retrospective descriptive mapping

This is **RETROSPECTIVE DESCRIPTIVE MAPPING ONLY — NOT NEW VALIDATION — NOT ACCEPTED OOS CLASSIFICATION**.

- REV05: `DIRECTIONALLY POSITIVE BUT UNSTABLE` equivalent.
- REV20: `CONTRADICTORY` equivalent.
- Accepted overall Phase-10 decision remains `RESEARCH FURTHER`.

## Requirements for the next untouched rerun

Use only signals after 2026-09-11. First extend and freeze official corporate-action certification and price coverage for every endpoint. Then run exactly REV05/REV20 in BASIC_LIQUID with MODERATE_LIQUID sensitivity and outcomes 1/2/3/5/10/20. Preserve signal ranks before outcome availability, all non-overlap offsets, the fixed bootstrap, and leave-one-date influence. Apply this amended hierarchy without further changes. No Phase 11, factor combination, or portfolio research is authorized by this amendment.
