from datetime import date

import pytest

from src import daily_cache


@pytest.fixture(autouse=True)
def cache_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cache, "ANSWER_CACHE_PATH", tmp_path / "daily_answer.json")
    monkeypatch.setattr(daily_cache, "PLAYED_CACHE_PATH", tmp_path / "played_today.json")


def test_played_flag_holds_only_for_its_day():
    daily_cache.mark_played(date(2026, 10, 21))

    assert daily_cache.is_played(date(2026, 10, 21))
    assert not daily_cache.is_played(date(2026, 10, 22))


def test_answer_round_trips_lowercased_for_its_day():
    daily_cache.store_answer("CRANE", date(2026, 10, 21))

    assert daily_cache.load_answer(date(2026, 10, 21)) == "crane"
    assert daily_cache.load_answer(date(2026, 10, 22)) is None
