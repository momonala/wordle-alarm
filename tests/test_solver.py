import pytest

from src.solver import GameMode
from src.solver import GuessNumber
from src.solver import Tile
from src.solver import WordleSolveError
from src.solver import WordleState
from src.solver import filter_possible_words
from src.solver import solve_wordle


def _tiles(word: str, states: str) -> list[Tile]:
    names = {"g": "correct", "y": "present", "x": "absent"}
    return [
        Tile(pos=i + 1, letter=c, state=names[s]) for i, (c, s) in enumerate(zip(word, states, strict=True))
    ]


def test_filter_keeps_only_words_matching_green_yellow_and_gray_feedback():
    state = WordleState()
    state.set_guess(GuessNumber.FIRST, _tiles("trace", "xygxx"))

    words = list(filter_possible_words(state)["word"])

    assert words
    for word in words:
        assert word[2] == "a"
        assert "r" in word and word[1] != "r"
        assert not set(word) & {"t", "c", "e"}


def test_solved_only_when_one_guess_is_all_green():
    state = WordleState()
    state.set_guess(GuessNumber.FIRST, _tiles("crane", "ggggx"))
    assert not state.solved

    state.set_guess(GuessNumber.SECOND, _tiles("craft", "ggggg"))
    assert state.solved


class _NoMatches:
    def count(self) -> int:
        return 0


class _BoardPage:
    def __init__(self, html: str):
        self._html = html

    def get_by_role(self, role, name):
        return _NoMatches()

    def locator(self, selector):
        return _NoMatches()

    def content(self) -> str:
        return self._html


def test_solver_raises_when_feedback_leaves_no_candidate_words():
    tiles = "".join(f'<div data-testid="tile" data-state="present">{c}</div>' for c in "xqjzv")
    page = _BoardPage(f'<div class="Row-module_row__pwpBq">{tiles}</div>')

    with pytest.raises(WordleSolveError, match="No valid words") as exc:
        solve_wordle(page, GameMode.CONTINUE)
    assert exc.value.state.guess_words() == ["xqjzv"]
