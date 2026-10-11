#!/usr/bin/env python3
"""Build the smelt static site.

Assembles pages from templates + generated partials, idempotently.

Run:  python3 site/scripts/build.py

Partials are injected between marker comments so re-running replaces the
previous injection instead of appending. Markers are re-emitted by the build,
so the pages on disk stay buildable.
"""
import re
import sys
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
SCRIPTS = SITE / "scripts"
PARTIALS = SITE / "_partials"

PAGES = ["index.html", "docs.html", "results.html", "install.html", "changelog.html", "roadmap.html"]


def run(script: str) -> None:
    r = subprocess.run([sys.executable, str(SCRIPTS / script)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"WARN: {script} exited {r.returncode}: {r.stderr[:300]}", file=sys.stderr)


def inject(page: Path, marker: str, content: str) -> bool:
    """Replace <!-- MARKER --> or the previously injected MARKER block.

    Idempotent: the marker is re-emitted around the content, so the next run
    finds and replaces the whole block instead of skipping or duplicating it.
    """
    html = page.read_text()
    block = f"<!-- {marker}:START -->\n{content}\n<!-- {marker}:END -->"

    # Already injected? Swap the whole block.
    start = f"<!-- {marker}:START -->"
    end = f"<!-- {marker}:END -->"
    if start in html and end in html:
        html = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            block,
            html,
            count=1,
            flags=re.S,
        )
        page.write_text(html)
        return True

    # First injection: replace the bare marker.
    marker_html = f"<!-- {marker} -->"
    if marker_html in html:
        html = html.replace(marker_html, block)
        page.write_text(html)
        return True

    return False


def minify_css() -> None:
    """Write assets/css/site.min.css (fonts inlined) and point pages at it.

    Fonts are merged in rather than linked separately: two chained
    render-blocking stylesheets delay first paint, and @font-face rules do not
    need a request of their own. Comment-stripping and whitespace-collapsing
    only — no structural change.
    """
    src = SITE / "assets" / "css" / "site.css"
    fonts = SITE / "assets" / "fonts" / "fonts.css"
    dst = SITE / "assets" / "css" / "site.min.css"

    body = src.read_text()
    banner = ""
    if body.startswith("/*"):
        end = body.find("*/")
        if end != -1:
            banner = body[: end + 2]
            body = body[end + 2 :]

    # Font faces are written relative to assets/fonts/; site.min.css lives in
    # assets/css/, so rewrite the urls to stay correct.
    font_css = fonts.read_text().replace("url(", "url(../fonts/")

    css = f"{body}\n\n/* ---- fonts (inlined) ---- */\n{font_css}"

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,])\s*", r"\1", css)
    css = re.sub(r";\}", "}", css)
    dst.write_text(f"{banner}\n{css.strip()}\n")

    # Point every page at the single minified stylesheet.
    for page_name in PAGES:
        page = SITE / page_name
        html = page.read_text()
        html2 = (
            html.replace('href="assets/css/site.css"', 'href="assets/css/site.min.css"')
            .replace('  <link rel="stylesheet" href="assets/fonts/fonts.css">\n', "")
        )
        if html2 != html:
            page.write_text(html2)

    print(
        f"site.min.css written ({src.stat().st_size + fonts.stat().st_size} -> {dst.stat().st_size} bytes, fonts inlined)"
    )


def main() -> None:
    PARTIALS.mkdir(exist_ok=True)
    run("gen_results.py")
    run("gen_cli_ref.py")
    minify_css()

    results = (PARTIALS / "results.html").read_text()
    cli = (PARTIALS / "cli-ref.html").read_text()
    scripts = (PARTIALS / "scripts.html").read_text()

    for page_name in PAGES:
        page = SITE / page_name
        did = []
        if "GENERATED_RESULTS" in page.read_text():
            if inject(page, "GENERATED_RESULTS", results):
                did.append("results")
        if "GENERATED_CLI" in page.read_text():
            if inject(page, "GENERATED_CLI", cli):
                did.append("cli")
        if inject(page, "SITE_SCRIPTS", scripts):
            did.append("scripts")
        print(f"{page_name}: {', '.join(did) if did else 'nothing to inject'}")

    pages = PAGES
    urls = "\n".join(f"  <url><loc>https://smelt.langersword.in/{p}</loc></url>" for p in pages)
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n"
    )
    (SITE / "sitemap.xml").write_text(sitemap)
    print("sitemap.xml written")

    (SITE / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://smelt.langersword.in/sitemap.xml\n"
    )
    print("robots.txt written")


if __name__ == "__main__":
    main()