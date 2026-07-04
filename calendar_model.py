"""Calendar model: defines target hours per calendar day, including holidays.

Separate from entries.csv. This file has one row per day of the year
(workday, weekend, or holiday); entries.csv only has the sessions the
user actually logs. Balance calculations use both.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

from holidays_de_nrw import nrw_holidays

DAILY_TARGET_HOURS = 3.4


class CalendarModel:
    """CRUD and generation for the calendar CSV."""

    FIELDS = ["date", "weekday", "target_hours", "note"]

    def __init__(self, filepath: Path):
        """Initialize the model.

        Args:
            filepath: Path to the calendar CSV file.
        """
        self.filepath = filepath
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, dict]:
        """Load calendar rows into a dict keyed by date.

        Returns:
            Dict mapping date -> {weekday, target_hours, note}. Empty if the
            file does not exist yet.
        """
        if not self.filepath.exists():
            return {}
        with open(self.filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return {
                row["date"]: {
                    "weekday": row["weekday"],
                    "target_hours": float(row["target_hours"]),
                    "note": row["note"],
                }
                for row in reader
            }

    def save(self, records: dict[str, dict]) -> None:
        """Write calendar rows to the CSV file, sorted by date."""
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()
            for day, record in sorted(records.items()):
                writer.writerow({"date": day, **record})

    def ensure_years(self, years: list[int]) -> dict[str, dict]:
        """Generate default rows for any missing dates in the given years.

        Existing rows (e.g. manually edited holidays) are kept as-is.

        Args:
            years: Years to generate default calendar rows for.

        Returns:
            The full, updated calendar dict.
        """
        records = self.load()
        changed = False

        for year in years:
            holidays = nrw_holidays(year)
            current = date(year, 1, 1)
            end = date(year, 12, 31)
            while current <= end:
                key = current.isoformat()
                if key not in records:
                    is_holiday = key in holidays
                    is_weekend = current.weekday() >= 5
                    target = 0.0 if (is_weekend or is_holiday) else DAILY_TARGET_HOURS
                    records[key] = {
                        "weekday": current.strftime("%A"),
                        "target_hours": target,
                        "note": holidays.get(key, ""),
                    }
                    changed = True
                current += timedelta(days=1)

        if changed:
            self.save(records)
        return records