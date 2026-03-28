# Intervention Derivation Methodology

This document describes the reproducible pipeline for deriving structured reasoning traces (hint files) and scripted interventions from human-authored writeups. This pipeline is part of the experimental methodology and should be cited when describing the intervention construction process.

## Overview

Interventions in this system serve as proxies for human collaborator input. Rather than using live human participants, we derive interventions from independently authored solution writeups for each challenge. The pipeline has three stages:

1. **Writeup collection and curation** (manual)
2. **Reasoning step extraction** (LLM-assisted, human-verified)
3. **Intervention synthesis** (LLM-assisted, human-verified)

Each stage is described below with the exact prompts and models used.

---

## Stage 1: Writeup Collection and Curation

**Process:** Writeups are collected from public challenge repositories (e.g., crackmes.one). Multiple writeups per challenge are required to enable consensus-based intervention derivation.

**Quality filter:** Writeups are assessed for:
- Presence of explicit reasoning steps (not just code dumps)
- Description of methodology (tools used, observations made)
- Testable claims about binary behavior

Writeups that consist solely of code, contain no analytical narrative, or are too brief to extract meaningful reasoning steps are excluded.

**For `yurisimplekeygen`:** 10 writeups were collected from crackmes.one. 3 were excluded (1 code-only dump, 1 overly brief, 1 assembly-only with minimal explanation), leaving 7 writeups from independent authors using varied tools (radare2, Ghidra, Cutter, objdump, GDB).

---

## Stage 2: Reasoning Step Extraction

**Objective:** Convert each narrative writeup into a structured sequence of typed reasoning steps.

**Model:** Claude Opus 4 (claude-opus-4-20250514)

**Prompt used for extraction:**

```
You are extracting reasoning steps from a cybersecurity CTF writeup.
Do NOT invent steps. Only extract what is explicitly stated or directly
implied by the text.

For each step, provide:
- type: one of "observation", "hypothesis", "action", "result"
- content: a concise description of the step
- evidence: a direct quote or close paraphrase from the writeup

Output format:
{
  "source": "<author or identifier>",
  "steps": [
    {"type": "observation", "content": "...", "evidence": "..."},
    ...
  ]
}

Step type definitions:
- observation: a fact the author discovered (e.g., "the binary is not stripped")
- hypothesis: a testable claim the author formed (e.g., "the serial must be 16 characters")
- action: something the author did to test a hypothesis (e.g., "ran strings on the binary")
- result: the outcome of an action (e.g., "the binary printed 'Good Serial'")
```

**Post-extraction normalization (LLM-assisted, human-verified):**

After initial extraction, a second pass normalizes the steps:
- Merge duplicate observations across steps
- Remove vague or untestable claims
- Ensure each hypothesis is testable and atomic
- Ensure each observation cites specific evidence

**Prompt for normalization:**

```
Given these extracted reasoning steps, clean and normalize them:
- Merge duplicates
- Remove vague steps that lack specific evidence
- Ensure each hypothesis is testable (remove hypotheses that aren't)
- Keep steps minimal and atomic
- Update the JSON file
```

**Human verification:** After LLM-assisted extraction and normalization, a human reviewer checks each hint file against the original writeup to verify:
1. No steps were fabricated by the extraction model
2. Evidence quotes accurately reflect the source text
3. Step types are correctly assigned
4. No critical reasoning steps from the writeup were omitted

---

## Stage 3: Intervention Synthesis

**Objective:** Derive a small set of tiered interventions from the consensus across multiple writeup hint files.

**Model:** Claude Opus 4 (claude-opus-4-20250514)

**Process:**

1. All hint files for a challenge are provided to the model
2. The model identifies recurring observations, hypotheses, and reasoning patterns across writeups
3. Consensus insights (present in 3+ writeups) become intervention candidates
4. Interventions are tiered by specificity

**Prompt used for synthesis:**

```
You have multiple structured writeup traces for the same reverse engineering
challenge. Each trace contains observations, hypotheses, actions, and results
extracted from an independent human writeup.

Your task: derive a small set (2-4) of scripted interventions that represent
consensus human insights, ordered from general to specific.

Rules:
- Tier 1 (light): directional guidance — point at WHAT to investigate,
  not what the answer is. Example: "The binary has a checkSerial function
  that validates input."
- Tier 2 (strong): structural insight — describe the PATTERN without giving
  a specific valid input. Example: "The validation compares pairs of adjacent
  characters using an arithmetic relationship."
- NEVER include a specific valid input, serial, or key in any intervention
- NEVER include tool commands (e.g., "try run_binary(abc...)")
- Each intervention should be derivable from the writeup evidence
- Prefer insights that appear in multiple writeups over single-source claims

Output format:
[
  {
    "id": "iv-001",
    "tier": 1,
    "type": "add_hypothesis",
    "payload": {
      "claim": "...",
      "confidence": "high|medium|low"
    }
  }
]
```

**Human verification:** After LLM-assisted synthesis, a human reviewer checks:
1. No intervention reveals the solution directly
2. Tier assignments are appropriate (tier 1 is directional, tier 2 is structural)
3. Each intervention claim is supported by evidence in 2+ writeup traces
4. Interventions are phrased as hypotheses, not instructions

---

## Reproducibility Notes

**Why LLM-assisted rather than fully manual?** Extracting structured reasoning steps from narrative text is time-consuming but relatively mechanical. Using an LLM for initial extraction followed by human verification reduces annotation effort while maintaining accuracy. The extraction prompt constrains the model to only extract what is explicitly stated, reducing hallucination risk.

**Why human verification is required:** LLMs may:
- Fabricate reasoning steps not present in the source text
- Misclassify step types (e.g., labeling an action as an observation)
- Omit important steps that use domain-specific terminology
- In intervention synthesis: inadvertently include solution-revealing information

Human verification serves as a quality gate. We recommend that reviewers have basic familiarity with reverse engineering terminology but need not be domain experts.

**Inter-annotator agreement:** For studies requiring formal reliability measures, we recommend having two independent reviewers verify each hint file and computing Cohen's kappa on step type classifications. This was not performed for the current prototype but is planned for the full study.

---

## File Manifest

For each challenge, the pipeline produces:

| File | Description | Stage |
|------|-------------|-------|
| `hints/writeup_*.json` | Structured reasoning traces, one per writeup | Stage 2 |
| `interventions.json` | Tiered consensus interventions | Stage 3 |

All intermediate artifacts (raw writeups, extraction prompts, reviewer notes) should be retained for reproducibility.
