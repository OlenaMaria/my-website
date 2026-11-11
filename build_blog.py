"""Generate local blog previews from the Markdown files in posts/."""

from datetime import date
from html import escape
from pathlib import Path

import markdown
import yaml


# Find the website folder.
ROOT = Path(__file__).resolve().parent
POSTS = ROOT / "posts"
PREVIEWS = ROOT / "_preview"

CATEGORIES = {
    "science": "Science notes",
    "personal": "Personal notes",
}


def read_post(path):
    """Read the metadata and convert the Markdown."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    if not lines or lines[0].strip() != "---":
        raise ValueError(
            "The file must begin with the metadata's --- line."
        )

    end = next(
        (
            i for i in range(1, len(lines))
            if lines[i].strip() == "---"
        ),
        None,
    )

    if end is None:
        raise ValueError(
            "Add a closing --- line after the metadata."
        )

    post = yaml.safe_load("\n".join(lines[1:end]))

    if not isinstance(post, dict):
        raise ValueError(
            "Add the title, date, category and published fields."
        )

    if not isinstance(post.get("title"), str) or not post["title"].strip():
        raise ValueError(
            "Give the post a title in quotation marks."
        )

    if post.get("category") not in CATEGORIES:
        raise ValueError(
            'Category must be "science" or "personal".'
        )

    if not isinstance(post.get("published"), bool):
        raise ValueError(
            "Use published: false or published: true, without quotes."
        )

    try:
        post["date"] = date.fromisoformat(str(post["date"]))
    except (KeyError, ValueError):
        raise ValueError(
            'Use a date such as "2026-11-11".'
        ) from None

    body = "\n".join(lines[end + 1:])

    post["html"] = markdown.markdown(
        body,
        extensions=["fenced_code", "tables"],
    )

    return post


def render_post(post):
    """Place the article inside a complete HTML page."""
    title = escape(post["title"])
    section = CATEGORIES[post["category"]]
    display_date = post["date"].strftime("%d %B %Y")
    preview_label = "Preview" if post["published"] else "Draft preview"

    return f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Olena-Maria Balta</title>

  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Caveat:wght@600&amp;family=DM+Sans:wght@400;500;700&amp;display=swap">
  <link rel="stylesheet" href="../../styles.css">
</head>

<body>
  <main>
    <nav class="site-nav" aria-label="Blog navigation">
      <a href="../../index.html#blog">&larr; Back to my website</a>
    </nav>

    <article class="blog-post">
      <p>{section} &middot; {preview_label}</p>

      <h1>{title}</h1>

      <p>
        <time datetime="{post["date"].isoformat()}">
          {display_date}
        </time>
      </p>

      {post["html"]}
    </article>
  </main>
</body>
</html>
'''


def main():
    # Check every source post before writing any preview pages.
    files = sorted(POSTS.glob("*.md"))

    if not files:
        raise SystemExit(
            "Add a Markdown (.md) file to the posts folder first."
        )

    pages = []

    for path in files:
        try:
            post = read_post(path)
            pages.append((path, post, render_post(post)))
        except (ValueError, TypeError, yaml.YAMLError) as error:
            raise SystemExit(
                f"Check {path.name}: {error}"
            ) from None

    # Write the generated pages into the preview folder.
    for path, post, page in pages:
        folder = PREVIEWS / post["category"]
        folder.mkdir(parents=True, exist_ok=True)

        output = folder / f"{path.stem}.html"
        output.write_text(page, encoding="utf-8")

        print(
            f"Preview created: {output.relative_to(ROOT).as_posix()}"
        )


if __name__ == "__main__":
    main()