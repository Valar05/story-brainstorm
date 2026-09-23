# Primitive quality calibration fixtures

`positive.json` contains 30 individually authored cards over three invented test scenarios: a flood rescue, an orchard hearing, and a besieged observatory. The names, observations, inferences, pattern components, and short snippets were written separately for these scenarios, not populated from per-family prose templates. Shared JSON serialization and family assignment are mechanical only.

All scenario and excerpt material is original synthetic test content. The `example.invalid` edition URLs cannot validate as sources. Schema-required `PD_US_CONFIRMED` and `accepted` values exercise the card shape; they do not establish rights or eligibility for a real corpus. Never merge these cards into canonical primitives, treat them as bibliography evidence, or report them as culturally reviewed extraction. Their acceptance is only a calibration positive for deterministic rules.

Each scenario has the 3/2/2/1/1/1 family matrix. Their contextual cards respectively use institution, object, and transformation. All 30 cards validate against the unchanged PrimitiveCard schema and native engine ID/count checks. This establishes structural compatibility, not semantic truth.

The calibrated lexical floors are name 3 words (3 distinct), summary 8 (6 distinct), observation and inference 10 (7 distinct), and each pattern field 6 (5 distinct). Focused tests replace every field with one-below and exact-floor values; repeated-word padding is separately rejected. A first-pass false positive on narrative credit was corrected by limiting publication-credit detection to metadata/attribution forms. Ordinary narrative credit and the verb produced have positive regression coverage.

`rejected_E_expected.json` seals the SHA-256 of the exact rejected `f520847` E JSON blob, its full commit identity, measured error counts, and minimum falsification counts. That blob was directly materialized outside the repository and passed through the production CLI with expected work count 34. All 340 cards failed. The full rejected shard is deliberately not copied here. A self-contained combined E-shaped ablation supplements the exact-blob proof without making ordinary tests depend on an unmerged Git object surviving in future clones.

The audit never fetches texts. No source books or complete source texts are included in this fixture directory.
