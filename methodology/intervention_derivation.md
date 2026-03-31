# Intervention Derivation Methodology

This document describes the reproducible pipeline for deriving structured reasoning traces (hint files) and scripted interventions from human-authored writeups.

## Overview

Interventions serve as proxies for human collaborator input. Rather than recruiting live participants, we derive interventions from independently authored solution writeups for each challenge. The pipeline has four stages, each with a standardized prompt template.

## Pipeline

```
Raw writeups (.txt/.md)
        │
  [Stage 1] Quality Filter (methodology/prompts/01_writeup_quality_filter.md)
        │
  [Stage 2] Reasoning Step Extraction (methodology/prompts/02_reasoning_step_extraction.md)
        │
  [Stage 3] Step Normalization (methodology/prompts/03_step_normalization.md)
        │
  [Stage 4] Intervention Synthesis (methodology/prompts/04_intervention_synthesis.md)
        │
  Human review at each stage
```

## Prompt Templates

All prompts are in `methodology/prompts/`. Each file contains:
- The exact prompt to use (copy-paste, do not paraphrase)
- The required model (Claude Opus 4)
- Input/output format specifications
- A human review checklist

**For reproducibility:** use the prompts exactly as written, with the specified model, on one input at a time. Document any manual changes made during human review.

## Stage 1: Writeup Collection and Quality Filter

Writeups are collected from public challenge repositories (e.g., crackmes.one). Each is assessed using Prompt 01 on three criteria: reasoning steps, methodology description, and specific evidence. Writeups scoring fewer than 2/3 are excluded.

## Stage 2: Reasoning Step Extraction

Each accepted writeup is processed with Prompt 02 to produce a structured JSON file with typed steps (observation, hypothesis, action, result). Every step requires a direct textual evidence quote.

## Stage 3: Step Normalization

Each extracted JSON is cleaned with Prompt 03: duplicates are merged, vague steps removed, multi-fact steps split. The prompt reports all changes made for auditability.

## Stage 4: Intervention Synthesis

All normalized hint JSONs for a challenge are provided to Prompt 04, which identifies consensus insights (present in 2+ writeups) and produces 2-4 tiered interventions. Each intervention includes a `derivation` field documenting which writeups support it.

## Intervention Format

```json
{
  "id": "iv-001",
  "tier": 1,
  "type": "add_hypothesis",
  "payload": {
    "claim": "directional guidance without specific values",
    "confidence": "high|medium|low"
  },
  "derivation": {
    "supporting_writeups": ["source1", "source2"],
    "consensus": "summary of what writeups agree on"
  }
}
```

Tier 1 (light): points at WHAT to investigate. Tier 2 (strong): describes the STRUCTURE of the algorithm.

Interventions must NEVER contain: specific valid inputs, tool commands, memory addresses, hex constants, or anything that directly reveals the solution.

## Human Verification

Human review is required after each stage. Checklists are embedded in each prompt file. The primary risks are:
- Fabricated reasoning steps not in the source text (Stage 2)
- Silent addition of steps during normalization (Stage 3)
- Solution leakage in intervention phrasing (Stage 4)

## Model

All LLM-assisted stages use Claude Opus 4 (claude-opus-4-20250514). Using a different model may produce different step counts or intervention phrasing. If a different model is used, document it and re-run human verification.
