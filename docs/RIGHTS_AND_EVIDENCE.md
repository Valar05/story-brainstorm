# Rights and Evidence

This lane accepts only an exact edition with `rights_basis: PD_US_CONFIRMED`. A work date alone is not an edition right. The edition record must provide a defensible United States public-domain basis and a stable source URL or identifier.

Foreign-first works, modern translations, adaptations, anonymous or pseudonymous works, uncertain dates, candidate rights, and unresolved jurisdiction are `UNKNOWN` or excluded until a specific edition record proves US status. Rights outside the United States are not implied.

Evidence is a short excerpt of at most 25 words plus an exact chapter, scene, page, stanza, paragraph, or equivalent locator. Store no full text. Observation records direct source facts; inference records the reusable abstraction.

Derivative-risk review:
- low: short evidence and high-level abstraction; accept when all gates pass.
- medium: source-specific detail could substitute for the original; shorten and abstract, then re-review.
- high: long quotation, close paraphrase, scene reconstruction, or voice imitation; reject.

Acceptance falsifiers are missing/unstable location, excerpt over 25 words, non-confirmed rights, merged observation and inference, unsupported generic inference, duplicate mechanism without independent distinction, invalid contextual subtype, or synthesis with fewer than three works.

Publication evidence gate: first-publication evidence must be an exact Open Library work record URL (`https://openlibrary.org/works/OL...W`), never a search/category/root URL. The auditor fetches/caches that JSON and requires title equality plus a four-digit `first_publish_date` equal to the record year. Gutenberg digital release date is not used as first-publication evidence.
