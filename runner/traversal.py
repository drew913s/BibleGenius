"""
Graph traversal over markdown nodes.

Uses keyword overlap scoring + frontmatter field matching + wikilink following.
NO embeddings. NO vectors. NO model.

Adds an mtime-keyed in-process cache of parsed nodes + their precomputed token sets,
so 31k-verse subgraphs are usable at chat latency. Pure IO optimization — does not
change scoring semantics. First query warms the cache; subsequent queries are fast.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.parser import Node, load_node, extract_wikilinks


_TOKENIZE_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "their",
    "this", "that", "these", "those", "but", "if", "for", "with", "from",
    "in", "on", "at", "by", "as", "not", "no", "yes", "so", "too", "very",
    "just", "now", "then", "here", "there", "what", "who", "where", "when",
    "why", "how", "can", "could", "would", "should", "will", "may", "might",
    "am", "me", "us", "him", "her", "them", "our",
}


def tokenize(text: str) -> set[str]:
    """Lowercase + split on non-alphanumerics + drop stopwords. Pure text munging."""
    tokens = set(_TOKENIZE_RE.findall(text.lower()))
    return tokens - _STOPWORDS


@dataclass
class _CachedNode:
    """A parsed Node plus its precomputed token sets, keyed by file mtime."""
    node: Node
    fm_tokens: set[str]
    body_tokens: set[str]
    mtime_ns: int


_NODE_CACHE: dict[str, _CachedNode] = {}
_SUBGRAPH_LIST_CACHE: dict[str, tuple[int, list[Path]]] = {}


def _load_cached(md_path: Path, project_root: Path) -> _CachedNode:
    """Return a _CachedNode, reusing a prior parse if the file's mtime hasn't changed."""
    key = str(md_path)
    try:
        mtime_ns = md_path.stat().st_mtime_ns
    except FileNotFoundError:
        _NODE_CACHE.pop(key, None)
        raise

    cached = _NODE_CACHE.get(key)
    if cached is not None and cached.mtime_ns == mtime_ns:
        return cached

    node = load_node(md_path, project_root)
    fm_tokens: set[str] = set()
    for kw in node.keywords:
        fm_tokens.update(tokenize(kw))
    fm_tokens.update(tokenize(node.name))
    body_tokens = tokenize(node.body)

    cached = _CachedNode(
        node=node,
        fm_tokens=fm_tokens,
        body_tokens=body_tokens,
        mtime_ns=mtime_ns,
    )
    _NODE_CACHE[key] = cached
    return cached


def _list_subgraph(subgraph_path: Path) -> list[Path]:
    """List .md files in a subgraph, cached by directory mtime."""
    key = str(subgraph_path)
    try:
        dir_mtime = subgraph_path.stat().st_mtime_ns
    except FileNotFoundError:
        _SUBGRAPH_LIST_CACHE.pop(key, None)
        return []

    cached = _SUBGRAPH_LIST_CACHE.get(key)
    if cached is not None and cached[0] == dir_mtime:
        return cached[1]

    files = list(subgraph_path.rglob("*.md"))
    _SUBGRAPH_LIST_CACHE[key] = (dir_mtime, files)
    return files


def load_subgraph(subgraph_path: Path, project_root: Path) -> list[Node]:
    """Load all .md files under a subgraph directory recursively (cached)."""
    if not subgraph_path.exists():
        return []
    return [_load_cached(md, project_root).node for md in _list_subgraph(subgraph_path)]


def _score_cached(cached: _CachedNode, query_tokens: set[str]) -> int:
    """Score using precomputed token sets — fast path used by find_best_node / find_top_nodes."""
    fm_overlap = len(query_tokens & cached.fm_tokens)
    body_overlap = len(query_tokens & cached.body_tokens)
    return fm_overlap * 3 + body_overlap


def score_node(node: Node, query_tokens: set[str]) -> int:
    """Score a node by keyword overlap. Frontmatter keywords are weighted 3x.

    Kept for orchestrations / tools that hold raw Nodes without a cached envelope.
    """
    body_tokens = tokenize(node.body)
    fm_tokens: set[str] = set()
    for kw in node.keywords:
        fm_tokens.update(tokenize(kw))
    fm_tokens.update(tokenize(node.name))

    body_overlap = len(query_tokens & body_tokens)
    fm_overlap = len(query_tokens & fm_tokens)
    return fm_overlap * 3 + body_overlap


def find_best_node(
    subgraph_path: Path,
    project_root: Path,
    query: str,
    name_hint: str | None = None,
) -> tuple[Node | None, int]:
    """Find the highest-scoring node in a subgraph for a given query string.

    name_hint: if provided, a node whose filename stem matches gets a large bonus.
    """
    if not subgraph_path.exists():
        return (None, -1)

    query_tokens = tokenize(query)
    best_node: Node | None = None
    best_score = -1
    for md in _list_subgraph(subgraph_path):
        cached = _load_cached(md, project_root)
        score = _score_cached(cached, query_tokens)
        if name_hint and md.stem == name_hint:
            score += 100
        if score > best_score:
            best_score = score
            best_node = cached.node
    return (best_node, best_score)


def find_top_nodes(
    subgraph_path: Path,
    project_root: Path,
    query: str,
    top_k: int = 3,
) -> list[Node]:
    """Return top_k nodes from a subgraph sorted by score (filter score > 0)."""
    if not subgraph_path.exists():
        return []

    query_tokens = tokenize(query)
    scored: list[tuple[int, Node]] = []
    for md in _list_subgraph(subgraph_path):
        cached = _load_cached(md, project_root)
        s = _score_cached(cached, query_tokens)
        if s > 0:
            scored.append((s, cached.node))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]


def follow_wikilinks(node: Node, project_root: Path, max_links: int = 5) -> list[Node]:
    """Load nodes referenced by [[wikilinks]] in a node's body. One hop only."""
    out: list[Node] = []
    for link in extract_wikilinks(node.body)[:max_links]:
        target = project_root / "corpus" / f"{link}.md"
        if target.exists():
            out.append(load_node(target, project_root))
    return out


def resolve_path(target: str, project_root: Path) -> Path:
    """Resolve a string like 'identity/voice_principles' to corpus/identity/voice_principles.md."""
    if target.endswith(".md"):
        return project_root / "corpus" / target
    return project_root / "corpus" / f"{target}.md"


# Exposed for tests / debugging — drops the in-process cache.
def _clear_cache() -> None:
    _NODE_CACHE.clear()
    _SUBGRAPH_LIST_CACHE.clear()
