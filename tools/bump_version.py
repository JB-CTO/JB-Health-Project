"""
Automated Version Bumper and Changelog Documenter for JB-Health-Project.
Usage:
    python tools/bump_version.py patch "Fixed X, updated Y"
    python tools/bump_version.py minor "Added feature Z"
    python tools/bump_version.py major "Breaking architecture overhaul"
"""

from datetime import datetime
from pathlib import Path
import subprocess
import sys
import re

VERSION_FILE = Path("src/__version__.py")
CHANGELOG_FILE = Path("CHANGELOG.md")


def get_current_version() -> str:
    if not VERSION_FILE.exists():
        return "1.0.0"
    content = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    return m.group(1) if m else "1.0.0"


def bump(current: str, part: str) -> str:
    parts = [int(x) for x in current.split(".")]
    while len(parts) < 3:
        parts.append(0)

    if part == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    elif part == "minor":
        parts[1] += 1
        parts[2] = 0
    elif part == "patch":
        parts[2] += 1
    else:
        raise ValueError(f"Unknown bump part: {part}. Choose 'patch', 'minor', or 'major'.")

    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def update_version_file(new_version: str):
    today_str = datetime.today().strftime("%Y-%m-%d")
    content = f'''"""Version metadata for JB-Health-Project."""

__version__ = "{new_version}"
__version_info__ = ({", ".join(new_version.split("."))})
__release_date__ = "{today_str}"
'''
    VERSION_FILE.write_text(content, encoding="utf-8")
    print(f"[OK] Updated {VERSION_FILE} to v{new_version}")


def update_changelog(new_version: str, message: str, category: str = "Changed"):
    today_str = datetime.today().strftime("%Y-%m-%d")
    new_section = f"""## [{new_version}] - {today_str}

### {category}
- {message}

---

"""
    if CHANGELOG_FILE.exists():
        existing = CHANGELOG_FILE.read_text(encoding="utf-8")
        # Insert right after the first separator or header
        marker = "---\n\n"
        idx = existing.find(marker)
        if idx != -1:
            updated = existing[:idx + len(marker)] + new_section + existing[idx + len(marker):]
        else:
            updated = existing + "\n\n" + new_section
    else:
        updated = f"# 📋 Changelog\n\nAll notable changes documented here.\n\n---\n\n{new_section}"

    CHANGELOG_FILE.write_text(updated, encoding="utf-8")
    print(f"[OK] Documented v{new_version} in {CHANGELOG_FILE}")


def main():
    if len(sys.argv) < 2:
        print("\nJB-Health-Project Version Tracking Tool")
        print("-" * 45)
        current = get_current_version()
        print(f"Current version: v{current}")
        print("\nUsage:")
        print("    python tools/bump_version.py patch \"Description of bug fix or tweak\"")
        print("    python tools/bump_version.py minor \"Description of new feature\"")
        print("    python tools/bump_version.py major \"Breaking overhaul description\"")
        sys.exit(0)

    part = sys.argv[1].lower()
    description = sys.argv[2] if len(sys.argv) > 2 else "Routine maintenance and enhancements"
    category = "Added" if part == "minor" else ("Changed" if part == "patch" else "Overhaul")

    current = get_current_version()
    new_version = bump(current, part)
    print(f"\nBumping version: v{current} -> v{new_version} ({part})")

    update_version_file(new_version)
    update_changelog(new_version, description, category)

    print("\nNext Git steps:")
    print(f"  git add src/__version__.py CHANGELOG.md")
    print(f'  git commit -m "chore(release): v{new_version} - {description}"')
    print(f'  git tag -a v{new_version} -m "Release v{new_version}"')
    print(f"  git push --follow-tags")
    print(f"\nDone! Version {new_version} successfully tracked.")


if __name__ == "__main__":
    main()
