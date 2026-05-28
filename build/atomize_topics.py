"""
Build-time atomizer: scan all verse nodes and emit topic cluster nodes.

For each seed topic (e.g. "forgiveness" → ["forgive", "forgave", "forgiven", "pardon"]),
score every verse by how many word forms appear in its body, then emit
corpus/topics/<topic_slug>.md with wikilinks to the top N verses.

The runtime never imports this. Topic nodes are pure markdown with [[wikilinks]];
follow_wikilinks in the runtime walks them at inference time.

Usage:
    python3 build/atomize_topics.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CORPUS = REPO_ROOT / "corpus"
VERSES_DIR = CORPUS / "verses"
TOPICS_DIR = CORPUS / "topics"

TOP_K_PER_TOPIC = 15

# Each topic has a slug, display name, keywords for user queries, and word-forms to scan verses for.
TOPICS: list[dict] = [
    {"slug": "forgiveness", "name": "Forgiveness",
     "keywords": ["forgiveness", "forgive", "pardon", "mercy", "release"],
     "forms": ["forgive", "forgiven", "forgave", "forgiving", "forgiveness", "pardon", "pardoned"]},
    {"slug": "faith", "name": "Faith",
     "keywords": ["faith", "believe", "trust", "belief", "believing"],
     "forms": ["faith", "faithful", "faithfulness", "believe", "believed", "believing", "believeth", "trust", "trusted"]},
    {"slug": "love", "name": "Love",
     "keywords": ["love", "loved", "loving", "charity", "beloved"],
     "forms": ["love", "loved", "loveth", "loving", "lover", "beloved", "charity"]},
    {"slug": "grace", "name": "Grace",
     "keywords": ["grace", "favor", "unmerited", "gracious"],
     "forms": ["grace", "gracious", "graciously"]},
    {"slug": "hope", "name": "Hope",
     "keywords": ["hope", "hoped", "expectation", "wait"],
     "forms": ["hope", "hoped", "hopeth", "hoping"]},
    {"slug": "prayer", "name": "Prayer",
     "keywords": ["prayer", "pray", "praying", "supplication", "intercede"],
     "forms": ["pray", "prayed", "prayer", "praying", "prayers", "supplication", "intercession"]},
    {"slug": "kingdom", "name": "Kingdom",
     "keywords": ["kingdom", "kings", "reign", "throne", "rule"],
     "forms": ["kingdom", "reign", "reigned", "throne", "thrones"]},
    {"slug": "anointing", "name": "Anointing",
     "keywords": ["anoint", "anointed", "anointing", "messiah", "christ"],
     "forms": ["anoint", "anointed", "anointing", "anointest", "messiah"]},
    {"slug": "salvation", "name": "Salvation",
     "keywords": ["salvation", "saved", "save", "saviour", "deliver", "redeemed"],
     "forms": ["salvation", "save", "saved", "saveth", "saviour", "savior", "redeem", "redeemed", "redemption"]},
    {"slug": "judgment", "name": "Judgment",
     "keywords": ["judgment", "judge", "judging", "justice"],
     "forms": ["judge", "judged", "judgeth", "judging", "judgment", "judgments", "judges"]},
    {"slug": "wisdom", "name": "Wisdom",
     "keywords": ["wisdom", "wise", "understanding", "knowledge", "prudent"],
     "forms": ["wisdom", "wise", "wiser", "wisely", "prudent", "prudence"]},
    {"slug": "fear", "name": "Fear of the Lord",
     "keywords": ["fear", "feared", "reverence", "awe", "afraid"],
     "forms": ["fear", "feared", "feareth", "fearing", "fearful", "afraid"]},
    {"slug": "joy", "name": "Joy",
     "keywords": ["joy", "rejoice", "glad", "gladness", "happy"],
     "forms": ["joy", "joyful", "joyous", "rejoice", "rejoiced", "rejoicing", "glad", "gladness"]},
    {"slug": "peace", "name": "Peace",
     "keywords": ["peace", "peaceful", "peacemaker", "shalom"],
     "forms": ["peace", "peaceful", "peacemaker", "peacemakers", "peaceably"]},
    {"slug": "righteousness", "name": "Righteousness",
     "keywords": ["righteousness", "righteous", "just", "upright"],
     "forms": ["righteous", "righteousness", "righteously"]},
    {"slug": "sin", "name": "Sin",
     "keywords": ["sin", "sins", "sinful", "iniquity", "transgression", "trespass"],
     "forms": ["sin", "sins", "sinned", "sinneth", "sinful", "sinner", "sinners", "iniquity", "iniquities", "transgress", "transgression", "trespass"]},
    {"slug": "covenant", "name": "Covenant",
     "keywords": ["covenant", "promise", "oath", "bond"],
     "forms": ["covenant", "covenants", "covenanted"]},
    {"slug": "resurrection", "name": "Resurrection",
     "keywords": ["resurrection", "raised", "risen", "rose", "rise"],
     "forms": ["resurrection", "raised", "raise", "risen", "rose", "rising", "arise", "arose"]},
    {"slug": "spirit", "name": "Holy Spirit",
     "keywords": ["spirit", "holy ghost", "comforter", "holy spirit"],
     "forms": ["spirit", "spirits", "spiritual", "ghost", "comforter"]},
    {"slug": "shepherd", "name": "Shepherd",
     "keywords": ["shepherd", "sheep", "flock", "pasture", "lamb"],
     "forms": ["shepherd", "shepherds", "sheep", "flock", "flocks", "lamb", "lambs"]},
    {"slug": "light", "name": "Light",
     "keywords": ["light", "shine", "lamp", "illumine"],
     "forms": ["light", "lights", "lighted", "lighten", "shineth", "shine", "shining", "lamp", "lamps", "candle"]},
    {"slug": "darkness", "name": "Darkness",
     "keywords": ["darkness", "dark", "night", "shadow"],
     "forms": ["darkness", "dark", "darkened", "darkeneth"]},
    {"slug": "bread", "name": "Bread",
     "keywords": ["bread", "loaves", "manna", "food", "feed"],
     "forms": ["bread", "loaves", "loaf", "manna"]},
    {"slug": "blood", "name": "Blood",
     "keywords": ["blood", "shed", "sacrifice", "atonement"],
     "forms": ["blood", "bloody", "bloodshed"]},
    {"slug": "name", "name": "The Name",
     "keywords": ["name", "called", "calleth", "renamed"],
     "forms": ["name", "names", "named"]},
    {"slug": "glory", "name": "Glory",
     "keywords": ["glory", "glorified", "glorify", "glorious"],
     "forms": ["glory", "glorified", "glorify", "glorifying", "glorious", "gloriously"]},
    {"slug": "eternal", "name": "Eternal Life",
     "keywords": ["eternal", "everlasting", "forever", "immortal"],
     "forms": ["eternal", "everlasting", "forever", "evermore", "immortal", "immortality"]},
    {"slug": "repentance", "name": "Repentance",
     "keywords": ["repent", "repentance", "turn", "return"],
     "forms": ["repent", "repented", "repenteth", "repenting", "repentance"]},
    {"slug": "truth", "name": "Truth",
     "keywords": ["truth", "true", "verity"],
     "forms": ["truth", "true", "truly", "truths", "verity"]},
    {"slug": "creation", "name": "Creation",
     "keywords": ["creation", "create", "created", "creator", "made", "make"],
     "forms": ["create", "created", "creator", "creation", "creature"]},
]


_FORM_BOUNDARY = re.compile(r"\b")
_BODY_TEXT_RE = re.compile(r"## summary\n\n(.+?)(?:\n\n##|\Z)", re.DOTALL)
_REF_RE = re.compile(r'reference:\s*"([^"]+)"')
_SLUG_RE = re.compile(r"book_slug:\s*(\w+)")
_CHAP_RE = re.compile(r"chapter:\s*(\d+)")
_VERSE_RE = re.compile(r"verse:\s*(\d+)")


def _score_verse(body_text: str, forms: list[str]) -> int:
    """Count word-form hits in a verse body. Word-boundary matching."""
    lower = body_text.lower()
    score = 0
    for form in forms:
        # match as word boundary - count occurrences
        pattern = r"\b" + re.escape(form) + r"\w*\b"
        score += len(re.findall(pattern, lower))
    return score


def _yaml_list(items: list[str]) -> str:
    parts = []
    for it in items:
        if re.search(r"[:\#\[\]\{\},'\"\n]", it) or " " in it:
            parts.append('"' + it.replace('"', '\\"') + '"')
        else:
            parts.append(it)
    return "[" + ", ".join(parts) + "]"


def main() -> None:
    print("Loading verse corpus ...")
    verse_files = list(VERSES_DIR.rglob("*.md"))
    print(f"  {len(verse_files)} verses")

    # Pre-read all verses once: extract (body_text, ref, wikilink_path)
    print("Indexing verse bodies ...")
    verses: list[tuple[str, str, str, str]] = []  # (body_lower, reference, wikilink, fullpath)
    for vf in verse_files:
        text = vf.read_text(encoding="utf-8")
        m_body = _BODY_TEXT_RE.search(text)
        if not m_body:
            continue
        body = m_body.group(1).strip()
        m_ref = _REF_RE.search(text)
        m_slug = _SLUG_RE.search(text)
        m_chap = _CHAP_RE.search(text)
        m_verse = _VERSE_RE.search(text)
        if not (m_ref and m_slug and m_chap and m_verse):
            continue
        ref = m_ref.group(1)
        wikilink = f"verses/{m_slug.group(1)}/{m_chap.group(1)}_{m_verse.group(1)}"
        verses.append((body.lower(), ref, wikilink, body))
    print(f"  indexed {len(verses)}")

    TOPICS_DIR.mkdir(parents=True, exist_ok=True)

    for topic in TOPICS:
        slug = topic["slug"]
        name = topic["name"]
        forms = topic["forms"]
        kws = topic["keywords"]

        # Score every verse for this topic
        scored: list[tuple[int, str, str, str]] = []
        for body_lower, ref, wikilink, body in verses:
            s = _score_verse(body_lower, forms)
            if s > 0:
                scored.append((s, ref, wikilink, body))
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:TOP_K_PER_TOPIC]

        # Build topic node
        all_kws = list(dict.fromkeys(kws + [name.lower(), slug, "topic", "verses", "about"]))
        wikilinks_md = "\n".join(f"- [[{wl}]] — {ref}" for _, ref, wl, _ in top)
        # Short preview lines: first 8 verses with text
        preview_md = "\n\n".join(
            f"**{ref}** — {body.strip()}"
            for _, ref, _, body in top[:8]
        ) or "_(no verses indexed for this topic)_"

        fm = (
            "---\n"
            f"name: topic_{slug}\n"
            "type: topic\n"
            f"topic: {name}\n"
            f"keywords: {_yaml_list(all_kws)}\n"
            "---\n"
        )
        body_md = (
            f"# {name}\n\n"
            f"## summary\n\n"
            f"Verses related to **{name.lower()}** in the King James Bible. "
            f"The top {len(top)} verses below are surfaced by word-form match against the corpus "
            f"and linked into the graph — click any reference to read the source.\n\n"
            f"## verses\n\n"
            f"{wikilinks_md if wikilinks_md else '_(no matches found — corpus may be incomplete)_'}\n\n"
            f"## preview\n\n"
            f"{preview_md}\n"
        )
        out = TOPICS_DIR / f"{slug}.md"
        out.write_text(fm + body_md, encoding="utf-8")
        print(f"  topic '{slug}' → {len(top)} verses")

    print(f"\nDone. {len(TOPICS)} topic nodes written to {TOPICS_DIR}.")


if __name__ == "__main__":
    main()
