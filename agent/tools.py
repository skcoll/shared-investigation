"""
agent/tools.py

Real tool execution for RE investigation.

- file() and strings() run locally
- run_binary() executes ELF binaries via Docker (linux/amd64 on macOS ARM)
- python_eval() runs locally

The challenges/ directory is mounted into the container so binaries
run in place with no syncing needed.
"""

import subprocess
from pathlib import Path


TIMEOUT = 15  # seconds
DOCKER_IMAGE = "ubuntu:22.04"


def _run(cmd: list[str]) -> str:
    """Run a command, return combined stdout+stderr. Truncate long output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr] " + result.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n[...truncated]"
        return output.strip()
    except subprocess.TimeoutExpired:
        return "[error] command timed out"
    except Exception as e:
        return f"[error] {e}"


def file_info(path: str) -> str:
    """Run the `file` command on a binary."""
    return _run(["file", path])


def strings(path: str) -> str:
    """Run `strings` on a binary."""
    return _run(["strings", path])


def run_binary(challenges_root: str, binary_path: str, input_arg: str) -> str:
    """Run an ELF binary via Docker with the challenges dir mounted."""
    # binary_path is absolute on the host; convert to container path
    # Host: /path/to/challenges/foo/artifacts/Binary
    # Container: /challenges/foo/artifacts/Binary
    rel = str(Path(binary_path).relative_to(challenges_root))
    container_path = f"/challenges/{rel}"

    safe_input = input_arg.replace("'", "'\\''")
    cmd = [
        "docker", "run", "--rm",
        "--platform", "linux/amd64",
        "-v", f"{challenges_root}:/challenges:ro",
        DOCKER_IMAGE,
        "sh", "-c", f"{container_path} '{safe_input}'",
    ]
    return _run(cmd)


def disasm(path: str, function: str = "") -> str:
    """Disassemble a binary with objdump. Optionally filter to a specific function."""
    if function:
        # Disassemble full binary, grep for the function section
        result = subprocess.run(
            ["objdump", "-d", "-M", "intel", path],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        output = result.stdout
        # Extract just the requested function
        lines = output.split("\n")
        capturing = False
        captured = []
        for line in lines:
            if f"<{function}>:" in line:
                capturing = True
            elif capturing and line and not line.startswith(" ") and ":" in line and "<" in line:
                # Hit the next function header
                break
            if capturing:
                captured.append(line)
        if captured:
            output = "\n".join(captured)
        else:
            output = f"Function '{function}' not found. Available functions:\n"
            output += "\n".join(l for l in lines if l.strip().endswith(">:"))[:2000]
        if len(output) > 4000:
            output = output[:4000] + "\n[...truncated]"
        return output.strip()
    else:
        # Full disassembly, truncated
        return _run(["objdump", "-d", "-M", "intel", path])


def python_eval(code: str) -> str:
    """Execute a Python snippet and return the result."""
    return _run(["python3", "-c", code])


# ---------------------------------------------------------------------------
# Tool dispatcher — called by loop.py
# ---------------------------------------------------------------------------

def execute(tool_name: str, args: dict, challenge_dir: str) -> str:
    """
    Execute a tool by name with arguments.

    - file/strings: run locally against artifacts/
    - run_binary: execute via Docker
    - python_eval: run locally
    """
    artifacts_dir = Path(challenge_dir) / "artifacts"
    # challenges_root is the parent of the challenge dir (must be absolute for Docker mount)
    challenges_root = str(Path(challenge_dir).parent.resolve())

    def _find_binary() -> str:
        """Find the first non-hidden file in artifacts/."""
        for f in sorted(artifacts_dir.iterdir()):
            if f.is_file() and f.name != ".DS_Store":
                return str(f)
        return str(artifacts_dir)

    def _resolve_local(path: str) -> str:
        """Resolve a path relative to artifacts/, or auto-find binary."""
        if not path:
            return _find_binary()
        if not path.startswith("/"):
            return str(artifacts_dir / path)
        return path

    # --- Local tools ---

    if tool_name == "file":
        path = _resolve_local(args.get("path", args.get("file", "")))
        return file_info(path)

    if tool_name == "strings":
        path = _resolve_local(args.get("path", args.get("file", "")))
        return strings(path)

    if tool_name == "disasm":
        path = _resolve_local(args.get("path", args.get("file", "")))
        function = args.get("function", "")
        return disasm(path, function)

    if tool_name == "python_eval":
        code = args.get("code", "")
        if not code:
            return "[error] python_eval requires code. Usage: TOOL: python_eval(print('hello'))"
        return python_eval(code)

    # --- Docker tool: run_binary ---

    if tool_name == "run_binary":
        input_arg = args.get("input", args.get("args", ""))
        if not input_arg:
            return "[error] run_binary requires input. Usage: TOOL: run_binary(your_test_input_here)"
        binary = str(Path(_resolve_local(args.get("binary", ""))).resolve())
        return run_binary(challenges_root, binary, input_arg)

    return (f"[error] unknown tool: {tool_name}. "
            f"Available tools: file(), strings(), disasm(), disasm(FUNCTION), "
            f"run_binary(INPUT), python_eval(CODE)")
