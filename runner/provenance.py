"""
Provenance tracking — every loaded file gets added to a list.

This is what makes the framework auditable: every output ships with its sources.
"""
from __future__ import annotations


class Provenance:
    """Ordered, deduped list of file paths that contributed to a response."""

    def __init__(self) -> None:
        self._paths: list[str] = []
        self._seen: set[str] = set()

    def add(self, source: str) -> None:
        if source in self._seen:
            return
        self._seen.add(source)
        self._paths.append(source)

    def add_many(self, sources: list[str]) -> None:
        for s in sources:
            self.add(s)

    def as_list(self) -> list[str]:
        return list(self._paths)
