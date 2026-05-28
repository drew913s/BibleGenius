"""
Lie detector #5: deleting a corpus file must visibly change behavior.

If you can delete a file and the output is identical, the file wasn't load-bearing — meaning
either (a) the runtime hardcoded a fallback, or (b) the orchestration didn't actually use it.
Both kill the architectural claim that knowledge lives in the markdown.

For Bible Genius: move John 3:16 aside, query for it, assert the response is different.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from runner.engine import execute  # noqa: E402
    from runner.traversal import _clear_cache  # noqa: E402
    RUNNER_AVAILABLE = True
except ImportError:
    RUNNER_AVAILABLE = False


@pytest.mark.skipif(not RUNNER_AVAILABLE, reason="runner not importable")
def test_deleting_verse_node_changes_behavior(tmp_path):
    """Move corpus/verses/john/3_16.md aside, ask for John 3:16, assert the answer changes."""
    target = ROOT / "corpus" / "verses" / "john" / "3_16.md"
    if not target.exists():
        pytest.skip(f"{target} not present — corpus incomplete")

    inputs = {"question": "John 3:16"}
    _clear_cache()
    baseline = execute("verse_lookup", inputs)["output"]
    assert "everlasting life" in baseline.lower() or "begotten" in baseline.lower(), (
        f"Baseline did not return John 3:16 content — orchestration is broken before the test even runs. "
        f"Got: {baseline[:200]!r}"
    )

    backup = tmp_path / "3_16.md.bak"
    shutil.move(str(target), str(backup))
    try:
        _clear_cache()
        degraded = execute("verse_lookup", inputs)["output"]
    finally:
        shutil.move(str(backup), str(target))
        _clear_cache()

    assert baseline != degraded, (
        "Deleting corpus/verses/john/3_16.md did not change behavior. "
        "Either the runtime is using a hardcoded fallback or the orchestration is broken."
    )
    assert "everlasting life" not in degraded.lower() and "begotten" not in degraded.lower(), (
        f"Even after deleting John 3:16, the response still contains its content — fallback leak. Got: {degraded[:200]!r}"
    )


@pytest.mark.skipif(not RUNNER_AVAILABLE, reason="runner not importable")
def test_deleting_topic_node_changes_behavior(tmp_path):
    """Same contract for topical search: deleting corpus/topics/forgiveness.md must change output."""
    target = ROOT / "corpus" / "topics" / "forgiveness.md"
    if not target.exists():
        pytest.skip(f"{target} not present")

    inputs = {"question": "what does the bible say about forgiveness"}
    _clear_cache()
    baseline = execute("topical_search", inputs)["output"]

    backup = tmp_path / "forgiveness.md.bak"
    shutil.move(str(target), str(backup))
    try:
        _clear_cache()
        degraded = execute("topical_search", inputs)["output"]
    finally:
        shutil.move(str(backup), str(target))
        _clear_cache()

    assert baseline != degraded, (
        "Deleting corpus/topics/forgiveness.md did not change behavior."
    )
