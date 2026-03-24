"""
challenges/init_challenge.py

Restructure or scaffold a challenge directory into the standard layout:

    challenges/<challenge_id>/
        problem.txt          # problem description (required)
        artifacts/           # files the agent can analyze
        hints/               # writeup JSONs for interventions
        metadata.json        # auto-generated from directory contents

Usage:
    # Scaffold a new empty challenge
    python challenges/init_challenge.py picoCTF2024_newchallenge

    # Restructure an existing challenge that has *_problem.txt and loose files
    python challenges/init_challenge.py picoCTF2019_vaultdoor3

The script is idempotent — running it again on an already-structured challenge
just regenerates metadata.json from the current directory contents.
"""

import json
import os
import shutil
import sys
from pathlib import Path


CHALLENGES_DIR = Path(__file__).parent


def init_challenge(challenge_id: str) -> None:
    challenge_dir = CHALLENGES_DIR / challenge_id

    if not challenge_dir.exists():
        # Scaffold a new empty challenge
        challenge_dir.mkdir(parents=True)
        (challenge_dir / "artifacts").mkdir()
        (challenge_dir / "hints").mkdir()
        (challenge_dir / "problem.txt").write_text(
            "# TODO: paste the challenge description here\n"
        )
        print(f"Scaffolded new challenge: {challenge_dir}")
        _generate_metadata(challenge_dir, challenge_id)
        return

    # --- Restructure an existing challenge ---

    # Create subdirectories
    artifacts_dir = challenge_dir / "artifacts"
    hints_dir = challenge_dir / "hints"
    artifacts_dir.mkdir(exist_ok=True)
    hints_dir.mkdir(exist_ok=True)

    # 1. Rename *_problem.txt -> problem.txt (if not already done)
    problem_dest = challenge_dir / "problem.txt"
    if not problem_dest.exists():
        problem_files = list(challenge_dir.glob("*_problem.txt"))
        if problem_files:
            shutil.move(str(problem_files[0]), str(problem_dest))
            print(f"  Renamed {problem_files[0].name} -> problem.txt")
        else:
            problem_dest.write_text("# TODO: paste the challenge description here\n")
            print(f"  Created empty problem.txt (fill this in)")

    # 2. Move writeup *.json -> hints/
    for f in list(challenge_dir.glob("writeup_*.json")):
        # Strip the common prefix to get a cleaner name
        # writeup_vaultdoor3_bastista.json -> bastista.json
        parts = f.stem.split("_")
        # Take everything after the second underscore (skip "writeup" and challenge name)
        if len(parts) >= 3:
            short_name = "_".join(parts[2:]) + ".json"
        else:
            short_name = f.name
        dest = hints_dir / short_name
        shutil.move(str(f), str(dest))
        print(f"  Moved {f.name} -> hints/{short_name}")

    # 3. Move non-special files into artifacts/
    #    Skip: problem.txt, metadata.json, writeup raw texts, directories
    skip = {"problem.txt", "metadata.json"}
    skip_prefixes = ("writeup_",)  # raw .txt writeups stay (or move them too)

    for f in list(challenge_dir.iterdir()):
        if f.is_dir():
            continue
        if f.name in skip:
            continue
        if f.name.startswith("writeup_"):
            # Move raw writeup .txt files to hints/ too
            parts = f.stem.split("_")
            if len(parts) >= 3:
                short_name = "_".join(parts[2:]) + f.suffix
            else:
                short_name = f.name
            dest = hints_dir / short_name
            shutil.move(str(f), str(dest))
            print(f"  Moved {f.name} -> hints/{short_name}")
            continue
        # Everything else is an artifact
        dest = artifacts_dir / f.name
        shutil.move(str(f), str(dest))
        print(f"  Moved {f.name} -> artifacts/{f.name}")

    _generate_metadata(challenge_dir, challenge_id)
    print(f"Done: {challenge_dir}")


def _generate_metadata(challenge_dir: Path, challenge_id: str) -> None:
    """Generate metadata.json from directory contents."""
    artifacts_dir = challenge_dir / "artifacts"
    hints_dir = challenge_dir / "hints"

    artifacts = sorted(f.name for f in artifacts_dir.iterdir() if f.is_file()) if artifacts_dir.exists() else []
    hints = sorted(f.name for f in hints_dir.iterdir() if f.is_file()) if hints_dir.exists() else []

    # Read first line of problem.txt as description
    problem_file = challenge_dir / "problem.txt"
    description = ""
    if problem_file.exists():
        text = problem_file.read_text().strip()
        # Skip comment lines, take first real line
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                description = line
                break

    metadata = {
        "id": challenge_id,
        "description": description,
        "artifacts": artifacts,
        "hints": [h for h in hints if h.endswith(".json")],
    }

    meta_path = challenge_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"  Wrote metadata.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <challenge_id>")
        print(f"  Example: python {sys.argv[0]} picoCTF2019_vaultdoor3")
        sys.exit(1)

    init_challenge(sys.argv[1])
