# Prompt 03: Step Normalization

**When to use:** After extraction (Prompt 02), to clean up a single hint JSON file.

**Input:** One extracted hint JSON file.

**Output:** The same JSON file, cleaned.

---

## Prompt

```
You are normalizing extracted reasoning steps from a reverse engineering writeup. The steps have already been extracted — your job is to clean them, not add new ones.

RULES:
1. MERGE duplicate observations that describe the same fact at different detail levels. Keep the more specific version.
2. REMOVE steps where the evidence field is vague, generic, or not tied to a specific observation about the binary.
3. REMOVE hypotheses that are not testable (e.g., "the binary does something with the input" — too vague).
4. SPLIT steps that contain multiple facts into separate atomic steps.
5. Do NOT add any new steps that weren't in the input.
6. Do NOT change the evidence field — it must stay as a quote from the original writeup.
7. Preserve the original step ordering (it reflects the author's investigation sequence).

OUTPUT: The cleaned JSON in the same format:
{
  "source": "<same source>",
  "steps": [...]
}

Report what you changed at the end:
CHANGES:
- Merged: [list of merged steps]
- Removed: [list of removed steps with reason]
- Split: [list of split steps]
- Total: X steps → Y steps

--- INPUT JSON ---
{paste extracted JSON here}
--- END ---
```

**Model:** Claude Opus 4 or equivalent.

**Human review:** Compare input and output step counts. Verify no steps were silently added. Check that merges preserved the more specific version.
