"""Tests for the version-bump automation (scripts/bump_version.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bump_version.py"
_spec = importlib.util.spec_from_file_location("bump_version", _SCRIPT)
bump = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# Register before exec so @dataclass can resolve the module by __module__.
sys.modules["bump_version"] = bump
_spec.loader.exec_module(bump)


class TestSemVer:
    def test_parse_core(self):
        v = bump.SemVer.parse("1.2.3")
        assert (v.major, v.minor, v.patch, v.pre) == (1, 2, 3, None)

    def test_parse_prerelease(self):
        v = bump.SemVer.parse("1.2.3-rc.1")
        assert v.pre == "rc.1"
        assert str(v) == "1.2.3-rc.1"

    @pytest.mark.parametrize("bad", ["1.2", "v1.2.3", "1.2.3.4", "1.02.3", "x"])
    def test_parse_rejects_invalid(self, bad):
        with pytest.raises(bump.VersionError):
            bump.SemVer.parse(bad)

    def test_bump_patch_minor_major(self):
        v = bump.SemVer.parse("1.2.3")
        assert str(v.bump("patch")) == "1.2.4"
        assert str(v.bump("minor")) == "1.3.0"
        assert str(v.bump("major")) == "2.0.0"

    def test_bump_clears_prerelease(self):
        v = bump.SemVer.parse("1.2.3-rc.1")
        assert str(v.bump("patch")) == "1.2.4"

    def test_with_pre(self):
        v = bump.SemVer.parse("1.2.3").bump("minor").with_pre("beta.2")
        assert str(v) == "1.3.0-beta.2"


class TestFileOps:
    def _init(self, tmp_path: Path, version: str) -> Path:
        p = tmp_path / "__init__.py"
        p.write_text(f'"""pkg."""\n\n__version__ = "{version}"\n', encoding="utf-8")
        return p

    def test_read_and_write_roundtrip(self, tmp_path, monkeypatch):
        init = self._init(tmp_path, "1.0.0")
        monkeypatch.setattr(bump, "INIT_PATH", init)
        assert str(bump.read_current_version()) == "1.0.0"
        bump.write_version(bump.SemVer.parse("1.0.1"))
        assert '__version__ = "1.0.1"' in init.read_text(encoding="utf-8")
        assert str(bump.read_current_version()) == "1.0.1"

    def test_changelog_promotion_inserts_fresh_unreleased(self, tmp_path, monkeypatch):
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n\n## [Unreleased]\n\n### Fixed\n- thing\n\n## [1.0.0] - 2024-01-01\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(bump, "CHANGELOG_PATH", changelog)
        assert bump.update_changelog(bump.SemVer.parse("1.1.0"), "2024-06-01") is True
        text = changelog.read_text(encoding="utf-8")
        assert "## [Unreleased]" in text
        assert "## [1.1.0] - 2024-06-01" in text
        # the promoted entries stay under the new version, above the old release
        assert text.index("## [1.1.0]") < text.index("- thing")
        assert text.index("- thing") < text.index("## [1.0.0]")

    def test_changelog_missing_is_soft_skip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bump, "CHANGELOG_PATH", tmp_path / "nope.md")
        assert bump.update_changelog(bump.SemVer.parse("1.1.0"), "2024-06-01") is False


class TestMain:
    def test_dry_run_changes_nothing(self, tmp_path, monkeypatch, capsys):
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.0.0"\n', encoding="utf-8")
        monkeypatch.setattr(bump, "INIT_PATH", init)
        rc = bump.main(["patch", "--dry-run"])
        assert rc == 0
        assert "1.0.0 -> 1.0.1" in capsys.readouterr().out
        assert '__version__ = "1.0.0"' in init.read_text(encoding="utf-8")

    def test_explicit_set_writes_version(self, tmp_path, monkeypatch):
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.0.0"\n', encoding="utf-8")
        monkeypatch.setattr(bump, "INIT_PATH", init)
        monkeypatch.setattr(bump, "CHANGELOG_PATH", tmp_path / "absent.md")
        assert bump.main(["--set", "2.5.0"]) == 0
        assert '__version__ = "2.5.0"' in init.read_text(encoding="utf-8")

    def test_noop_bump_is_error(self, tmp_path, monkeypatch):
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.0.0"\n', encoding="utf-8")
        monkeypatch.setattr(bump, "INIT_PATH", init)
        assert bump.main(["--set", "1.0.0"]) == 3
