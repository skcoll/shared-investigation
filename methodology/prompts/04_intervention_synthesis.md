# Prompt 04: Intervention Synthesis

**When to use:** After ALL writeup hint JSONs for a challenge are extracted and normalized. This produces the `interventions.json` file.

**Input:** All hint JSON files for a single challenge.

**Output:** `interventions.json` with 2-4 tiered interventions.

---

## Prompt

```
You are synthesizing interventions for a human-AI collaboration experiment on reverse engineering. You will be given multiple structured reasoning traces extracted from independent human writeups for the SAME challenge. Your job is to identify CONSENSUS insights and convert them into tiered interventions.

CONTEXT: These interventions will be injected into an LLM agent's investigation state when it stalls. They should guide the agent's reasoning without giving away the answer. The agent has these tools: file(), strings(), disasm(), disasm(FUNCTION), run_binary(INPUT), python_eval(CODE).

RULES:
1. Only include insights that appear in 2 or more writeups (cite which ones).
2. NEVER include a specific valid input, serial, key, password, or solution.
3. NEVER include specific tool commands (e.g., "try run_binary(...)").
4. NEVER include specific memory addresses, hex values, or exact constants from the binary — these are answers, not guidance.
5. Tier 1 (light) interventions point at WHAT to investigate — a function name, a pattern to look for, a category of behavior. The agent must still figure out the details.
6. Tier 2 (strong) interventions describe the STRUCTURE of the algorithm — the type of operation, the relationship between elements — without giving specific values.
7. Order interventions from most general (tier 1) to most specific (tier 2).
8. Include a "derivation" field documenting which writeups support each intervention.

OUTPUT FORMAT (strict JSON):
[
  {
    "id": "iv-001",
    "tier": 1,
    "type": "add_hypothesis",
    "payload": {
      "claim": "<directional guidance, no specific values>",
      "confidence": "high|medium|low"
    },
    "derivation": {
      "supporting_writeups": ["<source1>", "<source2>"],
      "consensus": "<one-sentence summary of what the writeups agree on>"
    }
  }
]

VALIDATION CHECKLIST (apply to each intervention before outputting):
- [ ] Does NOT contain a specific valid input or answer
- [ ] Does NOT contain tool commands
- [ ] Does NOT contain specific hex values or addresses
- [ ] IS supported by 2+ writeups (listed in derivation)
- [ ] Tier assignment is correct (1=directional, 2=structural)
- [ ] Phrased as a hypothesis, not an instruction

--- HINT FILES ---
{paste all hint JSON files here, separated by ---}
--- END ---
```

**Model:** Claude Opus 4 or equivalent.

**Human review checklist:**
- [ ] No intervention reveals the solution (test: could someone derive the answer from just reading the interventions without seeing the binary?)
- [ ] Every intervention has a derivation with 2+ supporting writeups
- [ ] Tier 1 interventions are genuinely directional (point at what, not how)
- [ ] Tier 2 interventions describe structure without specific values
- [ ] Total count is 2-4 interventions (enough to help, not so many as to solve)

**Known failure mode:** The model may include specific encoded strings, constants, or addresses from the writeups. These are effectively answers. Strip them and rephrase as categories (e.g., "an encoded string" not "the string fhz4yhx|~g=5").
