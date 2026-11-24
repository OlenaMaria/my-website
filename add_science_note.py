"""Build this website's Science Notes from posts/*.md. Run locally; never deploy."""

import codecs
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from urllib.parse import quote

try:
    import markdown
    import yaml
except ImportError:
    raise SystemExit("Use the website's .venv Python, the same one you use for build_blog.py.")


ROOT = Path(__file__).resolve().parent
WELCOME = "first-science-note"  # My first science note, 11 November 2026
BEGIN, END = "<!-- POSTS:START -->", "<!-- POSTS:END -->"
READY = "<!-- science-notes:archive-v1 -->"
ARTICLE = "<!-- science-notes:article-v1 -->"
LAYOUT_START, LAYOUT_END = "<!-- science-archive:start -->", "<!-- science-archive:end -->"
OLD_CARD_A, OLD_CARD_B = "<!-- first-science-note:start -->", "<!-- first-science-note:end -->"
OLD_ARTICLE = "<!-- article from posts/first-science-note.md -->"
CSS_START, CSS_END = "<!-- science-notes:style -->", "<!-- /science-notes:style -->"
CSS = """<style>
  .pn-block a {color:#71365b;text-decoration-thickness:.08em;text-underline-offset:.17em}
  .pn-block {margin-top:1.6rem;padding-top:1.35rem}
  .pn-kicker {color:#6b5364;font-weight:700;margin:0 0 .25rem}
  .pn-title {margin:0 0 .25rem}
  .pn-date {display:block;color:#695a67;font-size:.95rem;margin:0 0 .95rem}
  .pn-welcome p {max-width:65ch}
  .pn-latest-link {font-size:1.2rem;font-weight:700}
  .pn-entries {list-style:none;padding:0;margin:0}
  .pn-entries li {display:flex;align-items:baseline;justify-content:space-between;
    flex-wrap:wrap;gap:.2rem .8rem;border-bottom:1px solid #eadde5;padding:.7rem 0}
  .pn-entries time {color:#695a67;font-size:.95rem}
</style>"""


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.append(dict(attrs).get("href") or "")


def links(html):
    parser = Links()
    parser.feed(html)
    parser.close()
    return parser.urls


def file_text(path):
    data = path.read_bytes()
    return data.decode("utf-8-sig"), data.startswith(codecs.BOM_UTF8)


def encoded(text, bom):
    return (codecs.BOM_UTF8 if bom else b"") + text.encode("utf-8")


def fix_home(page):
    def correct(match):
        section = match["section"].lower()
        return match["key"] + match["q"] + f"blog/{section}/index.html" + match["q"]
    # Only the two exact old preview destinations on this website are eligible for repair.
    for section in ("science", "personal"):
        pattern = (r"""(?i)(?P<key>\bhref\s*=\s*)(?P<q>["'])(?:\./|/)?_preview/"""
                   + f"(?P<section>{section})/first-{section}-note" + r"""(?:\.html)?/?(?P=q)""")
        page = re.sub(pattern, correct, page)
    if not any(re.fullmatch(r"(?:\./|/)?blog/science(?:/index(?:\.html)?|/)?", url) for url in links(page)):
        raise ValueError('In the homepage index.html, set the Science Notes link to blog/science/index.html and run again.')
    return page


def replace_block(text, begin, end, inside):
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
        raise ValueError("The Science Notes page is missing its expected markers. No update was made.")
    left, rest = text.split(begin)
    _, right = rest.split(end)
    return left + begin + "\n" + inside + "\n" + end + right


def install_layout(page, sections):
    """Upgrade the supplied empty index or the earlier one-card version in place."""
    if page.count(BEGIN) != 1 or page.count(END) != 1 or page.index(BEGIN) >= page.index(END):
        raise ValueError("The Science Notes page is missing its posts markers. No files were changed.")
    left, rest = page.split(BEGIN)
    current, right = rest.split(END)
    if LAYOUT_START in current or LAYOUT_END in current:
        current = replace_block(current, LAYOUT_START, LAYOUT_END, sections)
    else:
        if OLD_CARD_A in current or OLD_CARD_B in current:
            if current.count(OLD_CARD_A) != 1 or current.count(OLD_CARD_B) != 1 or current.index(OLD_CARD_A) >= current.index(OLD_CARD_B):
                raise ValueError("The old science card has incomplete markers. No files were changed.")
            a, b = current.split(OLD_CARD_A)
            _, c = b.split(OLD_CARD_B)
            current = a + c
        current = re.sub(r"""(?i)<p\s+class=["']blog-empty["']\s*>\s*No posts published yet\.\s*</p>""", "", current)
        # Keep any unrelated handwritten content inside or outside the old posts area.
        if not current.strip():
            current = "\n"
        current = "\n" + LAYOUT_START + "\n" + sections + "\n" + LAYOUT_END + current
    return (left + BEGIN + current + END + right).replace("<h1>Science notes</h1>", "<h1>Science Notes</h1>", 1)


def parse_source(path, allow_welcome):
    original = path.read_bytes()
    lines = original.decode("utf-8-sig").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path.name}: missing Markdown metadata at the top.")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError(f"{path.name}: metadata has no closing --- line.")
    fields = yaml.safe_load("".join(lines[1:end]))
    if not isinstance(fields, dict):
        raise ValueError(f"{path.name}: expected title, date, category and published fields.")
    if fields.get("category") != "science":
        return None, None
    if not isinstance(fields.get("published"), bool):
        raise ValueError(f"{path.name}: published must be true or false, without quotes.")
    if not isinstance(fields.get("title"), str) or not fields["title"].strip():
        raise ValueError(f"{path.name}: give this entry a title.")
    try:
        when = date.fromisoformat(str(fields["date"]))
    except (ValueError, KeyError):
        raise ValueError(f"{path.name}: date must look like 2026-11-14.") from None
    if path.stem.casefold() == "index":
        raise ValueError("Rename posts/index.md to a post-specific filename first.")
    include = fields["published"]
    updated = None
    if allow_welcome and path.stem == WELCOME and not include:
        # Change this one flag, preserving the author's body, comments, BOM and line endings.
        front, n = re.subn(r"(?im)^(published[ \t]*:[ \t]*)false(?=[ \t]*(?:\#[^\r\n]*)?\r?$)",
                           r"\g<1>true", "".join(lines[1:end]))
        if n != 1:
            raise ValueError(f"Set published: true yourself in posts/{path.name}, then run again.")
        updated = (lines[0] + front + "".join(lines[end:])).encode("utf-8")
        if original.startswith(codecs.BOM_UTF8):
            updated = codecs.BOM_UTF8 + updated
        include = True
    return {
        "slug": path.stem, "title": fields["title"].strip(), "date": when, "published": include,
        "html": markdown.markdown("".join(lines[end+1:]), extensions=["fenced_code", "tables"]) if include else "",
    }, updated


def time_tag(post, css=""):
    d = post["date"]
    return f'<time class="{css}" datetime="{d.isoformat()}">{d.day} {d:%B %Y}</time>'


def link(post):
    return f'<a href="{quote(post["slug"], safe="-._~")}.html">{escape(post["title"])}</a>'


def article(post):
    title = escape(post["title"])
    return f"""<!DOCTYPE html>
<html lang="en-GB"><head>
{ARTICLE}
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Olena-Maria Balta</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Caveat:wght@600&amp;family=DM+Sans:wght@400;500;700&amp;display=swap">
<link rel="stylesheet" href="../../styles.css">
</head><body><main>
<nav class="site-nav" aria-label="Blog navigation"><a href="index.html">← Science Notes</a>
<a href="../../index.html#blog">Main website</a></nav>
<article class="blog-post"><p>Science notes</p><h1>{title}</h1>
<p>{time_tag(post)}</p>
{post["html"]}
</article></main></body></html>
"""


def archive_page(original, posts):
    published = sorted((p for p in posts if p["published"]), key=lambda p: (p["date"], p["slug"]), reverse=True)
    parts = [READY]
    if published:
        pinned = next((p for p in published if p["slug"] == WELCOME), None)
        if pinned:
            parts.append(f"""<section class="pn-block pn-welcome" id="pn-welcome" aria-labelledby="pn-welcome-title">
<p class="pn-kicker">Start here · My first science note</p>
<h2 class="pn-title" id="pn-welcome-title">{link(pinned)}</h2>
{time_tag(pinned, "pn-date")}
{pinned["html"]}
</section>""")
        latest = published[0]
        parts.append(f"""<section class="pn-block" id="pn-latest" aria-labelledby="pn-latest-title">
<h2 id="pn-latest-title">Latest post</h2><p class="pn-latest-link">{link(latest)}</p>
{time_tag(latest, "pn-date")}
</section>""")
        entries = "\n".join(f'<li>{link(p)} {time_tag(p)}</li>' for p in published)
        parts.append(f"""<section class="pn-block" id="pn-archive" aria-labelledby="pn-archive-title">
<h2 id="pn-archive-title">All blog entries</h2><ol class="pn-entries">{entries}</ol>
</section>""")
    else:
        parts.append('<p class="blog-empty">No science posts published yet.</p>')
    page = install_layout(original, "\n".join(parts))
    if CSS_START in page or CSS_END in page:
        return replace_block(page, CSS_START, CSS_END, CSS)
    if page.count("</head>") != 1:
        raise ValueError("Could not find the head of blog/science/index.html.")
    return page.replace("</head>", f"{CSS_START}\n{CSS}\n{CSS_END}\n</head>", 1)


def write_changed(path, data):
    if path.is_file() and path.read_bytes() == data:
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)
    try:
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def build(root):
    category = root / "blog" / "science"
    index = category / "index.html"
    sources = root / "posts"
    home = root / "index.html"
    if not (sources.is_dir() and index.is_file() and home.is_file() and (root / "styles.css").is_file()):
        raise ValueError("Put the two updater files in my-website, beside styles.css and build_blog.py.")
    raw_index, index_bom = file_text(index)
    original = raw_index.replace("\r\n", "\n")
    homepage, home_bom = file_text(home)
    new_home = encoded(fix_home(homepage), home_bom)
    # Only the very first setup may enable the specific welcome post the author chose.
    initial = READY not in original
    posts, flags = [], {}
    for path in sorted(sources.glob("*.md")):
        try:
            post, ready = parse_source(path, initial)
        except yaml.YAMLError as exc:
            raise ValueError(f"Check the metadata in posts/{path.name}: {exc}") from None
        if post is not None:
            if post["published"] and not post["html"].strip():
                raise ValueError(f"posts/{path.name}: add the text of the note before publishing it.")
            posts.append(post)
        if ready is not None:
            flags[path] = ready
    if initial and not any(p["slug"] == WELCOME for p in posts):
        raise ValueError(f"Couldn't find posts/{WELCOME}.md as a science post. No files were changed.")
    if len({p["slug"].casefold() for p in posts}) != len(posts):
        raise ValueError("Two science posts have filenames that differ only by letter case.")
    # Finish validating and rendering everything before touching the actual site.
    layout = archive_page(original, posts)
    if "\r\n" in raw_index:
        layout = layout.replace("\n", "\r\n")
    new_index = encoded(layout, index_bom)
    active = {p["slug"] for p in posts if p["published"]}
    writes, retire = {}, []
    for p in posts:
        if p["published"]:
            dest = category / (p["slug"] + ".html")
            old = file_text(dest)[0] if dest.is_file() else ""
            legacy = p["slug"] == WELCOME and OLD_ARTICLE in old
            known_preview = (p["slug"] == WELCOME and
                             re.search(r"<p>Science notes\s*(?:&middot;|·)\s*(?:Draft preview|Preview)\s*</p>", old, re.I))
            if not old.strip() or ARTICLE in old or legacy or known_preview:
                writes[dest] = article(p).encode("utf-8")
            # Hand-edited article pages already in the project are left intact.
    for dest in category.glob("*.html"):
        if dest.name != index.name and dest.stem not in active:
            old = file_text(dest)[0]
            if ARTICLE in old or (dest.stem == WELCOME and OLD_ARTICLE in old):
                retire.append(dest)
            else:
                print(f"Existing hand-written page {dest.name} is not listed and was left untouched.")
    for path, data in {**flags, **writes, home: new_home}.items():
        write_changed(path, data)
    write_changed(index, new_index)
    for path in retire:
        # Keep a local copy when a generated article leaves the published list.
        saved = root / "_preview" / "retired-science"
        saved.mkdir(parents=True, exist_ok=True)
        dest = saved / path.name
        serial = 1
        while dest.exists():
            dest = saved / f"{path.stem}-{serial}.html"
            serial += 1
        path.rename(dest)
    print(f"Ready on your computer: {len(active)} published science note(s).")
    print("Open blog/science/index.html to see the welcome note, latest post and all entries.")
    if flags:
        print("Marked the welcome note as published in its Markdown file. Its text was preserved.")
    print("Nothing was sent to GitHub or Cloudflare.")


if __name__ == "__main__":
    try:
        build(ROOT)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"Science Notes: {exc}", file=sys.stderr)
        sys.exit(1)
