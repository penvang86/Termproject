"""
TermProject.py - Spaced Repetition Flashcards (command-line)

Create decks of flashcards, review the cards that are due today, and let a
simplified SM-2 style scheduler decide when each card should come back.
Decks are stored as JSON files in the decks/ folder, and session results are
stored in history.json so progress can be shown as stats and a chart.

Run:        python TermProject.py
Time travel (for testing the scheduler):
            python TermProject.py --date 2026-11-01
"""

import argparse
import csv
import json
import os
import random
from datetime import date, timedelta

DECK_DIR = "decks"
HISTORY_FILE = "history.json"

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_EASE = 3.0
MASTERED_INTERVAL = 21  # a card with an interval of 21+ days counts as "mastered"


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class Card:
    """One flashcard plus its scheduling data."""

    def __init__(self, front, back, interval=0, ease=DEFAULT_EASE,
                 due=None, reps=0, lapses=0):
        self.front = front
        self.back = back
        self.interval = interval      # days until the next review
        self.ease = ease              # growth factor for the interval
        self.due = due or date.today()
        self.reps = reps              # current streak of correct answers
        self.lapses = lapses          # total number of misses

    def is_due(self, today):
        """Return True if the card should be reviewed on or before `today`."""
        return self.due <= today

    def review(self, correct, today):
        """Update the schedule after an answer (simplified SM-2)."""
        if correct:
            self.reps += 1
            if self.reps == 1:
                self.interval = 1
            elif self.reps == 2:
                self.interval = 3
            else:
                self.interval = max(1, round(self.interval * self.ease))
            self.ease = min(MAX_EASE, self.ease + 0.05)
        else:
            self.lapses += 1
            self.reps = 0
            self.interval = 1
            self.ease = max(MIN_EASE, self.ease - 0.2)
        self.due = today + timedelta(days=self.interval)

    def is_mastered(self):
        return self.interval >= MASTERED_INTERVAL

    def to_dict(self):
        return {
            "front": self.front,
            "back": self.back,
            "interval": self.interval,
            "ease": self.ease,
            "due": self.due.isoformat(),
            "reps": self.reps,
            "lapses": self.lapses,
        }

    @classmethod
    def from_dict(cls, data):
        """Build a Card from a dict. Raises KeyError/ValueError if malformed."""
        return cls(
            front=data["front"],
            back=data["back"],
            interval=int(data["interval"]),
            ease=float(data["ease"]),
            due=date.fromisoformat(data["due"]),
            reps=int(data["reps"]),
            lapses=int(data["lapses"]),
        )


class Deck:
    """A named collection of cards."""

    def __init__(self, name, cards=None):
        self.name = name
        self.cards = cards or []

    def add_card(self, front, back, today=None):
        """Add a card. Returns False if a card with the same front exists."""
        if any(c.front.lower() == front.lower() for c in self.cards):
            return False
        self.cards.append(Card(front, back, due=today or date.today()))
        return True

    def get_due_cards(self, today):
        return [c for c in self.cards if c.is_due(today)]

    def to_dict(self):
        return {"name": self.name, "cards": [c.to_dict() for c in self.cards]}

    @classmethod
    def from_dict(cls, data):
        cards = [Card.from_dict(c) for c in data["cards"]]
        return cls(data["name"], cards)


class StudySession:
    """Tracks the results of one review session."""

    def __init__(self, deck_name, today):
        self.deck_name = deck_name
        self.today = today
        self.reviewed = 0
        self.correct = 0

    def record(self, was_correct):
        self.reviewed += 1
        if was_correct:
            self.correct += 1

    def accuracy(self):
        if self.reviewed == 0:
            return 0.0
        return 100.0 * self.correct / self.reviewed

    def summary(self):
        return (f"Reviewed {self.reviewed} card(s), {self.correct} correct "
                f"({self.accuracy():.0f}%).")

    def to_dict(self):
        return {
            "deck": self.deck_name,
            "date": self.today.isoformat(),
            "reviewed": self.reviewed,
            "correct": self.correct,
        }


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------

def clean_deck_name(name):
    """Turn user input into a safe file-friendly deck name ('' if unusable)."""
    name = name.strip().replace(" ", "_")
    return "".join(ch for ch in name if ch.isalnum() or ch in "-_")


def deck_path(name):
    return os.path.join(DECK_DIR, f"{name}.json")


def list_decks():
    """Return the names of all saved decks, sorted."""
    try:
        files = os.listdir(DECK_DIR)
    except FileNotFoundError:
        return []
    return sorted(f[:-5] for f in files if f.endswith(".json"))


def load_deck(path):
    """Load a deck from JSON. Returns None (with a message) on any problem."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Deck.from_dict(data)
    except FileNotFoundError:
        print(f"  Could not find '{path}'.")
    except json.JSONDecodeError:
        print(f"  '{path}' is not valid JSON (the file may be corrupted).")
    except (KeyError, ValueError, TypeError):
        print(f"  '{path}' is missing data or has bad values.")
    except OSError as err:
        print(f"  Could not read '{path}': {err}")
    return None


def save_deck(deck, path):
    """Save a deck to JSON safely (write to a temp file, then swap it in)."""
    temp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(deck.to_dict(), f, indent=2)
        os.replace(temp_path, path)
        return True
    except OSError as err:
        print(f"  Could not save deck: {err}")
        return False


def load_history():
    """Return the list of past session records ([] if none or unreadable)."""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError):
        print("  Warning: history file could not be read; starting fresh.")
        return []


def save_session(session):
    """Append a finished session to the history file."""
    history = load_history()
    history.append(session.to_dict())
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except OSError as err:
        print(f"  Could not save history: {err}")


def import_cards_from_csv(deck, csv_path, today):
    """Import 'front,back' rows from a CSV file. Returns (added, skipped)."""
    added = skipped = 0
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if len(row) < 2 or not row[0].strip() or not row[1].strip():
                    skipped += 1
                    continue
                front, back = row[0].strip(), row[1].strip()
                if front.lower() in ("front", "question") and added == 0 and skipped == 0:
                    continue  # header row
                if deck.add_card(front, back, today):
                    added += 1
                else:
                    skipped += 1
    except FileNotFoundError:
        print(f"  File '{csv_path}' was not found.")
    except UnicodeDecodeError:
        print("  That file isn't UTF-8 text; save it as CSV (UTF-8) and retry.")
    except (OSError, csv.Error) as err:
        print(f"  Could not read the CSV file: {err}")
    return added, skipped


# ---------------------------------------------------------------------------
# User interaction
# ---------------------------------------------------------------------------

def get_menu_choice(prompt, valid_choices):
    """Keep asking until the user types one of `valid_choices`."""
    valid = [str(c).lower() for c in valid_choices]
    while True:
        choice = input(prompt).strip().lower()
        if choice in valid:
            return choice
        print(f"  Invalid choice. Please enter one of: {', '.join(valid)}")


def select_deck():
    """Let the user pick or create a deck. Returns (deck, path) or None."""
    os.makedirs(DECK_DIR, exist_ok=True)
    while True:
        names = list_decks()
        print("\n=== Choose a deck ===")
        for i, name in enumerate(names, 1):
            print(f"  {i}. {name}")
        print("  N. New deck")
        print("  Q. Quit")
        valid = [str(i) for i in range(1, len(names) + 1)] + ["n", "q"]
        choice = get_menu_choice("> ", valid)

        if choice == "q":
            return None
        if choice == "n":
            name = clean_deck_name(input("New deck name: "))
            if not name:
                print("  Please use letters, numbers, dashes, or underscores.")
                continue
            path = deck_path(name)
            if os.path.exists(path):
                print("  A deck with that name already exists.")
                continue
            deck = Deck(name)
            if save_deck(deck, path):
                print(f"  Created deck '{name}'.")
                return deck, path
            continue

        path = deck_path(names[int(choice) - 1])
        deck = load_deck(path)
        if deck is not None:
            return deck, path


def add_cards_interactive(deck, today):
    """Prompt for cards until the user enters a blank question."""
    print("\nAdd cards (leave the question blank to finish).")
    added = 0
    while True:
        front = input("  Question: ").strip()
        if not front:
            break
        back = input("  Answer:   ").strip()
        if not back:
            print("  Answer cannot be empty; card skipped.")
            continue
        if deck.add_card(front, back, today):
            added += 1
        else:
            print("  That question is already in the deck; skipped.")
    print(f"  Added {added} card(s).")
    return added


def run_review_session(deck, today):
    """Quiz the user on all due cards. Returns a StudySession (or None)."""
    due = deck.get_due_cards(today)
    if not due:
        print("\nNo cards are due today. Come back tomorrow!")
        return None

    random.shuffle(due)
    session = StudySession(deck.name, today)
    print(f"\n{len(due)} card(s) due. Type q at the grading prompt to stop early.")

    for number, card in enumerate(due, 1):
        print(f"\nCard {number}/{len(due)}")
        print(f"  Q: {card.front}")
        try:
            input("  (press Enter to reveal the answer)")
            print(f"  A: {card.back}")
            answer = get_menu_choice("  Did you get it right? (y/n/q): ",
                                     ["y", "n", "q"])
        except (KeyboardInterrupt, EOFError):
            print("\n  Session interrupted.")
            break
        if answer == "q":
            break
        was_correct = answer == "y"
        card.review(was_correct, today)
        session.record(was_correct)
        days = card.interval
        print(f"  Next review in {days} day{'s' if days != 1 else ''}.")

    print("\n" + session.summary())
    return session


def show_stats(deck, today):
    """Print deck statistics and per-deck accuracy history."""
    total = len(deck.cards)
    print(f"\n=== Stats for '{deck.name}' ===")
    if total == 0:
        print("  This deck has no cards yet.")
        return

    due = len(deck.get_due_cards(today))
    mastered = sum(1 for c in deck.cards if c.is_mastered())
    new = sum(1 for c in deck.cards if c.reps == 0 and c.lapses == 0)
    print(f"  Total cards:    {total}")
    print(f"  Due today:      {due}")
    print(f"  New (unseen):   {new}")
    print(f"  Mastered:       {mastered} ({100 * mastered // total}%)")

    hardest = sorted((c for c in deck.cards if c.lapses > 0),
                     key=lambda c: c.lapses, reverse=True)[:3]
    if hardest:
        print("  Trickiest cards:")
        for c in hardest:
            print(f"    - {c.front}  (missed {c.lapses}x)")

    records = [r for r in load_history() if r.get("deck") == deck.name]
    reviewed = sum(r.get("reviewed", 0) for r in records)
    correct = sum(r.get("correct", 0) for r in records)
    if reviewed:
        print(f"  Lifetime accuracy: {100 * correct / reviewed:.0f}% "
              f"over {len(records)} session(s)")


def plot_progress(deck_name):
    """Show accuracy per session as a chart (falls back to text)."""
    records = [r for r in load_history()
               if r.get("deck") == deck_name and r.get("reviewed", 0) > 0]
    if not records:
        print("\n  No completed sessions yet - review some cards first.")
        return

    labels = [r["date"] for r in records]
    scores = [100 * r["correct"] / r["reviewed"] for r in records]

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n  matplotlib is not installed; showing a text summary instead:")
        for label, score in zip(labels, scores):
            print(f"    {label}: {score:.0f}% {'#' * int(score // 5)}")
        return

    plt.figure(figsize=(8, 4))
    plt.plot(range(1, len(scores) + 1), scores, marker="o")
    plt.xticks(range(1, len(scores) + 1), labels, rotation=45, ha="right")
    plt.ylim(0, 105)
    plt.ylabel("Accuracy (%)")
    plt.xlabel("Session date")
    plt.title(f"Progress - {deck_name}")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_today(date_text):
    """Return a date from --date text, or today's date if none was given."""
    if not date_text:
        return date.today()
    try:
        return date.fromisoformat(date_text)
    except ValueError:
        print(f"Invalid date '{date_text}'. Use YYYY-MM-DD. Using today instead.")
        return date.today()


def main():
    parser = argparse.ArgumentParser(description="Spaced repetition flashcards")
    parser.add_argument("--date", help="pretend today is this date (YYYY-MM-DD)")
    args = parser.parse_args()
    today = parse_today(args.date)

    print("=" * 40)
    print("  SPACED REPETITION FLASHCARDS")
    print(f"  Today: {today.isoformat()}")
    print("=" * 40)

    try:
        selection = select_deck()
        while selection is not None:
            deck, path = selection
            print(f"\n--- Deck: {deck.name} ({len(deck.cards)} cards, "
                  f"{len(deck.get_due_cards(today))} due) ---")
            print("  1. Review due cards")
            print("  2. Add cards")
            print("  3. Import cards from CSV")
            print("  4. Show stats")
            print("  5. Progress chart")
            print("  6. Switch deck")
            print("  0. Quit")
            choice = get_menu_choice("> ", ["1", "2", "3", "4", "5", "6", "0"])

            if choice == "1":
                session = run_review_session(deck, today)
                if session is not None:
                    save_deck(deck, path)
                    if session.reviewed > 0:
                        save_session(session)
            elif choice == "2":
                if add_cards_interactive(deck, today):
                    save_deck(deck, path)
            elif choice == "3":
                csv_path = input("  Path to CSV file: ").strip()
                added, skipped = import_cards_from_csv(deck, csv_path, today)
                print(f"  Imported {added} card(s); skipped {skipped}.")
                if added:
                    save_deck(deck, path)
            elif choice == "4":
                show_stats(deck, today)
            elif choice == "5":
                plot_progress(deck.name)
            elif choice == "6":
                selection = select_deck()
            else:
                break
    except (KeyboardInterrupt, EOFError):
        print()

    print("Goodbye - keep studying!")


if __name__ == "__main__":
    main()
