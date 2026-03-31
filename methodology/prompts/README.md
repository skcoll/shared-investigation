# Data Processing Prompts

Standardized prompt templates for the intervention derivation pipeline. Use these exact prompts (with the specified model) to reproduce the data processing steps.

## Pipeline

For each new challenge:

```
Raw writeups (.txt/.md)
        │
        ▼
  [01] Quality Filter ──→ REJECT (discard) or ACCEPT
        │
        ▼
  [02] Reasoning Step Extraction ──→ writeup_*.json (one per writeup)
        │
        ▼
  [03] Step Normalization ──→ writeup_*.json (cleaned)
        │
        ▼
  [04] Intervention Synthesis ──→ interventions.json (from ALL hint JSONs)
        │
        ▼
  Human review at each stage (checklists in each prompt file)
```

## Files

| Prompt | Input | Output | Stage |
|--------|-------|--------|-------|
| `01_writeup_quality_filter.md` | Raw writeup text | ACCEPT/REJECT | Curation |
| `02_reasoning_step_extraction.md` | Raw writeup text | `hints/writeup_*.json` | Extraction |
| `03_step_normalization.md` | Extracted JSON | Cleaned JSON | Normalization |
| `04_intervention_synthesis.md` | All hint JSONs | `interventions.json` | Synthesis |

## Reproducibility

- Use the same model (Claude Opus 4) for all steps
- Apply prompts exactly as written — do not paraphrase or add context
- Run each prompt on one input at a time (one writeup per extraction call)
- Human review after each stage using the checklist in the prompt file
- Document any manual changes made during review

## Known Issues

- Prompt 04 (synthesis) may include specific binary constants — always check the "known failure mode" section
- Different models may produce slightly different step counts — this is acceptable as long as human review confirms accuracy
- The normalization prompt (03) may occasionally remove steps that should be kept — compare input/output step counts
