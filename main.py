"""Entry point for the HiWi time tracker application."""

from pathlib import Path

from models import TimeTrackerModel
from calendar_model import CalendarModel
from gui import TimeTrackerApp

ENTRIES_PATH = Path(__file__).parent / "data" / "entries.csv"
CALENDAR_PATH = Path(__file__).parent / "data" / "calendar.csv"


def main() -> None:
    """Launch the time tracker GUI."""
    model = TimeTrackerModel(ENTRIES_PATH)
    calendar_model = CalendarModel(CALENDAR_PATH)
    app = TimeTrackerApp(model, calendar_model)
    app.mainloop()


if __name__ == "__main__":
    main()