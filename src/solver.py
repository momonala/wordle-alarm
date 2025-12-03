import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import sleep

import pandas as pd
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Get path relative to project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent
WORDLE_WORDS = pd.read_csv(PROJECT_ROOT / "wordle-answers.csv")


class GameMode(Enum):
    """Enum for Wordle game modes."""

    PLAY = "Play"
    CONTINUE = "Continue"


class GuessNumber(Enum):
    """Enum for Wordle guess numbers."""

    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4
    FIFTH = 5
    SIXTH = 6


@dataclass
class Tile:
    pos: int
    letter: str
    state: str


@dataclass
class WordleState:
    """Represents the state of a Wordle game."""

    guesses: dict[GuessNumber, list[Tile] | None] = field(
        default_factory=lambda: {num: None for num in GuessNumber}
    )

    def get_guess(self, guess_num: GuessNumber) -> list[Tile] | None:
        """Get the tiles for a specific guess number."""
        return self.guesses[guess_num]

    def set_guess(self, guess_num: GuessNumber, tiles: list[Tile] | None) -> None:
        """Set the tiles for a specific guess number."""
        self.guesses[guess_num] = tiles

    @property
    def solved(self) -> bool:
        """Check if the game is solved (any guess has all correct tiles)."""
        return any(
            guess is not None and all(tile.state == "correct" for tile in guess)
            for guess in self.guesses.values()
        )

    @property
    def unsolved(self) -> bool:
        """Check if the game is unsolved (no guess has all correct tiles)."""
        return not self.solved

    @property
    def num_guesses(self) -> int:
        """Get the number of guesses made."""
        return len([g for g in self.guesses.values() if g is not None])

    @property
    def max_guesses_reached(self) -> bool:
        """Check if maximum guesses (6) have been reached."""
        return self.num_guesses >= 6


def guess_word(page, word: str):
    for char in word:
        page.keyboard.type(char, delay=100)
    page.keyboard.press("Enter")
    sleep(2)


def parse_wordle_tiles(html: str, wordle_state: WordleState) -> WordleState:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("div", {"class": "Row-module_row__pwpBq"})

    for idx, row in enumerate(rows):
        tiles = row.find_all("div", {"data-testid": "tile"})
        guess = []
        for i, tile in enumerate(tiles):
            letter = tile.text.lower()
            state = tile.get("data-state")
            if state and state != "empty":
                tile = Tile(pos=i + 1, letter=letter, state=state)
                guess.append(tile)
        if guess:
            wordle_state.set_guess(GuessNumber(idx + 1), guess)

    return wordle_state


def filter_possible_words(wordle_state: WordleState) -> list[str]:
    """Filter possible words based on all guesses in the WordleState."""
    # Collect all guesses
    guesses = [wordle_state.get_guess(num) for num in GuessNumber]

    # If no guesses have been made, return all words
    if not any(guesses):
        return WORDLE_WORDS

    correct_pos = {}
    present_letters = set()
    absent_letters = set()
    wrong_pos = {}
    guessed_words = set()

    # Process each guess
    for guess in guesses:
        if not guess:
            continue

        # Collect the guessed word
        guessed_word = "".join(tile.letter for tile in guess)
        guessed_words.add(guessed_word)

        for tile in guess:
            letter, pos, state = tile.letter, tile.pos - 1, tile.state
            if state == "correct":
                correct_pos[pos] = letter
            elif state == "present":
                present_letters.add(letter)
                wrong_pos.setdefault(letter, set()).add(pos)
            elif state == "absent":
                absent_letters.add(letter)

    def is_valid(word: str) -> bool:
        # Skip words that have already been guessed
        if word in guessed_words:
            return False

        # Check correct positions
        for pos, letter in correct_pos.items():
            if word[pos] != letter:
                return False

        # Check present letters and their wrong positions
        for letter, bad_positions in wrong_pos.items():
            if letter not in word:
                return False
            if any(word[pos] == letter for pos in bad_positions):
                return False

        # Check that all present letters are in the word
        if not present_letters.issubset(set(word)):
            return False

        # Check absent letters
        for letter in absent_letters:
            if letter in word and letter not in present_letters and letter not in correct_pos.values():
                return False

        return True

    # Filter words and sort by frequency
    valid_words = WORDLE_WORDS[WORDLE_WORDS["word"].apply(is_valid)]
    return valid_words.sort_values("frequency", ascending=False)


def solve_wordle(page, mode: GameMode) -> int:
    # close cookies if present
    has_close_cookie_banner = page.get_by_role("button", name="Reject all").count()
    if has_close_cookie_banner:
        page.get_by_role("button", name="Reject all").click()
        page.get_by_test_id(mode.value).click()
        page.get_by_role("button", name="Close").click()
        page.wait_for_timeout(1000)

    wordle_state = WordleState()

    if mode == GameMode.CONTINUE:
        # Parse existing game state
        wordle_state = parse_wordle_tiles(page.content(), wordle_state)
        logger.info("Parsed existing game state")
        logger.info(wordle_state)
        # Start from the next guess number
        start_guess = next(
            (num for num in GuessNumber if wordle_state.get_guess(num) is None), GuessNumber.FIRST
        )
    else:
        # Start new game with "trace"
        first_guess = "trace"
        guess_word(page, first_guess)
        wordle_state = parse_wordle_tiles(page.content(), wordle_state)
        logger.info(f"First guess: {first_guess}")
        logger.info(wordle_state)
        start_guess = GuessNumber.SECOND

    # Continue guessing until we win or run out of guesses
    for guess_num in range(start_guess.value, 7):
        filtered_words = filter_possible_words(wordle_state)
        logger.info(f"Filtered {len(filtered_words)} words")

        if len(filtered_words) == 0:
            logger.error("No valid words found!")
            raise RuntimeError("No valid words found!")

        next_guess = filtered_words.iloc[0]["word"]
        logger.info(f"Guess {guess_num}: {next_guess}")
        guess_word(page, next_guess)

        wordle_state = parse_wordle_tiles(page.content(), wordle_state)
        logger.info(wordle_state)

        # Check if we won (all tiles in the last guess are correct)
        last_guess = wordle_state.get_guess(GuessNumber(guess_num))
        if last_guess and all(tile.state == "correct" for tile in last_guess):
            logger.info(f"Won in {guess_num} guesses!")
            return guess_num

    raise RuntimeError("Failed to solve Wordle in 6 guesses")


def solve_wordle_for_target(target_word: str, first_guess: str = "trace") -> WordleState:
    """Solve Wordle for a specific target word and return the complete WordleState.

    Args:
        target_word: The 5-letter target word to solve for
        first_guess: The first word to guess (default: "trace")

    Returns:
        WordleState with all guesses and their results

    Raises:
        ValueError: If target_word is not 5 letters
        RuntimeError: If unable to solve in 6 guesses
    """
    if len(target_word) != 5:
        raise ValueError(f"Target word must be 5 letters, got {len(target_word)}")

    target_word = target_word.lower()
    wordle_state = WordleState()

    # Make first guess
    first_tiles = _evaluate_guess(first_guess, target_word)
    wordle_state.set_guess(GuessNumber.FIRST, first_tiles)

    # Continue guessing until we win or run out of guesses
    for guess_num in range(2, 7):
        filtered_words = filter_possible_words(wordle_state)

        if len(filtered_words) == 0:
            logger.warning("No valid words found!")
            return wordle_state

        next_guess = filtered_words.iloc[0]["word"]
        next_tiles = _evaluate_guess(next_guess, target_word)
        wordle_state.set_guess(GuessNumber(guess_num), next_tiles)

        # Check if we won
        if all(tile.state == "correct" for tile in next_tiles):
            logger.debug(f"Solved '{target_word}' in {guess_num} guesses")
            return wordle_state

    logger.warning(f"Failed to solve '{target_word}' in 6 guesses")
    return wordle_state


def _evaluate_guess(guess: str, target: str) -> list[Tile]:
    """Evaluate a guess against a target word and return the tile states.

    Args:
        guess: The 5-letter word being guessed
        target: The 5-letter target word

    Returns:
        List of Tile objects representing the guess result
    """
    tiles = []
    target_letters = list(target)
    guess_letters = list(guess)

    # First pass: mark correct letters
    for i, (guess_letter, target_letter) in enumerate(zip(guess_letters, target_letters)):
        if guess_letter == target_letter:
            tiles.append(Tile(pos=i + 1, letter=guess_letter, state="correct"))
            target_letters[i] = None  # Mark as used
        else:
            tiles.append(Tile(pos=i + 1, letter=guess_letter, state="absent"))

    # Second pass: mark present letters (but not in correct position)
    for i, tile in enumerate(tiles):
        if tile.state == "absent":
            guess_letter = tile.letter
            if guess_letter in target_letters:
                tile.state = "present"
                # Remove the first occurrence from target_letters
                target_letters[target_letters.index(guess_letter)] = None

    return tiles
