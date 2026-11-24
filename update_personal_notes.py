"""Build this website's Personal Notes from posts/*.md. Run locally; never deploy."""

import argparse
import codecs
from datetime import date
from html import escape
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
WELCOME = "first-personal-note"  # A very organised work in progress, 11 November 2026
BEGIN, END = "<!-- POSTS:START -->", "<!-- POSTS:END -->"
READY = "<!-- personal-notes:archive-v1 -->"
ARTICLE = "<!-- personal-notes:article-v1 -->"
CSS_START, CSS_END = "<!-- personal-notes:style -->", "<!-- /personal-notes:style -->"
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


def replace_block(text, begin, end, inside):
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
        raise ValueError("The Personal Notes page is missing its expected markers. No update was made.")
    left, rest = text.split(begin)
    _, right = rest.split(end)
    return left + begin + "\n" + inside + "\n" + end + right


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
    if fields.get("category") != "personal":
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
<nav class="site-nav" aria-label="Blog navigation"><a href="index.html">← Personal Notes</a>
<a href="../../index.html#blog">Main website</a></nav>
<article class="blog-post"><p>Personal notes</p><h1>{title}</h1>
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
<p class="pn-kicker">Start here · My first personal note</p>
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
        parts.append('<p class="blog-empty">No personal posts published yet.</p>')
    page = replace_block(original, BEGIN, END, "\n".join(parts))
    if CSS_START in page or CSS_END in page:
        return replace_block(page, CSS_START, CSS_END, CSS)
    if page.count("</head>") != 1:
        raise ValueError("Could not find the head of blog/personal/index.html.")
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


def build(root, setup=False):
    category = root / "blog" / "personal"
    index = category / "index.html"
    sources = root / "posts"
    if not (sources.is_dir() and index.is_file() and (root / "styles.css").is_file()):
        raise ValueError("Put the two updater files in my-website, beside styles.css and build_blog.py.")
    original = index.read_text(encoding="utf-8-sig")
    initial = setup and READY not in original
    posts, flags = [], {}
    for path in sorted(sources.glob("*.md")):
        post, ready = parse_source(path, initial)
        if post is not None:
            posts.append(post)
        if ready is not None:
            flags[path] = ready
    if initial and not any(p["slug"] == WELCOME for p in posts):
        raise ValueError(f"Couldn't find posts/{WELCOME}.md as a personal post. No files were changed.")
    if len({p["slug"].casefold() for p in posts}) != len(posts):
        raise ValueError("Two personal posts have filenames that differ only by letter case.")
    # Finish validating and rendering everything before touching the actual site.
    new_index = archive_page(original, posts).encode("utf-8")
    active = {p["slug"] for p in posts if p["published"]}
    writes, retire = {}, []
    for p in posts:
        if p["published"]:
            dest = category / (p["slug"] + ".html")
            if not dest.exists() or ARTICLE in dest.read_text(encoding="utf-8-sig"):
                writes[dest] = article(p).encode("utf-8")
            # Hand-edited article pages already in the project are left intact.
    for dest in category.glob("*.html"):
        if dest.name != index.name and dest.stem not in active:
            if ARTICLE in dest.read_text(encoding="utf-8-sig"):
                retire.append(dest)
            else:
                print(f"Existing hand-written page {dest.name} is not listed and was left untouched.")
    for path, data in {**flags, **writes}.items():
        write_changed(path, data)
    write_changed(index, new_index)
    for path in retire:
        path.unlink()
    print(f"Ready on your computer: {len(active)} personal post(s). Open blog/personal/index.html to check.")
    if flags:
        print("Marked the welcome note as published in its Markdown file. Its text was preserved.")
    print("Nothing was sent to GitHub or Cloudflare.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true",
                        help="On the first build, include the existing 11 November welcome note. Later builds respect every draft flag.")
    args = parser.parse_args()
    try:
        build(ROOT, args.setup)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"Personal Notes: {exc}", file=sys.stderr)
        sys.exit(1)
