import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state.schema import Observation, Hypothesis, ActionRecord, InvestigationState

state = InvestigationState(
    challenge_id="picoctf_rev01",
    agent_variant="structured",
)

# Add an observation
state.observations.append(Observation(
    id=state.next_obs_id(),
    content="File is a 64-bit ELF binary, not stripped",
    source="strings",
    step=1,
))

# Add a hypothesis
state.hypotheses.append(Hypothesis(
    id=state.next_hyp_id(),
    claim="The binary does a simple string comparison against a hardcoded flag",
    status="active",
    confidence="low",
    origin="agent",
    step_created=1,
    step_updated=1,
))

# Add an action
state.actions.append(ActionRecord(
    step=1,
    tool="strings",
    arguments={"file": "crackme"},
    result_summary="Found readable strings including 'Enter password:' and some hex-looking data",
))

state.current_understanding = "Binary prompts for a password. Likely does a direct comparison."
state.next_steps = ["Run strings to find hardcoded values", "Disassemble the comparison function"]

print(state.model_dump_json(indent=2))
