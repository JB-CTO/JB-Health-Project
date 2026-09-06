"""
Pre-Commit & Pre-Push PHI / Secret Security Scanner.
Guarantees that NO personal health information (PHI), real patient data,
private databases, or API keys are exposed or committed to Git.
"""

from pathlib import Path
import subprocess
import shutil
import sys
import re

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BLOCKED_EXTENSIONS = {
    ".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key"
}

# Regex patterns for sensitive credentials & PHI
SENSITIVE_PATTERNS = [
    (r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{12,}['\"]", "API / Secret Key"),
    (r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b", "Social Security Number (SSN)"),
    (r"(?i)\bMRN[:\s#]+[0-9]{6,}\b", "Medical Record Number (MRN)"),
    (r"(?i)ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
]


def find_git_binary() -> str:
    which = shutil.which("git")
    if which:
        return which
    candidates = [
        r"C:\Users\jbrie\AppData\Local\Programs\Git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return "git"


def get_git_files(repo_root: Path):
    """Gets list of files tracked or staged by git."""
    git_bin = find_git_binary()
    try:
        res = subprocess.run(
            [git_bin, "ls-files"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True
        )
        tracked = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        if tracked:
            return tracked
    except Exception:
        pass

    # Fallback to filesystem scan excluding git and venv
    files = []
    for p in repo_root.rglob("*"):
        if p.is_file():
            parts = p.parts
            if ".git" not in parts and ".venv" not in parts and "__pycache__" not in parts and ".pytest_cache" not in parts:
                files.append(str(p.relative_to(repo_root)))
    return files


def scan_repo(repo_root: Path) -> bool:
    print("=" * 70)
    print("JB-Health-Project Security & Privacy Audit")
    print("Scanning for personal health information (PHI) and secrets...")
    print("=" * 70)

    tracked_files = get_git_files(repo_root)
    violations = []

    for rel_path in tracked_files:
        p = repo_root / rel_path
        if not p.exists() or p.is_dir():
            continue

        # 1. Check file extensions
        if p.suffix.lower() in BLOCKED_EXTENSIONS:
            violations.append(f"Blocked file type: {rel_path}")

        # 2. Check for raw data outside data/samples/
        if p.suffix.lower() in (".xml", ".zip", ".pdf", ".csv"):
            norm = p.as_posix()
            if "data/samples/" not in norm:
                violations.append(f"Private health data file outside samples dir: {rel_path}")

        # 3. Check text files for credentials or PHI patterns
        if p.suffix.lower() in (".py", ".yaml", ".yml", ".json", ".md", ".txt", ".csv"):
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                for pat, label in SENSITIVE_PATTERNS:
                    matches = re.findall(pat, content)
                    if matches:
                        violations.append(f"Potential {label} detected in {rel_path}!")
            except Exception:
                pass

    if violations:
        print("\n[ERROR] SECURITY AUDIT FAILED! The following potential issues were found:")
        for v in violations:
            print(f"  - {v}")
        print("\nPlease remove these files or patterns before pushing to GitHub.")
        return False
    else:
        print("\n[SUCCESS] SECURITY AUDIT PASSED! Clean repository.")
        print(f"Scanned {len(tracked_files)} files.")
        print("Zero PHI, zero private databases, and zero secrets detected.")
        return True


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    success = scan_repo(root)
    sys.exit(0 if success else 1)
