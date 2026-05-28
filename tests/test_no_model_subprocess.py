"""
Lie detector #3: runner/ may not invoke any subprocess.

Stated as a hard ban rather than a blocklist of binary names. The runtime is pure
file I/O + pattern matching + template substitution. If the runtime ever needs to
shell out, that is a redesign signal, not a cue to allowlist a specific binary.

Tests themselves are exempt (test_endpoint.py spawns the server) because tests are
not the runtime. This file checks runner/*.py only.
"""
import ast
from pathlib import Path

RUNNER_DIR = Path(__file__).parent.parent / "runner"

# Attribute names that constitute shell-out backdoors when invoked as os.<attr> / pty.<attr>
_BACKDOOR_ATTRS = {"sys" + "tem", "popen", "execv", "execve", "execvp", "execvpe", "spawn"}


def _imports_subprocess(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "subprocess":
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "subprocess":
                return True
    return False


def _uses_exec_backdoors(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _BACKDOOR_ATTRS:
            hits.append(node.attr)
    return hits


def test_runner_does_not_use_subprocess():
    py_files = list(RUNNER_DIR.glob("*.py"))
    assert py_files, f"No Python files in {RUNNER_DIR}"

    violations = []
    for py in py_files:
        tree = ast.parse(py.read_text())
        if _imports_subprocess(tree):
            violations.append((py.name, "imports subprocess module"))
        backdoor_hits = _uses_exec_backdoors(tree)
        if backdoor_hits:
            violations.append((py.name, f"uses shell-out backdoors: {sorted(set(backdoor_hits))}"))

    assert not violations, (
        "runner/ contains subprocess invocations — architecture violated:\n"
        + "\n".join(f"  {name}: {detail}" for name, detail in violations)
        + "\n\nThe runtime is pure file I/O + pattern matching + template substitution."
        " Shelling out is how external services and model binaries sneak back into the inference path."
    )
