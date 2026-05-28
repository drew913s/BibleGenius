"""
Lie detector #4: every response must list provenance — real corpus files that contributed.

If provenance is empty, the runtime hallucinated. If a cited file doesn't exist, the runtime lied.
For Bible Genius this also means: when a verse is returned, the file under corpus/verses/<book>/
that holds that verse MUST be in the provenance list.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus"
sys.path.insert(0, str(ROOT))

try:
    from runner.engine import execute  # noqa: E402
    RUNNER_AVAILABLE = True
except ImportError:
    RUNNER_AVAILABLE = False


SCENARIOS = [
    {"orchestration": "verse_lookup",   "inputs": {"question": "John 3:16"},
     "expect_path": "corpus/verses/john/3_16.md"},
    {"orchestration": "verse_lookup",   "inputs": {"question": "Genesis 1:1"},
     "expect_path": "corpus/verses/genesis/1_1.md"},
    {"orchestration": "verse_lookup",   "inputs": {"question": "3 John 1:13"},
     "expect_path": "corpus/verses/3john/1_13.md"},
    {"orchestration": "verse_lookup",   "inputs": {"question": "1 Samuel 17:45"},
     "expect_path": "corpus/verses/1samuel/17_45.md"},
    {"orchestration": "verse_lookup",   "inputs": {"question": "Matt 5:3"},
     "expect_path": "corpus/verses/matthew/5_3.md"},
    {"orchestration": "topical_search", "inputs": {"question": "verses about forgiveness"},
     "expect_path": "corpus/topics/forgiveness.md"},
    {"orchestration": "topical_search", "inputs": {"question": "what does the bible say about faith"},
     "expect_path": "corpus/topics/faith.md"},
]


@pytest.mark.skipif(not RUNNER_AVAILABLE, reason="runner not importable")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["inputs"]["question"][:40])
def test_response_has_provenance(scenario):
    result = execute(scenario["orchestration"], scenario["inputs"])

    assert "output" in result
    assert "provenance" in result
    assert isinstance(result["provenance"], list)
    assert len(result["provenance"]) > 0, (
        f"Empty provenance for {scenario!r} — the runtime produced output without citing any files."
    )

    for src in result["provenance"]:
        full = ROOT / src
        assert full.exists(), f"Provenance cites {src!r} which does not exist on disk."
        assert full.is_relative_to(CORPUS) or full.is_relative_to(ROOT / "orchestration"), (
            f"Provenance cites {src!r} which is outside corpus/ and orchestration/."
        )

    expected = scenario["expect_path"]
    assert expected in result["provenance"], (
        f"Expected provenance to cite {expected!r} but it was missing. "
        f"Actual provenance: {result['provenance']}"
    )


@pytest.mark.skipif(not RUNNER_AVAILABLE, reason="runner not importable")
def test_response_output_non_empty():
    for scenario in SCENARIOS:
        result = execute(scenario["orchestration"], scenario["inputs"])
        output = result.get("output", "")
        assert output and output.strip(), f"Empty output for {scenario!r}"
        assert len(output) > 20, f"Output too short for {scenario!r}: {output!r}"


@pytest.mark.skipif(not RUNNER_AVAILABLE, reason="runner not importable")
def test_dont_know_path_returns_identity_node():
    """A query that cannot be parsed as a reference must fall through to corpus/identity/dont_know.md."""
    result = execute("verse_lookup", {"question": "asdfqwerty zxcvbnm not a reference"})
    assert "corpus/identity/dont_know.md" in result["provenance"], (
        f"Unmatched query did not fall through to dont_know. Provenance: {result['provenance']}"
    )
