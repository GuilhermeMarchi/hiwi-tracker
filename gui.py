"""GUI for the HiWi time tracker: Month > Week > Day > Session tree + edit form."""

import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime

from models import TimeTrackerModel, WorkEntry
from calendar_model import CalendarModel
from calculations import (
    session_hours, build_day_records, cumulative_balance,
    group_days_by_month, group_days_by_week, period_totals,
)


CONTRACT_START_MONTH = "2026-07"
CONTRACT_MONTHS = 12


class TimeTrackerApp(ctk.CTk):
    """Main application window."""

    def __init__(self, model: TimeTrackerModel, calendar_model: CalendarModel):
        """Initialize the window, models, and widgets.

        Args:
            model: TimeTrackerModel instance backing the sessions.
            calendar_model: CalendarModel instance backing per-day targets.
        """
        super().__init__()
        self.model = model
        self.calendar_model = calendar_model
        self.selected_entry_id: int | None = None

        self.title("HiWi Time Tracker")
        self.geometry("980x640")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._init_tree()
        self._init_form()
        self.refresh()

    def _init_tree(self) -> None:
        """Build the nested Treeview (month > week > day > session)."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        columns = ("start", "end", "hours", "notes")
        self.tree = ttk.Treeview(frame, columns=columns, show="tree headings")

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#242424",
            fieldbackground="#242424",
            foreground="#f2f2f2",
            borderwidth=0,
            rowheight=28,
        )
        style.map("Treeview", background=[("selected", "#1f538d")])
        style.configure(
            "Treeview.Heading",
            background="#2b2b2b",
            foreground="#ffffff",
            borderwidth=1,
            relief="flat",
        )

        self.tree.tag_configure("month", background="#1a1a1a", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("week", background="#212121", foreground="#d0d0d0")
        self.tree.tag_configure("day", background="#2a2a2a")
        self.tree.tag_configure("session", background="#333333")

        self.tree.heading("#0", text="Period / Balance")
        self.tree.heading("start", text="Start")
        self.tree.heading("end", text="End")
        self.tree.heading("hours", text="Hours")
        self.tree.heading("notes", text="Notes")
        self.tree.column("#0", width=380)
        self.tree.column("start", width=70, anchor="center")
        self.tree.column("end", width=70, anchor="center")
        self.tree.column("hours", width=70, anchor="center")
        self.tree.column("notes", width=160)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _init_form(self) -> None:
        """Build the entry form and action buttons."""
        panel = ctk.CTkFrame(self)
        panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(panel, text="Session", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(10, 15))

        self.entry_date = self._labeled_entry(panel, "Date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        self.entry_start = self._labeled_entry(panel, "Start (HH:MM)")
        self.entry_end = self._labeled_entry(panel, "End (HH:MM)")
        self.entry_notes = self._labeled_entry(panel, "Notes")

        ctk.CTkButton(panel, text="Add", command=self.add_entry).pack(pady=(20, 5), padx=20, fill="x")
        ctk.CTkButton(panel, text="Update selected", command=self.update_entry).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(panel, text="Delete selected", fg_color="darkred", hover_color="red",
                      command=self.delete_entry).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(panel, text="Clear form", fg_color="gray30", hover_color="gray20",
                      command=self.clear_form).pack(pady=(5, 20), padx=20, fill="x")

        self.summary_label = ctk.CTkLabel(panel, text="", justify="left")
        self.summary_label.pack(pady=10, padx=10)

    def _labeled_entry(self, parent, label: str, default: str = "") -> ctk.CTkEntry:
        """Create a labeled CTkEntry and return the entry widget."""
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", padx=20)
        entry = ctk.CTkEntry(parent)
        entry.insert(0, default)
        entry.pack(fill="x", padx=20, pady=(0, 10))
        return entry

    @staticmethod
    def _period_label(worked: float, target: float, balance: float) -> str:
        """Format a 'worked / target / balance' suffix for tree row labels."""
        return f"worked {worked:.2f}h | target {target:.2f}h | balance {balance:+.2f}h"

    @staticmethod
    def _month_range(start_month: str, count: int) -> set[str]:
        """Return `count` consecutive year-month keys starting at `start_month`."""
        year, month = (int(p) for p in start_month.split("-"))
        months = set()
        for i in range(count):
            m = (month - 1 + i) % 12 + 1
            y = year + (month - 1 + i) // 12
            months.add(f"{y}-{m:02d}")
        return months

    def _relevant_months(self, entries: list[WorkEntry]) -> set[str]:
        """Months to display: the contract window, plus any month with entries."""
        months = self._month_range(CONTRACT_START_MONTH, CONTRACT_MONTHS)
        months.update(e.date[:7] for e in entries)
        return months

    def refresh(self) -> None:
        """Reload data from the models and redraw the tree and summary."""
        self.tree.delete(*self.tree.get_children())
        entries = self.model.load_all()
        months = self._relevant_months(entries)
        years = sorted({int(m[:4]) for m in months})
        calendar = self.calendar_model.ensure_years(years)

        day_records = cumulative_balance(build_day_records(entries, calendar, months))
        grouped_months = group_days_by_month(day_records)

        for month in sorted(grouped_months.keys()):
            month_days = grouped_months[month]
            totals = period_totals(month_days)
            month_id = self.tree.insert("", "end", open=False,
                                         text=f"{month}  |  {self._period_label(**totals)}",
                                         tags=("month",))
            self._insert_weeks(month_id, month_days)

        self._update_summary(day_records)

    def _insert_weeks(self, month_id: str, month_days: list[dict]) -> None:
        """Insert week nodes (and their days/sessions) under a month node."""
        weeks = group_days_by_week(month_days)
        for week in sorted(weeks.keys()):
            week_days = weeks[week]
            totals = period_totals(week_days)
            week_id = self.tree.insert(month_id, "end", open=False,
                                        text=f"{week}  |  {self._period_label(**totals)}",
                                        tags=("week",))
            self._insert_days(week_id, week_days)

    def _insert_days(self, week_id: str, week_days: list[dict]) -> None:
        """Insert day nodes (and their sessions) under a week node."""
        for day in week_days:
            label = f"{day['date']}  |  {self._period_label(day['worked'], day['target'], day['balance'])}"
            day_id = self.tree.insert(week_id, "end", open=True, text=label, tags=("day",))
            for s in day["sessions"]:
                self.tree.insert(day_id, "end", iid=str(s.id), text="",
                                  values=(s.start, s.end, f"{session_hours(s.start, s.end):.2f}", s.notes),
                                  tags=("session",))

    def _update_summary(self, day_records: list[dict]) -> None:
        """Update the overall summary label (total hours, current balance)."""
        totals = period_totals(day_records)
        current_balance = day_records[-1]["cumulative"] if day_records else 0.0
        text = (f"Total worked: {totals['worked']:.2f}h\n"
                f"Total target: {totals['target']:.2f}h\n"
                f"Current balance: {current_balance:+.2f}h")
        self.summary_label.configure(text=text)

    def _on_select(self, _event) -> None:
        """Populate the form when a session row is selected."""
        selection = self.tree.selection()
        if not selection or not selection[0].isdigit():
            return
        entry_id = int(selection[0])
        entry = next((e for e in self.model.load_all() if e.id == entry_id), None)
        if entry is None:
            return
        self.selected_entry_id = entry.id
        self._set_form(entry)

    def _set_form(self, entry: WorkEntry) -> None:
        """Fill the form fields with the given entry's values."""
        for widget, value in ((self.entry_date, entry.date), (self.entry_start, entry.start),
                               (self.entry_end, entry.end), (self.entry_notes, entry.notes)):
            widget.delete(0, "end")
            widget.insert(0, value)

    def clear_form(self) -> None:
        """Reset the form and clear the current selection."""
        self.selected_entry_id = None
        self.tree.selection_remove(self.tree.selection())
        self._set_form(WorkEntry(0, datetime.now().strftime("%Y-%m-%d"), "", "", ""))

    def _read_form(self) -> tuple[str, str, str, str] | None:
        """Validate and read form fields.

        Returns:
            Tuple (date, start, end, notes) or None if validation fails.
        """
        date, start, end, notes = (self.entry_date.get().strip(), self.entry_start.get().strip(),
                                    self.entry_end.get().strip(), self.entry_notes.get().strip())
        try:
            datetime.strptime(date, "%Y-%m-%d")
            datetime.strptime(start, "%H:%M")
            datetime.strptime(end, "%H:%M")
        except ValueError:
            messagebox.showerror("Invalid input", "Check date (YYYY-MM-DD) and time (HH:MM) formats.")
            return None
        if session_hours(start, end) <= 0:
            messagebox.showerror("Invalid input", "End time must be after start time.")
            return None
        return date, start, end, notes

    def add_entry(self) -> None:
        """Add a new session from the form."""
        data = self._read_form()
        if data is None:
            return
        self.model.add_entry(*data)
        self.clear_form()
        self.refresh()

    def update_entry(self) -> None:
        """Update the selected session with the form's current values."""
        if self.selected_entry_id is None:
            messagebox.showwarning("No selection", "Select a session to update.")
            return
        data = self._read_form()
        if data is None:
            return
        self.model.update_entry(self.selected_entry_id, *data)
        self.clear_form()
        self.refresh()

    def delete_entry(self) -> None:
        """Delete the selected session."""
        if self.selected_entry_id is None:
            messagebox.showwarning("No selection", "Select a session to delete.")
            return
        if messagebox.askyesno("Confirm", "Delete selected session?"):
            self.model.delete_entry(self.selected_entry_id)
            self.clear_form()
            self.refresh()