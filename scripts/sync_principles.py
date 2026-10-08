#!/usr/bin/env python3
"""Copy or verify the shared rules included in all independently installable skills."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    ROOT / "claude/study-notes-docs",
    ROOT / "codex/study-notes-pages",
    ROOT / "cursor/study-notes-cursor",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Copy the canonical rules to all three skills")
    mode.add_argument("--check", action="store_true", help="Verify that all three copies match")
    args = parser.parse_args()
    canonical = (ROOT / "shared/principles.md").read_bytes()
    missing = [skill for skill in SKILLS if not (skill / "SKILL.md").is_file()]
    if missing:
        for skill in missing:
            print("缺少 skill：", skill.relative_to(ROOT))
        return 1
    different = []
    for skill in SKILLS:
        target = skill / "references/principles.md"
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != canonical:
                target.write_bytes(canonical)
        if not target.is_file() or target.read_bytes() != canonical:
            different.append(target.relative_to(ROOT))
    if different:
        for target in different:
            print("共同规则不一致：", target)
        return 1
    print("三版共同规则一致。平台行为仍须按 README 的核验清单人工检查。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
