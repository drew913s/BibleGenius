"""
Lie detector #1: runner/ may import only from a small allowlist of safe modules.

Stated positively (what IS allowed) instead of negatively (a blocklist of brand-name
model libraries that would always be incomplete as new providers emerge). Any import
outside the allowlist fails the test.
"""
import ast
import sys
from pathlib import Path

RUNNER_DIR = Path(__file__).parent.parent / "runner"

# Standard library + declared framework dependencies. Nothing else may appear in runner/.
ALLOWED_IMPORTS = (
    set(getattr(sys, "stdlib_module_names", set()))
    | {"fastapi", "pydantic", "uvicorn", "yaml", "httpx", "starlette", "pytest", "anyio"}
    | {"runner"}
)
ALLOWED_IMPORTS |= {"__future__", "collections", "typing", "dataclasses", "pathlib"}


def _collect_imports(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
    return found


def test_runner_imports_only_from_allowlist():
    py_files = list(RUNNER_DIR.glob("*.py"))
    assert py_files, f"No Python files in {RUNNER_DIR}"

    violations = []
    for py in py_files:
        tree = ast.parse(py.read_text())
        imports = _collect_imports(tree)
        bad = imports - ALLOWED_IMPORTS
        if bad:
            violations.append((py.name, bad))

    assert not violations, (
        "runner/ imported modules outside the architectural allowlist:\n"
        + "\n".join(f"  {name}: {sorted(bad)}" for name, bad in violations)
        + "\n\nAllowed: stdlib + {fastapi, pydantic, uvicorn, yaml, httpx, runner}."
        + " Any other import means a model library or external service is being smuggled in."
    )
