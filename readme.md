# Spaced Repetition Flashcards

#### Video Demo: <PASTE YOUR YOUTUBE URL HERE>

#### Description:

Spaced Repetition Flashcards is a command-line study tool written in Python. It lets a user build decks of flashcards, review the cards that are due on a given day, and relies on a simplified version of the SM-2 spaced repetition algorithm to decide when each card should come back. Cards you know well are shown less and less often, while cards you miss return quickly, so study time goes where it is needed most.

## What the program does

When the program starts, the user chooses an existing deck or creates a new one. Each deck is saved as its own JSON file. From the deck menu the user can:

1. **Review due cards.** The program shuffles every card whose due date is today or earlier. For each card it shows the question, waits for the user to press Enter, reveals the answer, and asks the user to grade themselves (`y` for correct, `n` for incorrect, `q` to stop early). The card's schedule is updated immediately and the user is told how many days until it appears again.
2. **Add cards** interactively, one question and answer at a time.
3. **Import cards from a CSV file** with `front,back` columns. Malformed rows and duplicate questions are skipped and counted rather than crashing the program.
4. **Show stats**: total cards, cards due today, unseen cards, mastered cards, the trickiest cards (most misses), and lifetime accuracy for the deck.
5. **Show a progress chart** of accuracy per study session using matplotlib, with a plain-text fallback if matplotlib is not installed.
6. **Switch decks** or quit.

The scheduling rules work like this. A first correct answer sets the interval to 1 day, a second consecutive correct answer sets it to 3 days, and every correct answer after that multiplies the interval by the card's "ease" factor (which starts at 2.5 and grows slightly with each success, up to 3.0). A wrong answer resets the card to a 1-day interval, records a lapse, and lowers the ease factor (never below 1.3). A card with an interval of 21 days or more is counted as "mastered."

## How to run it

```
pip install -r requirements.txt
python TermProject.py
```

To test the scheduler without waiting for real days to pass, the program accepts a `--date` flag that pretends today is a different date:

```
python TermProject.py --date 2026-10-25
```

## Files in this project

- **TermProject.py** is the entire application. It contains three classes (`Card`, `Deck`, and `StudySession`) and the module-level functions `main`, `load_deck`, `save_deck`, `load_history`, `save_session`, `import_cards_from_csv`, `get_menu_choice`, `select_deck`, `add_cards_interactive`, `run_review_session`, `show_stats`, `plot_progress`, and a few small helpers. All functions, including `main`, are defined at module level and not inside any class.
- **requirements.txt** lists the one third-party library, `matplotlib`, which is used only for the progress chart. Everything else comes from the standard library (`json`, `csv`, `argparse`, `datetime`, `random`, `os`).
- **sample_cards.csv** is a small set of Python-themed flashcards that can be imported to try the program quickly.
- **decks/** is created automatically at runtime and holds one JSON file per deck.
- **history.json** is created automatically after the first completed review session and stores the date, deck, number reviewed, and number correct for each session. The stats screen and chart read from it.

## Design decisions and justifications

**Classes for the data, functions for the actions.** `Card` owns its own scheduling logic in a `review()` method, so the rules for intervals and ease live in exactly one place. `Deck` manages a collection of cards and handles duplicate detection and due-card filtering. `StudySession` tracks the results of a single sitting and converts them to a record for the history file. Menu handling, file input and output, and the review loop are plain functions because they act on the objects rather than being part of them.

**JSON for decks, JSON for history.** JSON preserves the structure of each card (numbers stay numbers, dates are stored as ISO strings) and is easy to read and debug by hand. CSV is supported only for importing, since it suits bulk entry from a spreadsheet but cannot cleanly store scheduling data.

**Safe saving.** Decks are written to a temporary file first and then swapped into place with `os.replace`. If something goes wrong mid-write, the original deck is not destroyed.

**Defensive input and error handling.** Every place the program touches the outside world is guarded: missing files, corrupted JSON, missing keys, bad dates, unreadable CSV files, invalid menu choices, and Ctrl+C during a review session. A bad deck file produces a clear message instead of a traceback, and an interrupted session still saves the cards already answered.

**Self-grading.** The user decides whether they were right. Checking typed answers automatically would punish small spelling differences and fail on answers that can be phrased many ways, whereas self-grading is how most real flashcard tools work and keeps the program focused on scheduling.

**Simplified SM-2.** The full SM-2 algorithm asks for a 0-5 quality rating on each answer. A simple correct/incorrect choice is faster in a terminal session and still captures the core idea: intervals grow on success and reset on failure.

**A command-line interface instead of a GUI.** A text interface kept the project's complexity in the scheduling, file handling, and error handling rather than in window layout, and it runs anywhere Python does.

**The `--date` option.** Spaced repetition is hard to demonstrate in real time, so being able to simulate future days made it possible to test the scheduler thoroughly and to show it working in the video.
