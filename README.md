# Story Brainstorm

A standalone, source-first research engine for 100 rights-verified written works first published by 1929. It extracts short-evidence narrative primitives (story, speech, character, conflict, structure, contextual) without storing full source texts.

This sibling preserves Thunder Brainstorm's deterministic hashes, atomic no-op writes, JSON/JSONL reports, and safe document-serving boundary. It does not contain game/runtime payloads.

## Status

The scaffold is intentionally empty/not-ready until bibliography and extraction packets populate `data/`.

```sh
python story_brainstorm.py --help
python story_brainstorm.py works validate
python -m unittest discover -s tests -v
```

