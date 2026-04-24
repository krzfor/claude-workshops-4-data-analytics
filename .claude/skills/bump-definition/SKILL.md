---
name: bump-definition
description: Safely bump the churn metric definition version — updates definition.md and DEFINITION_VERSION in churn.py together, keeping them in sync.
---

Bump the metric definition version. The version constant in `engine/churn.py` and the definition document in `definition.md` must always match — this skill updates both atomically.

## Steps

1. Read `engine/churn.py` to find the current `DEFINITION_VERSION` value.
   Read `definition.md` to see the current version and `effective_date`.

2. Ask the user:
   - What changed? (a short description of the change)
   - What is the new version string? (suggest the next logical version, e.g. v1.0 → v1.1 for a minor edge-case change, v1.1 → v2.0 for a breaking change to the formula)

3. Apply the changes:
   - In `engine/churn.py`: update `DEFINITION_VERSION = "<new_version>"`
   - In `definition.md`:
     - Update the `definition_version:` line at the bottom to the new version
     - Update `effective_date:` to today's date
     - Prepend a brief changelog entry under a new `## Changelog` section (create it if it doesn't exist) in this format:
       ```
       ### <new_version> — <today's date>
       <user's description of what changed>
       ```

4. Check `engine/tests/test_churn.py` for any hardcoded version strings (grep for the old version). If found, list them and ask the user whether to update them.

5. Confirm what was changed and remind the user: every API response now carries `definition_version: <new_version>`, so historical results tagged with the old version were produced under different rules.
