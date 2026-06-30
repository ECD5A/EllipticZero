# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GATE_ROOT = (PROJECT_ROOT / ".test_runs" / "release-gate").resolve()
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
IGNORED_TREE_PARTS = {".git", ".venv", ".test_runs", "artifacts", "build", "dist"}
SOURCE_HEADER_MARKERS = (
    "EllipticZero: https://github.com/ECD5A/EllipticZero",
    "Copyright (c) 2026 ECD5A",
    "SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2",
    "License terms: see LICENSE in the project root.",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local EllipticZero production release gate."
    )
    parser.add_argument(
        "--skip-package",
        action="store_true",
        help="Skip distribution build and installed-wheel smoke checks.",
    )
    args = parser.parse_args()

    failures = _static_release_checks(PROJECT_ROOT)
    if failures:
        print("[FAIL] static release checks")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[PASS] static release checks")

    commands = [
        ("dependency sanity", [sys.executable, "-m", "pip", "check"]),
        (
            "bytecode compilation",
            [sys.executable, "-m", "compileall", "-q", "app", "tests", "scripts"],
        ),
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("test suite", [sys.executable, "-m", "pytest", "-q"]),
        (
            "benchmark scorecard",
            [sys.executable, "-m", "app.main", "--benchmark-scorecard"],
        ),
    ]
    if _git_available():
        commands.insert(0, ("git whitespace", ["git", "diff", "--check"]))

    for label, command in commands:
        if _run_stage(label, command, cwd=PROJECT_ROOT) != 0:
            return 1

    if not args.skip_package and _run_package_gate() != 0:
        return 1

    print("\nPRODUCTION RELEASE GATE: PASS")
    return 0


def _run_package_gate() -> int:
    _reset_gate_root()
    dist_dir = GATE_ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    if _run_stage(
        "build distributions",
        [sys.executable, "-m", "build", "--outdir", str(dist_dir)],
        cwd=PROJECT_ROOT,
    ):
        return 1

    distributions = sorted(
        path for path in dist_dir.iterdir() if path.suffix in {".whl", ".gz"}
    )
    if not distributions:
        print("[FAIL] distribution build produced no wheel or sdist")
        return 1
    if _run_stage(
        "distribution metadata",
        [sys.executable, "-m", "twine", "check", *map(str, distributions)],
        cwd=PROJECT_ROOT,
    ):
        return 1

    wheel_paths = [path for path in distributions if path.suffix == ".whl"]
    if len(wheel_paths) != 1:
        print(f"[FAIL] expected one wheel, found {len(wheel_paths)}")
        return 1

    smoke_env = GATE_ROOT / "wheel-env"
    outside_root = GATE_ROOT / "outside"
    outside_root.mkdir(parents=True, exist_ok=True)
    if _run_stage(
        "create wheel smoke environment",
        [sys.executable, "-m", "venv", "--system-site-packages", str(smoke_env)],
        cwd=PROJECT_ROOT,
    ):
        return 1
    smoke_python = _venv_python(smoke_env)
    if _run_stage(
        "install built wheel",
        [
            str(smoke_python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--force-reinstall",
            str(wheel_paths[0]),
        ],
        cwd=outside_root,
        clean_python_path=True,
    ):
        return 1
    for label, arguments in (
        ("installed-wheel evaluation smoke", ["--evaluation-summary"]),
        ("installed-wheel resource smoke", ["--list-golden-cases"]),
    ):
        if _run_stage(
            label,
            [str(smoke_python), "-m", "app.main", *arguments],
            cwd=outside_root,
            clean_python_path=True,
        ):
            return 1
    return 0


def _run_stage(
    label: str,
    command: list[str],
    *,
    cwd: Path,
    clean_python_path: bool = False,
) -> int:
    print(f"\n== {label} ==")
    environment = os.environ.copy()
    if clean_python_path:
        environment.pop("PYTHONPATH", None)
        environment["PYTHONNOUSERSITE"] = "1"
    try:
        completed = subprocess.run(command, cwd=cwd, env=environment, check=False)
    except OSError as exc:
        print(f"[FAIL] {label}: {exc}")
        return 1
    if completed.returncode:
        print(f"[FAIL] {label} (exit={completed.returncode})")
        return completed.returncode
    print(f"[PASS] {label}")
    return 0


def _static_release_checks(root: Path) -> list[str]:
    failures = [
        *_check_version_consistency(root),
        *_check_markdown_links(root),
        *_check_source_headers(root),
    ]
    for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
        if not workflow.read_text(encoding="utf-8").strip():
            failures.append(f"empty workflow: {workflow.relative_to(root)}")
    return failures


def _check_source_headers(root: Path) -> list[str]:
    source_paths = [
        *sorted((root / "app").rglob("*.py")),
        *sorted((root / "scripts").glob("*.py")),
        root / "scripts" / "setup_local_lab.bat",
        root / "scripts" / "setup_local_lab.ps1",
        root / "scripts" / "setup_local_lab.sh",
    ]
    failures: list[str] = []
    for source_path in source_paths:
        if not source_path.is_file():
            continue
        header = "\n".join(source_path.read_text(encoding="utf-8").splitlines()[:8])
        missing = [marker for marker in SOURCE_HEADER_MARKERS if marker not in header]
        if missing:
            failures.append(
                f"missing source license header in {source_path.relative_to(root)}: "
                + ", ".join(missing)
            )
    return failures


def _check_version_consistency(root: Path) -> list[str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = str(pyproject["project"]["version"])
    init_text = (root / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    failures: list[str] = []
    if match is None or match.group(1) != package_version:
        failures.append(
            f"version mismatch: pyproject={package_version}; app={match.group(1) if match else 'missing'}"
        )
    for relative in (Path("CHANGELOG.md"), Path("docs/ru/CHANGELOG.ru.md")):
        text = (root / relative).read_text(encoding="utf-8")
        if f"`{package_version}`" not in text[:500]:
            failures.append(f"package version {package_version} missing near top of {relative}")
    return failures


def _check_markdown_links(root: Path) -> list[str]:
    failures: list[str] = []
    markdown_paths: list[Path] = []
    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = [
            name
            for name in directory_names
            if name not in IGNORED_TREE_PARTS and not name.startswith(".venv-")
        ]
        markdown_paths.extend(
            Path(current_root) / name for name in file_names if name.endswith(".md")
        )

    for markdown_path in sorted(markdown_paths):
        text = markdown_path.read_text(encoding="utf-8")
        raw_targets = [
            *MARKDOWN_LINK_RE.findall(text),
            *HTML_LINK_RE.findall(text),
        ]
        for raw_target in raw_targets:
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(
                ("#", "data:", "http://", "https://", "mailto:", "tel:")
            ):
                continue
            path_text = unquote(target.split("#", 1)[0].split("?", 1)[0]).strip()
            if not path_text:
                continue
            candidate = (
                root / path_text.lstrip("/")
                if path_text.startswith("/")
                else markdown_path.parent / path_text
            )
            if not candidate.resolve().exists():
                failures.append(
                    f"broken Markdown link in {markdown_path.relative_to(root)}: {raw_target}"
                )
    return failures


def _reset_gate_root() -> None:
    expected_parent = (PROJECT_ROOT / ".test_runs").resolve()
    if GATE_ROOT.parent != expected_parent or GATE_ROOT.name != "release-gate":
        raise RuntimeError(f"Refusing to reset unexpected gate directory: {GATE_ROOT}")
    if GATE_ROOT.exists():
        shutil.rmtree(GATE_ROOT)
    GATE_ROOT.mkdir(parents=True, exist_ok=True)


def _venv_python(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _git_available() -> bool:
    return shutil.which("git") is not None and (PROJECT_ROOT / ".git").exists()


if __name__ == "__main__":
    raise SystemExit(main())
