from __future__ import annotations

from pydantic import BaseModel, Field


class Observation(BaseModel):
    id: str                  # "obs-001"
    content: str             # what was observed
    source: str              # tool that produced this (e.g. "strings", "hexdump")
    step: int                # agent step when this was recorded
    important: bool = False  # flagged by mark_observation_as_important intervention


class Hypothesis(BaseModel):
    id: str                  # "hyp-001"
    claim: str               # what the agent believes is true
    status: str              # "active" | "supported" | "refuted"
    confidence: str          # "low" | "medium" | "high"
    origin: str              # "agent" | "intervention" — who introduced this
    step_created: int
    step_updated: int


class ActionRecord(BaseModel):
    step: int
    tool: str                # tool name called
    arguments: dict          # arguments passed to the tool
    result_summary: str      # one-line summary of what the result showed


class Intervention(BaseModel):
    id: str                  # "iv-001"
    type: str                # "add_hypothesis" | "reject_hypothesis" |
                             # "mark_observation_as_important" |
                             # "suggest_action" | "reprioritize_next_steps"
    payload: dict            # type-specific fields
    step: int                # agent step when this was applied
    source: str              # "scripted" | "oracle" | "human"


class InvestigationState(BaseModel):
    challenge_id: str
    agent_variant: str                        # "baseline" | "structured"
    step: int = 0

    observations: list[Observation] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    actions: list[ActionRecord] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)  # plain strings, priority-ordered

    current_understanding: str = ""           # free-text summary the agent maintains
    interventions_applied: list[Intervention] = Field(default_factory=list)

    flag_candidate: str | None = None
    solved: bool = False

    # --- ID generators ---
    def next_obs_id(self) -> str:
        return f"obs-{len(self.observations) + 1:03d}"

    def next_hyp_id(self) -> str:
        return f"hyp-{len(self.hypotheses) + 1:03d}"

    # --- Convenience queries ---
    def active_hypotheses(self) -> list[Hypothesis]:
        return [h for h in self.hypotheses if h.status == "active"]

    def get_hypothesis(self, hyp_id: str) -> Hypothesis | None:
        return next((h for h in self.hypotheses if h.id == hyp_id), None)

    def get_observation(self, obs_id: str) -> Observation | None:
        return next((o for o in self.observations if o.id == obs_id), None)
