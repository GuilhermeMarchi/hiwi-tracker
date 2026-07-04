"""Data model and CSV persistence for work session entries."""

import csv
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class WorkEntry:
    """A single work session.

    Attributes:
        id: Unique identifier.
        date: Session date, format YYYY-MM-DD.
        start: Start time, format HH:MM.
        end: End time, format HH:MM.
        notes: Optional free-text note.
    """
    id: int
    date: str
    start: str
    end: str
    notes: str = ""


class TimeTrackerModel:
    """CRUD operations for work entries backed by a CSV file."""

    FIELDS = ["id", "date", "start", "end", "notes"]

    def __init__(self, filepath: Path):
        """Initialize the model and ensure the CSV file exists.

        Args:
            filepath: Path to the CSV file.
        """
        self.filepath = filepath
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self.filepath.exists():
            self._write_all([])

    def _write_all(self, entries: list[WorkEntry]) -> None:
        """Overwrite the CSV file with the given entries."""
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()
            for entry in entries:
                writer.writerow(asdict(entry))

    def load_all(self) -> list[WorkEntry]:
        """Load all entries from the CSV file, sorted by date and start time.

        Returns:
            List of WorkEntry, sorted chronologically.
        """
        with open(self.filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            entries = [WorkEntry(int(row["id"]), row["date"], row["start"],
                                  row["end"], row["notes"]) for row in reader]
        entries.sort(key=lambda e: (e.date, e.start))
        return entries

    def _next_id(self, entries: list[WorkEntry]) -> int:
        """Compute the next available id."""
        return max((e.id for e in entries), default=0) + 1

    def add_entry(self, date: str, start: str, end: str, notes: str = "") -> WorkEntry:
        """Add a new session and persist it.

        Returns:
            The created WorkEntry.
        """
        entries = self.load_all()
        entry = WorkEntry(self._next_id(entries), date, start, end, notes)
        entries.append(entry)
        self._write_all(entries)
        return entry

    def update_entry(self, entry_id: int, date: str, start: str, end: str, notes: str = "") -> None:
        """Update an existing session by id."""
        entries = self.load_all()
        for i, e in enumerate(entries):
            if e.id == entry_id:
                entries[i] = WorkEntry(entry_id, date, start, end, notes)
                break
        self._write_all(entries)

    def delete_entry(self, entry_id: int) -> None:
        """Delete a session by id."""
        entries = [e for e in self.load_all() if e.id != entry_id]
        self._write_all(entries)
