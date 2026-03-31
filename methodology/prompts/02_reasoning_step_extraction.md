# Prompt 02: Reasoning Step Extraction

**When to use:** For each ACCEPTED writeup, to produce a structured hint JSON file.

**Input:** One raw writeup text file.

**Output:** A JSON file with typed reasoning steps.

---

## Prompt

```
You are extracting reasoning steps from a reverse engineering writeup for a research study on human-AI collaboration.

RULES:
1. Only extract steps that are EXPLICITLY stated or DIRECTLY evidenced in the text.
2. Do NOT invent, infer, or add steps that are not in the writeup.
3. Every step MUST have an "evidence" field with a direct quote or close paraphrase.
4. If a step cannot be supported by a specific quote, do not include it.

STEP TYPES (use exactly these):
- "observation": a fact the author discovered about the binary
  Example: "The binary is a 64-bit ELF executable, not stripped"
- "hypothesis": a testable claim the author formed about how the binary works
  Example: "The serial must be exactly 16 characters long"
- "action": a specific analysis step the author took
  Example: "Disassembled the checkSerial function using radare2"
- "result": the outcome of an action
  Example: "Running the binary with 'abcdefghijklmnop' produced 'Good Serial'"

OUTPUT FORMAT (strict JSON):
{
  "source": "<author name or writeup identifier>",
  "steps": [
    {
      "type": "observation|hypothesis|action|result",
      "content": "<concise one-sentence description>",
      "evidence": "<direct quote or close paraphrase from the writeup>"
    }
  ]
}

CONSTRAINTS:
- Keep each step atomic (one fact, one claim, one action, or one result per step)
- Do not merge multiple observations into one step
- Do not include steps about the writeup author's setup or environment
- Content should be 1-2 sentences maximum
- Evidence must be traceable to a specific passage in the writeup

--- WRITEUP START ---
{paste writeup text here}
--- WRITEUP END ---
```

**Model:** Claude Opus 4 or equivalent.

**Post-processing:** Run Prompt 03 (normalization) on the output.

**Human review checklist:**
- [ ] Every step has a non-empty evidence field
- [ ] No evidence field contains text not found in the original writeup
- [ ] Step types are correctly assigned (observations are facts, hypotheses are claims, actions are things done, results are outcomes)
- [ ] No important reasoning steps from the writeup were omitted
