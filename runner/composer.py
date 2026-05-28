"""
Composer — given an orchestration step result context, fills a template.

Templates live as named code blocks in orchestration files. The composer pulls them out
and runs them through the templater.
"""
from __future__ import annotations

from typing import Any

from runner.parser import Node, extract_named_blocks
from runner.templater import render_template


def compose(
    template_name: str,
    orchestration_body: str,
    context: dict[str, Any],
) -> str:
    """Look up the named template block in the orchestration file, render it."""
    blocks = extract_named_blocks(orchestration_body)
    if template_name not in blocks:
        raise ValueError(
            f"Template {template_name!r} not found in orchestration. "
            f"Available: {sorted(blocks.keys())}"
        )
    return render_template(blocks[template_name], context)


def node_as_dict(node: Node) -> dict[str, Any]:
    """Flatten a Node into a dict for template lookups. Includes frontmatter + body sections."""
    from runner.parser import extract_sections

    d: dict[str, Any] = dict(node.frontmatter)
    d["body"] = node.body
    d["source"] = node.source
    sections = extract_sections(node.body)
    d.update(sections)
    return d
