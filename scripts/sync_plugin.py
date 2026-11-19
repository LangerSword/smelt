#!/usr/bin/env python3
"""Sync the vendored plugin artifacts from the canonical sources.

The Hermes plugin must work without smelt_rs installed, so it vendors the
stdlib-only handler core BYTE-IDENTICAL, and carries a real COPY of the skill
(the validator rejects symlinks escaping the plugin root). One source of
truth, synced homes:

    src/smelt_rs/agent_api.py  -> plugin/smelt_agent_api.py
    skills/smelt/              -> plugin/skills/smelt/

    python3 scripts/sync_plugin.py           # copy
    python3 scripts/sync_plugin.py --check   # CI: fail if they drifted
"""

import argparse
import filecmp
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "src", "smelt_rs", "agent_api.py")
DST = os.path.join(REPO, "plugin", "smelt_agent_api.py")
SKILL_SRC = os.path.join(REPO, "skills", "smelt")
SKILL_DST = os.path.join(REPO, "plugin", "skills", "smelt")


def _dir_diff(a: str, b: str) -> bool:
    """True if the two trees differ (missing/extra/changed files)."""
    if not os.path.isdir(b):
        return True
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return True
    for sub in cmp.common_dirs:
        if _dir_diff(os.path.join(a, sub), os.path.join(b, sub)):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    drift = []
    if not os.path.exists(DST) or not filecmp.cmp(SRC, DST, shallow=False):
        drift.append("plugin/smelt_agent_api.py differs from src/smelt_rs/agent_api.py")
    if _dir_diff(SKILL_SRC, SKILL_DST):
        drift.append("plugin/skills/smelt differs from skills/smelt")
    if args.check:
        if drift:
            for d in drift:
                print("DRIFT:", d, file=sys.stderr)
            print("run: python3 scripts/sync_plugin.py", file=sys.stderr)
            return 1
        print("plugin core + skill in sync")
        return 0
    shutil.copyfile(SRC, DST)
    if os.path.islink(SKILL_DST):
        os.unlink(SKILL_DST)
    if os.path.isdir(SKILL_DST):
        shutil.rmtree(SKILL_DST)
    shutil.copytree(SKILL_SRC, SKILL_DST)
    print("synced plugin/smelt_agent_api.py + plugin/skills/smelt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
