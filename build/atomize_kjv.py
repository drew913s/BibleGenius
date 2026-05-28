"""
Build-time atomizer: convert the King James Bible (kjv.json) into MLM corpus nodes.

For each of 31,100 verses, emits one markdown file under corpus/verses/<book_slug>/<chap>_<verse>.md
with YAML frontmatter (name, type, book, chapter, verse, reference, keywords, related) and a body
containing the verse text plus a reference section.

For each of 66 books, emits one index node under corpus/books/<book_slug>.md with the book's
name, aliases, abbreviations, chapter/verse counts, and wikilinks to its first few chapters.

This script is BUILD-TIME ONLY. It does not run at inference time. The MLM runtime never imports it.
No LLM is involved at any step — pure JSON → markdown transformation.

Usage:
    python3 build/atomize_kjv.py /path/to/kjv.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CORPUS = REPO_ROOT / "corpus"

# Map kjv.json abbreviation → (full_name, slug, ordinal_1_based, aliases_for_keywords)
# Aliases include common abbreviations (mt, matt, mat) and ordinal-prose forms (first samuel, 1st samuel).
BOOKS: list[tuple[str, str, str, list[str]]] = [
    ("gn",   "Genesis",         "genesis",        ["gen", "gn"]),
    ("ex",   "Exodus",          "exodus",         ["ex", "exo", "exod"]),
    ("lv",   "Leviticus",       "leviticus",      ["lev", "lv", "levit"]),
    ("nm",   "Numbers",         "numbers",        ["num", "nm", "nb"]),
    ("dt",   "Deuteronomy",     "deuteronomy",    ["deut", "dt", "deu"]),
    ("js",   "Joshua",          "joshua",         ["josh", "jos", "js"]),
    ("jud",  "Judges",          "judges",         ["judg", "jdg", "jud"]),
    ("rt",   "Ruth",            "ruth",           ["rt", "ru"]),
    ("1sm",  "1 Samuel",        "1samuel",        ["1sam", "1sm", "1 samuel", "1st samuel", "first samuel", "i samuel"]),
    ("2sm",  "2 Samuel",        "2samuel",        ["2sam", "2sm", "2 samuel", "2nd samuel", "second samuel", "ii samuel"]),
    ("1kgs", "1 Kings",         "1kings",         ["1kgs", "1ki", "1 kings", "1st kings", "first kings", "i kings"]),
    ("2kgs", "2 Kings",         "2kings",         ["2kgs", "2ki", "2 kings", "2nd kings", "second kings", "ii kings"]),
    ("1ch",  "1 Chronicles",    "1chronicles",    ["1chr", "1ch", "1 chronicles", "1st chronicles", "first chronicles", "i chronicles"]),
    ("2ch",  "2 Chronicles",    "2chronicles",    ["2chr", "2ch", "2 chronicles", "2nd chronicles", "second chronicles", "ii chronicles"]),
    ("ezr",  "Ezra",            "ezra",           ["ezra", "ezr"]),
    ("ne",   "Nehemiah",        "nehemiah",       ["neh", "ne"]),
    ("et",   "Esther",          "esther",         ["est", "et", "esth"]),
    ("job",  "Job",             "job",            ["job", "jb"]),
    ("ps",   "Psalms",          "psalms",         ["psa", "ps", "psalm", "psalms"]),
    ("prv",  "Proverbs",        "proverbs",       ["prov", "pro", "prv"]),
    ("ec",   "Ecclesiastes",    "ecclesiastes",   ["ecc", "ec", "eccl", "qoh"]),
    ("so",   "Song of Solomon", "songofsolomon",  ["song", "sos", "ss", "so", "song of songs", "canticles"]),
    ("is",   "Isaiah",          "isaiah",         ["isa", "is"]),
    ("jr",   "Jeremiah",        "jeremiah",       ["jer", "jr"]),
    ("lm",   "Lamentations",    "lamentations",   ["lam", "lm"]),
    ("ez",   "Ezekiel",         "ezekiel",        ["ezek", "ez", "eze"]),
    ("dn",   "Daniel",          "daniel",         ["dan", "dn"]),
    ("ho",   "Hosea",           "hosea",          ["hos", "ho"]),
    ("jl",   "Joel",            "joel",           ["jl", "joe"]),
    ("am",   "Amos",            "amos",           ["am", "amo"]),
    ("ob",   "Obadiah",         "obadiah",        ["oba", "ob", "obad"]),
    ("jn",   "Jonah",           "jonah",          ["jon", "jn", "jonh"]),
    ("mi",   "Micah",           "micah",          ["mic", "mi"]),
    ("na",   "Nahum",           "nahum",          ["nah", "na"]),
    ("hk",   "Habakkuk",        "habakkuk",       ["hab", "hk", "habk"]),
    ("zp",   "Zephaniah",       "zephaniah",      ["zep", "zp", "zeph"]),
    ("hg",   "Haggai",          "haggai",         ["hag", "hg"]),
    ("zc",   "Zechariah",       "zechariah",      ["zec", "zc", "zech"]),
    ("ml",   "Malachi",         "malachi",        ["mal", "ml"]),
    ("mt",   "Matthew",         "matthew",        ["matt", "mt", "mat"]),
    ("mk",   "Mark",            "mark",           ["mk", "mar", "mrk"]),
    ("lk",   "Luke",            "luke",           ["lk", "luk"]),
    ("jo",   "John",            "john",           ["jn", "jo", "joh"]),
    ("act",  "Acts",            "acts",           ["act", "ac", "acts of the apostles"]),
    ("rm",   "Romans",          "romans",         ["rom", "rm"]),
    ("1co",  "1 Corinthians",   "1corinthians",   ["1cor", "1co", "1 corinthians", "1st corinthians", "first corinthians", "i corinthians"]),
    ("2co",  "2 Corinthians",   "2corinthians",   ["2cor", "2co", "2 corinthians", "2nd corinthians", "second corinthians", "ii corinthians"]),
    ("gl",   "Galatians",       "galatians",      ["gal", "gl"]),
    ("eph",  "Ephesians",       "ephesians",      ["eph", "ep"]),
    ("ph",   "Philippians",     "philippians",    ["phil", "ph", "phili"]),
    ("cl",   "Colossians",      "colossians",     ["col", "cl", "colos"]),
    ("1ts",  "1 Thessalonians", "1thessalonians", ["1thess", "1ts", "1 thessalonians", "1st thessalonians", "first thessalonians", "i thessalonians"]),
    ("2ts",  "2 Thessalonians", "2thessalonians", ["2thess", "2ts", "2 thessalonians", "2nd thessalonians", "second thessalonians", "ii thessalonians"]),
    ("1tm",  "1 Timothy",       "1timothy",       ["1tim", "1tm", "1 timothy", "1st timothy", "first timothy", "i timothy"]),
    ("2tm",  "2 Timothy",       "2timothy",       ["2tim", "2tm", "2 timothy", "2nd timothy", "second timothy", "ii timothy"]),
    ("tt",   "Titus",           "titus",          ["tit", "tt"]),
    ("phm",  "Philemon",        "philemon",       ["phm", "philem", "phlm"]),
    ("hb",   "Hebrews",         "hebrews",        ["heb", "hb"]),
    ("jm",   "James",           "james",          ["jas", "jm", "jam"]),
    ("1pe",  "1 Peter",         "1peter",         ["1pet", "1pe", "1 peter", "1st peter", "first peter", "i peter"]),
    ("2pe",  "2 Peter",         "2peter",         ["2pet", "2pe", "2 peter", "2nd peter", "second peter", "ii peter"]),
    ("1jo",  "1 John",          "1john",          ["1jn", "1jo", "1 john", "1st john", "first john", "i john"]),
    ("2jo",  "2 John",          "2john",          ["2jn", "2jo", "2 john", "2nd john", "second john", "ii john"]),
    ("3jo",  "3 John",          "3john",          ["3jn", "3jo", "3 john", "3rd john", "third john", "iii john"]),
    ("jd",   "Jude",            "jude",           ["jud", "jd"]),
    ("re",   "Revelation",      "revelation",     ["rev", "re", "revelation of john", "apocalypse"]),
]


# KJV body words rarely useful for retrieval (preserved in text, dropped from keywords).
_LIGHT_STOPWORDS = {
    "thou", "thee", "thy", "thine", "ye", "shall", "unto", "behold", "lo",
    "saith", "said", "say", "saying", "spake", "spoken",
    "lord", "god",   # too generic to help discrimination — kept in body but not keywords
    "yea", "verily", "amen", "selah", "wherefore", "therefore",
    "let", "let's", "into", "out", "up", "down", "over", "under",
    "shalt", "wilt", "doth", "dost", "hast", "hath",
    "him", "her", "us", "them", "they", "their", "theirs",
    "all", "every", "any", "some", "none",
    "one", "two", "three",  # noisy numerics
    "also", "even", "only", "ever", "still", "yet",
    "before", "after", "again", "against",
    "good", "great", "many", "much", "more", "most",
}

_WORD_RE = re.compile(r"[A-Za-z]+")
_CURLY_NOTE_RE = re.compile(r"\{[^}]*:[^}]*\}")  # `{...: ...}` = translator marginal note — drop
_CURLY_ITALIC_RE = re.compile(r"\{([^}:]+)\}")    # `{word}` = KJV italicized supplied word — keep as *word*


def slugify_book(slug: str) -> str:
    """Filesystem-safe slug (already lowercased + no-spaces in BOOKS table)."""
    return slug


def clean_verse_text(raw: str) -> str:
    """KJV uses {...} for two purposes:
      - translator marginal notes with a colon, e.g. `{Heb: ...}` — drop entirely.
      - italicized supplied words, e.g. `{was}` — keep as markdown italics `*was*`.

    Leaving raw `{word}` would collide with the templater's `{var.path}` syntax and
    silently render to empty. The italic form is both faithful to KJV typography and safe.
    """
    text = _CURLY_NOTE_RE.sub("", raw)
    text = _CURLY_ITALIC_RE.sub(lambda m: f"*{m.group(1).strip()}*", text)
    return re.sub(r"\s+", " ", text).strip()


def content_keywords(verse_text: str, limit: int = 18) -> list[str]:
    """Return distinctive content words from a verse, lowercased, deduped."""
    seen: dict[str, int] = {}
    for word in _WORD_RE.findall(verse_text.lower()):
        if len(word) < 4:
            continue
        if word in _LIGHT_STOPWORDS:
            continue
        seen[word] = seen.get(word, 0) + 1
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


def verse_keywords(book_name: str, book_slug: str, aliases: list[str], chap: int, verse: int, text: str) -> list[str]:
    """Compose the searchable keyword list for one verse node."""
    kws: list[str] = []
    # Book identity (lowercased forms + aliases the user might type)
    kws.append(book_name.lower())
    kws.append(book_slug)
    for a in aliases:
        kws.append(a)
    # Pure-number tokens for chapter and verse — drives "John 3:16" → unique high score
    kws.append(str(chap))
    kws.append(str(verse))
    # Combined reference forms users may type
    kws.append(f"{book_slug} {chap} {verse}")
    kws.append(f"{book_slug}_{chap}_{verse}")
    kws.append(f"{book_name.lower()} {chap}:{verse}")
    # Distinctive content words
    kws.extend(content_keywords(text))
    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def yaml_list(items: list[str]) -> str:
    """Render a YAML flow sequence safely (quotes when needed)."""
    parts: list[str] = []
    for it in items:
        if re.search(r"[:\#\[\]\{\},'\"\n]", it) or " " in it:
            parts.append('"' + it.replace('"', '\\"') + '"')
        else:
            parts.append(it)
    return "[" + ", ".join(parts) + "]"


def write_verse_node(book_name: str, book_slug: str, aliases: list[str],
                     chap: int, verse: int, text: str, num_chapters: int, num_verses_in_chap: int) -> Path:
    """Emit corpus/verses/<book_slug>/<chap>_<verse>.md."""
    text = clean_verse_text(text)
    reference = f"{book_name} {chap}:{verse}"
    node_name = f"verse_{book_slug}_{chap}_{verse}"

    # Adjacent verses + previous chapter end + next chapter start, as wikilinks for cross-walking.
    related: list[str] = []
    if verse > 1:
        related.append(f"verses/{book_slug}/{chap}_{verse - 1}")
    if verse < num_verses_in_chap:
        related.append(f"verses/{book_slug}/{chap}_{verse + 1}")

    kws = verse_keywords(book_name, book_slug, aliases, chap, verse, text)

    fm = (
        "---\n"
        f"name: {node_name}\n"
        "type: verse\n"
        f"book: {book_name}\n"
        f"book_slug: {book_slug}\n"
        f"chapter: {chap}\n"
        f"verse: {verse}\n"
        f"reference: \"{reference}\"\n"
        f"translation: KJV\n"
        f"keywords: {yaml_list(kws)}\n"
        f"---\n"
    )

    related_md = "\n".join(f"- [[{link}]]" for link in related)
    body = (
        f"# {reference}\n\n"
        f"## summary\n\n"
        f"{text}\n\n"
        f"## reference\n\n"
        f"{reference} (KJV)\n\n"
        f"## related\n\n"
        f"{related_md if related_md else '_(no adjacent verses)_'}\n"
    )

    out_dir = CORPUS / "verses" / book_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{chap}_{verse}.md"
    out_path.write_text(fm + body, encoding="utf-8")
    return out_path


def write_book_node(book_name: str, book_slug: str, aliases: list[str],
                    book_index: int, num_chapters: int, num_verses: int) -> Path:
    """Emit corpus/books/<book_slug>.md — a book-level index node."""
    kws: list[str] = [book_name.lower(), book_slug] + aliases + ["book", "of"]
    # Dedupe
    seen: set[str] = set()
    kws = [k for k in kws if not (k in seen or seen.add(k))]

    testament = "Old Testament" if book_index < 39 else "New Testament"

    sample_chapters = "\n".join(
        f"- [[verses/{book_slug}/{i}_1]]" for i in range(1, min(num_chapters, 5) + 1)
    )

    fm = (
        "---\n"
        f"name: book_{book_slug}\n"
        "type: book\n"
        f"book: {book_name}\n"
        f"book_slug: {book_slug}\n"
        f"testament: \"{testament}\"\n"
        f"order: {book_index + 1}\n"
        f"chapters: {num_chapters}\n"
        f"verses: {num_verses}\n"
        f"keywords: {yaml_list(kws)}\n"
        "---\n"
    )
    body = (
        f"# {book_name}\n\n"
        f"## summary\n\n"
        f"{book_name} is book {book_index + 1} of the King James Bible "
        f"({testament}). It contains {num_chapters} chapter"
        f"{'s' if num_chapters != 1 else ''} and {num_verses} verses.\n\n"
        f"## opening_chapters\n\n"
        f"{sample_chapters}\n"
    )

    out_path = CORPUS / "books" / f"{book_slug}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(fm + body, encoding="utf-8")
    return out_path


def main(kjv_json_path: str) -> None:
    print(f"Loading {kjv_json_path} ...")
    with open(kjv_json_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    assert len(data) == len(BOOKS), f"Expected {len(BOOKS)} books, got {len(data)}"

    total_verses = 0
    total_books = 0

    for book_idx, (book, book_record) in enumerate(zip(BOOKS, data)):
        kj_abbrev, book_name, book_slug, aliases = book
        assert book_record["abbrev"] == kj_abbrev, (
            f"Book abbreviation mismatch at index {book_idx}: "
            f"expected {kj_abbrev}, got {book_record['abbrev']}"
        )

        chapters = book_record["chapters"]
        num_chapters = len(chapters)
        num_verses = sum(len(ch) for ch in chapters)

        # Book index node
        write_book_node(book_name, book_slug, aliases, book_idx, num_chapters, num_verses)
        total_books += 1

        # Verse nodes
        for chap_idx, chapter_verses in enumerate(chapters, start=1):
            num_v_in_chap = len(chapter_verses)
            for v_idx, verse_text in enumerate(chapter_verses, start=1):
                write_verse_node(
                    book_name, book_slug, aliases,
                    chap_idx, v_idx, verse_text,
                    num_chapters, num_v_in_chap,
                )
                total_verses += 1

        if book_idx % 10 == 0 or book_idx == len(BOOKS) - 1:
            print(f"  [{book_idx + 1:2d}/66] {book_name:20s} {num_chapters:3d} ch  {num_verses:5d} v")

    print(f"\nDone.")
    print(f"  Books written:  {total_books}")
    print(f"  Verses written: {total_verses}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 build/atomize_kjv.py /path/to/kjv.json")
        sys.exit(2)
    main(sys.argv[1])
