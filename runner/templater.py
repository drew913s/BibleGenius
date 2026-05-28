"""
Template variable substitution.

Templates use {var.path} syntax. Lookups walk a context dict by dotted path.
NO eval(). NO exec(). Pure dict lookup.
"""
from __future__ import annotations

import re
from typing import Any


_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def lookup(path: str, context: dict[str, Any]) -> Any:
    """Walk a dotted path through a nested dict / list / object. Returns '' on miss.

    Numeric segments index into lists (e.g. 'items.0.name').
    """
    parts = path.split(".")
    cur: Any = context
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            if part.isdigit():
                idx = int(part)
                cur = cur[idx] if 0 <= idx < len(cur) else None
            else:
                return ""
        elif hasattr(cur, part):
            cur = getattr(cur, part)
        else:
            return ""
        if cur is None:
            return ""
    return cur


def render_template(template: str, context: dict[str, Any]) -> str:
    """Substitute {var.path} placeholders with their values from context.

    Runs a second pass to catch placeholders nested inside substituted content
    (e.g. {name} living inside a template-node body that was loaded into context).
    Any remaining unfilled placeholders are stripped silently — better an empty string
    than a literal "{name}" leaking to the user.
    """
    def replace(match: re.Match) -> str:
        path = match.group(1)
        val = lookup(path, context)
        if val is None or val == "":
            return ""
        return str(val)

    out = _VAR_RE.sub(replace, template)
    # Second pass for nested placeholders, then strip leftovers
    out = _VAR_RE.sub(replace, out)
    out = _VAR_RE.sub("", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    # Collapse multiple spaces left by stripped placeholders
    out = re.sub(r"  +", " ", out)
    return out.strip()
