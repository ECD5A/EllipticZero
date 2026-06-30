from __future__ import annotations

from pathlib import Path

from scripts.release_gate import (
    PROJECT_ROOT,
    _check_markdown_links,
    _check_source_headers,
    _static_release_checks,
)


def test_repository_static_release_checks_are_clean() -> None:
    assert _static_release_checks(PROJECT_ROOT) == []


def test_markdown_link_check_reports_missing_local_target(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        (
            "[Missing](docs/missing.md)\n"
            "![Missing image](docs/missing.png)\n"
            '<img src="docs/missing-html.png" alt="Missing HTML image">\n'
            "[External](https://example.com)\n"
        ),
        encoding="utf-8",
    )

    failures = _check_markdown_links(tmp_path)

    assert failures == [
        "broken Markdown link in README.md: docs/missing.md",
        "broken Markdown link in README.md: docs/missing.png",
        "broken Markdown link in README.md: docs/missing-html.png",
    ]


def test_source_header_check_reports_unmarked_production_file(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("print('missing header')\n", encoding="utf-8")

    failures = _check_source_headers(tmp_path)

    assert len(failures) == 1
    assert "app" in failures[0]
    assert "main.py" in failures[0]
    assert "SPDX-License-Identifier" in failures[0]
