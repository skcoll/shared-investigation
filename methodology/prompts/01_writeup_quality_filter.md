# Prompt 01: Writeup Quality Filter

**When to use:** After collecting raw writeups for a challenge, before extraction.

**Input:** One raw writeup text file.

**Output:** ACCEPT or REJECT with reason.

---

## Prompt

```
You are evaluating a reverse engineering writeup for inclusion in a research study. The writeup will be used to extract structured reasoning steps that represent how a human analyst approaches the challenge.

Evaluate the following writeup on three criteria:

1. REASONING STEPS: Does the writeup describe a step-by-step investigation process? (not just a code dump or final answer)
2. METHODOLOGY: Does it mention specific tools, commands, or analysis techniques used?
3. EVIDENCE: Does it include specific observations about the binary (addresses, strings, function names, behavior)?

Rate each criterion YES or NO, then give a final verdict:
- ACCEPT: at least 2 of 3 criteria are YES
- REJECT: fewer than 2 criteria are YES

Output format:
REASONING_STEPS: YES/NO — [one sentence justification]
METHODOLOGY: YES/NO — [one sentence justification]
EVIDENCE: YES/NO — [one sentence justification]
VERDICT: ACCEPT/REJECT

--- WRITEUP START ---
{paste writeup text here}
--- WRITEUP END ---
```

**Model:** Any capable model (Claude, GPT-4, etc.) — this is a classification task, not generation.

**Human review:** Spot-check REJECT decisions to ensure no high-quality writeups were excluded.
