#!/usr/bin/env python3
"""Check internal links in the built site resolve to real files.

Run:  python3 site/scripts/check_links.py
Exits non-zero if any internal link is broken.
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

SITE = Path(__file__).resolve().parent.parent
PAGES = ["index.html", "docs.html", "results.html", "install.html", "changelog.html", "roadmap.html"]

# Links that are external or intentionally not checked as files
EXTERNAL_OK = re.compile(r"^(https?:|mailto:|#)")


def main():
    errors = []
    for page in PAGES:
        html = (SITE / page).read_text()
        # href and src
        for m in re.finditer(r'(?:href|src)="([^"]+)"', html):
            url = m.group(1)
            if EXTERNAL_OK.match(url):
                continue
            # strip fragment/query
            path = unquote(urlparse(url).path)
            if not path:
                continue
            target = (SITE / path).resolve()
            if not target.exists():
                errors.append(f"{page}: broken link -> {url}")
    if errors:
        for e in errors:
            print(f"LINK ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"all internal links OK across {len(PAGES)} pages")


if __name__ == "__main__":
    main()
