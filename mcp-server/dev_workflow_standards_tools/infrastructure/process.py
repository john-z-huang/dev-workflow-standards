"""Fixed argument-vector process invocation."""

import subprocess


def _run_fixed(args: list[str], *, cwd: str | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a fixed argument vector without invoking a shell."""
    return subprocess.run(args, cwd=cwd, input=input_text, capture_output=True, text=True, check=False)
