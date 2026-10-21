import os

from src.main import use_ram_for_browser_temp_files


def test_clears_leftover_profiles_and_points_tmpdir_at_ram(tmp_path, monkeypatch):
    monkeypatch.delenv("TMPDIR", raising=False)
    (tmp_path / "playwright_chromiumdev_profile-abc").mkdir()
    (tmp_path / "playwright-artifacts-xyz").mkdir()
    (tmp_path / "unrelated").mkdir()

    use_ram_for_browser_temp_files(tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["unrelated"]
    assert os.environ["TMPDIR"] == str(tmp_path)


def test_leaves_tmpdir_alone_without_a_ram_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", "/original")

    use_ram_for_browser_temp_files(tmp_path / "missing")

    assert os.environ["TMPDIR"] == "/original"
