# Extraction Method

## Objective
Extract exactly 1,000 evidence-backed primitive cards from 100 pre-1930 works: 3 story, 2 speech, 2 character, 1 conflict, 1 structure, and 1 contextual card per work.

## Workflow
1. Lock one eligible edition per work. Record its stable URL/identifier, publication metadata, rights basis, and locator convention before reading.
2. Read for mechanisms, not retellings. Capture the smallest useful passage; the excerpt must be 1–25 words. Never store full source text.
3. Write `observation` as only what the passage and locator establish. Write `inference` as the abstract reusable pattern. Do not hide inference in observation.
4. Assign one primary family. Contextual cards must use exactly one subtype: setting, institution, object, transformation, or tone_pressure.
5. Encode the pattern as setup, pressure, turn, residue. Names must identify the mechanism, not merely a trope.
6. Deduplicate within a work before cross-source synthesis. Preserve culturally specific patterns as distinct records.
7. Accept only `PD_US_CONFIRMED` editions with exact locators. Unknown, candidate, translation-layer, or jurisdictionally uncertain material is rejected or quarantined.

## Review rubric
A reviewer independently checks identity/date, edition rights, locator, excerpt word count, observation/inference separation, family fit, specificity, cultural distinctness, and duplicate status. Any falsifier blocks acceptance.

## Derivative-risk rubric
- `low`: short excerpt plus abstract mechanism; no distinctive sequence or voice imitation.
- `medium`: several source-specific details remain; shorten excerpt and abstract further before acceptance.
- `high`: long quotation, close paraphrase, scene reconstruction, distinctive dialogue imitation, or full-text material; reject and delete from staging.

## Synthesis
A synthesis card is allowed only after three distinct works independently support the same mechanism. It links source card IDs and states the shared abstraction; it does not replace the source observations.

## Negative controls
The fixture file contains exactly 50 intentionally invalid examples in five groups of ten. Validators must reject each for its declared reason.

## Schema alignment
The schema requires observation and inference as separate nonempty fields, strict setup/pressure/turn/residue pattern keys, and a contextual subtype only for contextual cards. Primitive IDs must equal the engine's deterministic hash projection.

## Evidence entailment audit

`tools/audit_primitive_evidence.py` checks source-entailment prerequisites without storing source text in the repository. Invoke it with `--works`, `--cards`, `--out`, and a caller-supplied `--text-cache`; add `--live` to fetch missing Gutenberg plain-text items into that external cache.

An evidence reference passes only when its work is known, its edition URL exactly equals the WorkRecord edition URL, its stored word count recomputes to 1–25 words, its locator is specific (for example `Chapter 1`, `page 4`, or `scene 2`), and normalized excerpt text occurs in the exact cached/fetched source. Duplicate references, missing evidence, vague locations, wrong editions, malformed/unavailable UTF-8 sources, and cache paths inside the repository fail closed. Cache writes are atomic and repeat runs are no-ops. This proves entailment prerequisites only; it does not judge semantic inference correctness.

Evidence auditor requires recognized START/END Gutenberg markers, body-only excerpt matching with exactly one normalized occurrence, and specific locators (Chapter/Act/Scene/Book/Part/Section/Poem/Stanza identifier or Page number). License, credits, produced-by, and transcriber boilerplate are rejected.
Clarification: boilerplate rejection applies to the submitted excerpt, not to arbitrary words appearing in otherwise valid body prose; a body passage that merely uses a word such as “license” remains eligible when its excerpt is not boilerplate.

## Deterministic primitive quality guardrails (C9)

The source-evidence auditor and existing PrimitiveCard schema remain their respective owners. `tools/audit_primitive_quality.py` adds a separate pre-review guardrail; it does not replace either owner or establish semantic truth. Run all three checks before independent interpretation, cultural-specificity, derivative-risk, and locator review. A quality report always states `semantic_review: REQUIRED`, including when its guardrail `state` is `READY`.

```sh
python tools/audit_primitive_quality.py --cards tests/fixtures/primitive_quality/positive.json --out /data/data/com.termux/files/usr/tmp/C9-positive-audit.json --expected-works 3
python -m unittest discover -s tests -p test_primitive_quality_audit.py
```

`--expected-works` is a mandatory positive integer count of distinct evidence work IDs, not a path or an allowlist. Work identity is anchored by the separate canonical-source audit. A card must reference exactly one work, though it may have multiple distinct references within that work. The shard must contain exactly ten cards per work and the 3 story / 2 speech / 2 character / 1 conflict / 1 structure / 1 contextual matrix independently for every work. Correct global totals cannot conceal a per-work swap.

Normalization uses Unicode NFKC, case folding, and lexical tokens with punctuation, underscores, and whitespace treated as separators. Names, summaries, observations, and inferences must each be unique within their field. Every pattern component must be unique across all four component fields and cards, and composite patterns must also be unique. Repeated wording after replacing work IDs and numeric slots is flagged separately as template repetition. Evidence references are compared after normalization; reusing the same work/edition/excerpt under a renamed locator still fails. Repetition within one card is also rejected.

Names may not include work IDs, terminal numeric placeholders, or generic mechanism/primitive placeholder labels. Minimum lexical counts are 3 words for names, 8 for summaries, 10 each for observations and inferences, and 6 for each setup/pressure/turn/residue component. Distinct-word floors are respectively 3, 6, 7, 7, and 5. Purely numeric tokens do not count toward these substantive-word floors. These are calibrated rejection floors, not a recipe for quality and not proof of substance: padding, arbitrary synonyms, or longer generic prose can remain semantically false. Observation must not equal its excerpt after normalization.

Publication/license/credit/transcription boilerplate and the known false-green extraction phrases are forbidden in prose and evidence snippets. Examples include `this passage supports`, `source-specific ... grounded`, `source situation in`, `pressure accumulates through [the] observed condition`, `observed condition changes`, and `consequence remains available`. Known generic pattern components receive their own error code. Narrative discussion of credit or an ordinary action described by produced is not itself publication metadata.

Only contextual cards may have a subtype, which must be one of the unchanged taxonomy values. A multi-work shard must use at least three distinct contextual subtypes; none may exceed 70 percent of contextual cards. Consequently, a two-work shard with one contextual card per work cannot meet this multi-work gate. A one-work calibration/extraction unit is exempt from cross-work subtype diversity but not subtype validity. Merely relabeling cards does not establish that their mechanisms fit those subtypes; human review must reject that evasion.

Reports contain deterministic global errors, per-card coded errors, work/family counts, subtype counts, thresholds, and the exact input-byte SHA-256. Error counters count findings, not unique cards: a repeated field marks every participating card, and contextual collapse contributes global and per-card findings. `cards_with_errors` separately counts failing cards. Exit status is 0 for guardrail READY, 1 for NOT_READY, and 2 for invalid invocation or inability to write a report. Malformed/missing input produces NOT_READY when the output remains writable. The existing native atomic JSON writer provides byte-identical no-op reruns; an input/output alias is refused, and a pre-replace failure preserves the previous report.

The hand-authored three-work/30-card synthetic positive fixture is schema/engine compatible but is not real-source extraction and must never enter the corpus. Focused ablations cover every guardrail, threshold boundaries, ordinary normalization variation, repeated-word padding, per-work quota swaps, renamed evidence locators, the exact 70 percent boundary, invalid inputs, deterministic/no-op writes, and atomic failure preservation. A combined E-shaped negative is self-contained for portable regression tests. Independently, the exact rejected E commit was materialized into external temporary storage and audited through the production CLI: 340/340 cards NOT_READY, with 340 placeholder names, 656 boilerplate findings, 2,040 known-template prose findings, 2,630 template-repetition findings, 1,360 generic-pattern findings, and complete contextual collapse. Its source hash and full counters are sealed in `tests/fixtures/primitive_quality/rejected_E_expected.json`; synthetic ablations do not replace that exact-blob evidence.

Limitations remain explicit: lexical uniqueness does not prove non-generic inference; an exact quote does not prove an accurate locator or interpretation; subtype variety does not prove cultural distinctness; and a passing schema or guardrail cannot authorize voice imitation. Unknown or disputed semantic evidence still blocks extraction acceptance.
