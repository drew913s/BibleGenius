"""
Markdown parser — splits YAML frontmatter from body, extracts wikilinks and steps blocks.

No LLM. Pure text munging.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Node:
    """A loaded markdown node: frontmatter + body + source path (relative to project root)."""
    frontmatter: dict[str, Any]
    body: str
    source: str  # relative path like "corpus/concepts/forward_pass.md"

    @property
    def name(self) -> str:
        return self.frontmatter.get("name", Path(self.source).stem)

    @property
    def keywords(self) -> list[str]:
        return [str(k).lower() for k in self.frontmatter.get("keywords", [])]


_FM_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_STEPS_BLOCK_RE = re.compile(r"```yaml\s*\n(steps:.*?)\n```", re.DOTALL)
_NAMED_BLOCK_RE = re.compile(r"```(\w+)\s*\n(.*?)\n```", re.DOTALL)


def load_node(path: Path, project_root: Path) -> Node:
    """Read a .md file and return a Node."""
    text = path.read_text(encoding="utf-8")
    match = _FM_RE.match(text)
    if match:
        fm = yaml.safe_load(match.group(1)) or {}
        body = match.group(2).strip()
    else:
        fm = {}
        body = text.strip()
    rel = str(path.relative_to(project_root))
    return Node(frontmatter=fm, body=body, source=rel)


def extract_wikilinks(body: str) -> list[str]:
    """Return all [[wikilink]] targets in a body."""
    return _WIKILINK_RE.findall(body)


def extract_steps(orchestration_body: str) -> list[dict[str, Any]]:
    """Pull the `steps:` YAML block out of an orchestration file."""
    match = _STEPS_BLOCK_RE.search(orchestration_body)
    if not match:
        raise ValueError("No ```yaml steps:``` block found in orchestration file")
    parsed = yaml.safe_load(match.group(1))
    steps = parsed.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("`steps:` must be a list")
    return steps


def extract_named_blocks(body: str) -> dict[str, str]:
    """Pull named code blocks (\\`\\`\\`templatename\\n...\\n\\`\\`\\`) into {name: content}."""
    blocks: dict[str, str] = {}
    for match in _NAMED_BLOCK_RE.finditer(body):
        name = match.group(1)
        if name == "yaml":
            continue  # skip the steps block
        blocks[name] = match.group(2).strip()
    return blocks


def extract_sections(body: str) -> dict[str, str]:
    """Split a markdown body by `## Heading` into {heading_slug: content}.

    Section content is then addressable from templates as `{node.heading_slug}`.
    """
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = _slug(m.group(1))
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def _slug(heading: str) -> str:
    """'Summary — short version' -> 'summary'. Strips punctuation, takes first word."""
    h = heading.lower()
    h = re.sub(r"[^\w\s-]", " ", h)
    h = re.split(r"\s+", h.strip())[0]
    return h
