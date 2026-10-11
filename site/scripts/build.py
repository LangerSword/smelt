#!/usr/bin/env python3
"""Build the smelt static site.

Assembles pages from templates + generated partials.
Run:  python3 site/scripts/build.py
"""
import sys
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
SCRIPTS = SITE / "scripts"
PARTIALS = SITE / "_partials"


def run(script):
    r = subprocess.run([sys.executable, str(SCRIPTS / script)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"WARN: {script} exited {r.returncode}: {r.stderr[:200]}", file=sys.stderr)


def main():
    PARTIALS.mkdir(exist_ok=True)
    run("gen_results.py")
    run("gen_cli_ref.py")

    # Inject results + CLI into pages
    results = (PARTIALS / "results.html").read_text()
    cli = (PARTIALS / "cli-ref.html").read_text()

    index = SITE / "index.html"
    html = index.read_text().replace("<!-- GENERATED_RESULTS -->", results)
    index.write_text(html)
    print("index.html updated with results")

    respage = SITE / "results.html"
    rhtml = respage.read_text()
    rhtml = rhtml.replace("<!-- GENERATED_RESULTS -->", results)
    rhtml = rhtml.replace("<!-- GENERATED_CLI -->", cli)
    respage.write_text(rhtml)
    print("results.html updated with results + cli")

    # Build sitemap
    pages = ["index.html", "docs.html", "results.html", "install.html", "changelog.html", "roadmap.html"]
    urls = "\n".join(f"  <url><loc>https://LangerSword.github.io/smelt/{p}</loc></url>" for p in pages)
    sitemap = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n'
    (SITE / "sitemap.xml").write_text(sitemap)
    print("sitemap.xml written")

    (SITE / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://LangerSword.github.io/smelt/sitemap.xml\n"
    )
    print("robots.txt written")


if __name__ == "__main__":
    main()
