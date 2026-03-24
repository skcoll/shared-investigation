"""
challenges/loader.py

Load a challenge by ID. Returns the problem description and artifact contents
so agents can include them in prompts.
"""

import json
from pathlib import Path


CHALLENGES_DIR = Path(__file__).parent


def load_challenge(challenge_id: str) -> dict:
    """
    Load a challenge and return its contents.

    Returns:
        {
            "id": "picoCTF2019_vaultdoor3",
            "description": "This vault uses for-loops and byte arrays.",
            "problem_text": "full contents of problem.txt",
            "artifacts": {"VaultDoor3.java": "file contents...", ...},
            "hints": ["bastista.json", ...],
        }
    """
    challenge_dir = CHALLENGES_DIR / challenge_id

    if not challenge_dir.exists():
        raise FileNotFoundError(f"Challenge not found: {challenge_dir}")

    meta_path = challenge_dir / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"No metadata.json in {challenge_dir}. "
            f"Run: python challenges/init_challenge.py {challenge_id}"
        )

    metadata = json.loads(meta_path.read_text())

    # Read problem text
    problem_file = challenge_dir / "problem.txt"
    problem_text = problem_file.read_text().strip() if problem_file.exists() else ""

    # Read artifact file contents
    artifacts = {}
    artifacts_dir = challenge_dir / "artifacts"
    for name in metadata.get("artifacts", []):
        artifact_path = artifacts_dir / name
        if artifact_path.exists():
            try:
                artifacts[name] = artifact_path.read_text()
            except UnicodeDecodeError:
                artifacts[name] = f"[binary file: {name}]"

    return {
        "id": metadata["id"],
        "description": metadata.get("description", ""),
        "problem_text": problem_text,
        "artifacts": artifacts,
        "hints": metadata.get("hints", []),
    }


def format_challenge_prompt(challenge: dict) -> str:
    """Format a loaded challenge into text suitable for an agent prompt."""
    lines = [f"# Challenge: {challenge['id']}"]

    if challenge["description"]:
        lines.append(f"\n{challenge['description']}")

    if challenge["problem_text"]:
        lines.append(f"\n## Problem Description\n{challenge['problem_text']}")

    for name, content in challenge["artifacts"].items():
        lines.append(f"\n## File: {name}\n```\n{content}\n```")

    return "\n".join(lines)
