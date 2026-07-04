"""GUI for the HiWi time tracker: Custom pure-CTK nested list, edit form, and monthly chart."""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import TimeTrackerModel, WorkEntry
from calendar_model import CalendarModel
from calculations import (
    session_hours, build_day_records, cumulative_balance,
    group_days_by_month, group_days_by_week, period_totals
)

CONTRACT_START_MONTH = "2026-07"
CONTRACT_MONTHS = 12

class TimeTrackerApp(ctk.CTk):
    """Main application window using pure CustomTkinter and Matplotlib."""

    def __init__(self, model: TimeTrackerModel, calendar_model: CalendarModel):
        super().__init__()
        self.model = model
        self.calendar_model = calendar_model
        self.selected_entry_id: int | None = None

        self.title("HiWi Time Tracker")
        self.geometry("1100x720")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._init_list()
        self._init_right_panel()
        self.refresh()

    def _init_list(self) -> None:
        """Build the scrollable container for the session list."""
        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _init_right_panel(self) -> None:
        """Build the right panel with Tabs for Form and Chart."""
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        tab_form = self.tabs.add("Entry Form")
        tab_chart = self.tabs.add("Monthly Chart")

        # --- Tab 1: Form ---
        ctk.CTkLabel(tab_form, text="Session Details", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(10, 15))

        self.entry_date = self._labeled_entry(tab_form, "Date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        self.entry_start = self._labeled_entry(tab_form, "Start (HH:MM)")
        self.entry_end = self._labeled_entry(tab_form, "End (HH:MM)")
        self.entry_notes = self._labeled_entry(tab_form, "Notes")

        ctk.CTkButton(tab_form, text="Add", command=self.add_entry).pack(pady=(20, 5), padx=20, fill="x")
        ctk.CTkButton(tab_form, text="Update selected", command=self.update_entry).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(tab_form, text="Delete selected", fg_color="darkred", hover_color="red", command=self.delete_entry).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(tab_form, text="Clear form", fg_color="gray30", hover_color="gray20", command=self.clear_form).pack(pady=(5, 20), padx=20, fill="x")

        self.summary_label = ctk.CTkLabel(tab_form, text="", justify="left")
        self.summary_label.pack(pady=10, padx=10)

        # --- Tab 2: Chart ---
        self.chart_frame = ctk.CTkFrame(tab_chart, fg_color="transparent")
        self.chart_frame.pack(fill="both", expand=True)

    def _labeled_entry(self, parent, label: str, default: str = "") -> ctk.CTkEntry:
        """Create and return a labeled CTkEntry."""
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", padx=20)
        entry = ctk.CTkEntry(parent)
        entry.insert(0, default)
        entry.pack(fill="x", padx=20, pady=(0, 10))
        return entry

    @staticmethod
    def _period_label(worked: float, target: float, balance: float) -> str:
        return f"W: {worked:.2f}h | T: {target:.2f}h | B: {balance:+.2f}h"

    def _month_range(self, start_month: str, count: int) -> set[str]:
        year, month = (int(p) for p in start_month.split("-"))
        months = set()
        for i in range(count):
            m = (month - 1 + i) % 12 + 1
            y = year + (month - 1 + i) // 12
            months.add(f"{y}-{m:02d}")
        return months

    def _relevant_months(self, entries: list[WorkEntry]) -> set[str]:
        months = self._month_range(CONTRACT_START_MONTH, CONTRACT_MONTHS)
        months.update(e.date[:7] for e in entries)
        return months

    def _create_accordion(self, parent, text: str, default_open: bool = False) -> ctk.CTkFrame:
        """Creates a collapsible section and returns its content frame."""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", pady=2)
        
        content = ctk.CTkFrame(container, fg_color="transparent")
        
        def toggle():
            if content.winfo_ismapped():
                content.pack_forget()
            else:
                content.pack(fill="x", padx=(20, 0), pady=2)
        
        btn = ctk.CTkButton(container, text=text, anchor="w", command=toggle, 
                            fg_color="#2b2b2b", hover_color="#3a3a3a", corner_radius=4)
        btn.pack(fill="x")
        
        if default_open:
            content.pack(fill="x", padx=(20, 0), pady=2)
            
        return content

    def refresh(self) -> None:
        """Clear and rebuild the list frame and update UI elements."""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        entries = self.model.load_all()
        months = self._relevant_months(entries)
        years = sorted({int(m[:4]) for m in months})
        calendar = self.calendar_model.ensure_years(years)

        day_records = cumulative_balance(build_day_records(entries, calendar, months))
        grouped_months = group_days_by_month(day_records)

        for month in sorted(grouped_months.keys()):
            month_days = grouped_months[month]
            totals = period_totals(month_days)
            
            label = f"📅 {month}   [{self._period_label(**totals)}]"
            month_content = self._create_accordion(self.list_frame, label, default_open=False)
            self._insert_weeks(month_content, month_days)

        self._update_summary(day_records, entries)
        self._update_chart(grouped_months)

    def _insert_weeks(self, parent, month_days: list[dict]) -> None:
        weeks = group_days_by_week(month_days)
        for week in sorted(weeks.keys()):
            week_days = weeks[week]
            totals = period_totals(week_days)
            
            label = f"🗓️ {week}   [{self._period_label(**totals)}]"
            week_content = self._create_accordion(parent, label, default_open=False)
            self._insert_days(week_content, week_days)

    def _insert_days(self, parent, week_days: list[dict]) -> None:
        for day in week_days:
            label = f"🔹 {day['date']} ({day['weekday'][:3]})   [{self._period_label(day['worked'], day['target'], day['balance'])}]"
            has_sessions = len(day["sessions"]) > 0
            day_content = self._create_accordion(parent, label, default_open=has_sessions)
            
            for s in day["sessions"]:
                s_label = f"  🕒 {s.start} - {s.end}  |  {session_hours(s.start, s.end):.2f}h  |  {s.notes}"
                btn = ctk.CTkButton(day_content, text=s_label, anchor="w", 
                                    fg_color="#1e1e1e", hover_color="#1f538d", corner_radius=4,
                                    command=lambda session_id=s.id: self._on_select(session_id))
                btn.pack(fill="x", pady=1)

    def _update_summary(self, day_records: list[dict], entries: list[WorkEntry]) -> None:
        """Calculate and display balance only between the first and last logged dates."""
        if not entries:
            self.summary_label.configure(text="Effective Balance: 0.00h")
            return

        first_date = min(entry.date for entry in entries)
        last_date = max(entry.date for entry in entries)

        active_balance = sum(
            record["balance"]
            for record in day_records
            if first_date <= record["date"] <= last_date
        )

        self.summary_label.configure(text=f"Effective Balance: {active_balance:+.2f}h")

    def _update_chart(self, grouped_months: dict[str, list[dict]]) -> None:
        """Draws a bar chart of worked vs target hours per month."""
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        months = sorted(grouped_months.keys())
        worked = [period_totals(grouped_months[m])["worked"] for m in months]
        target = [period_totals(grouped_months[m])["target"] for m in months]

        # Dark theme colors for Matplotlib
        bg_color = "#242424"
        text_color = "#dce4ee"

        fig, ax = plt.subplots(figsize=(5, 4), facecolor=bg_color)
        ax.set_facecolor(bg_color)

        x = range(len(months))
        width = 0.35

        ax.bar([i - width/2 for i in x], worked, width, label='Worked', color='#1f538d')
        ax.bar([i + width/2 for i in x], target, width, label='Target', color='#a33b3b')

        # Formatting
        ax.set_xticks(x)
        # Display only month numbers for space (e.g. '07' from '2026-07')
        ax.set_xticklabels([m[-2:] for m in months], color=text_color) 
        ax.tick_params(colors=text_color)
        
        for spine in ax.spines.values():
            spine.set_color(text_color)
            spine.set_alpha(0.3)

        ax.legend(facecolor=bg_color, edgecolor=bg_color, labelcolor=text_color)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _on_select(self, entry_id: int) -> None:
        entry = next((e for e in self.model.load_all() if e.id == entry_id), None)
        if entry is None:
            return
        self.selected_entry_id = entry.id
        self.tabs.set("Entry Form")
        self._set_form(entry)

    def _set_form(self, entry: WorkEntry) -> None:
        for widget, value in ((self.entry_date, entry.date), (self.entry_start, entry.start),
                              (self.entry_end, entry.end), (self.entry_notes, entry.notes)):
            widget.delete(0, "end")
            widget.insert(0, value)

    def clear_form(self) -> None:
        self.selected_entry_id = None
        self._set_form(WorkEntry(0, datetime.now().strftime("%Y-%m-%d"), "", "", ""))

    def _read_form(self) -> tuple[str, str, str, str] | None:
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
        data = self._read_form()
        if data is None:
            return
        self.model.add_entry(*data)
        self.clear_form()
        self.refresh()

    def update_entry(self) -> None:
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
        if self.selected_entry_id is None:
            messagebox.showwarning("No selection", "Select a session to delete.")
            return
        if messagebox.askyesno("Confirm", "Delete selected session?"):
            self.model.delete_entry(self.selected_entry_id)
            self.clear_form()
            self.refresh()