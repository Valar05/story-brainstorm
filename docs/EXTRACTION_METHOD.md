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
