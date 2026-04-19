# main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
import win32gui
import win32process
import psutil

import listApps002 as listapps  # backend


class MonitorThread(threading.Thread):
    """Wątek monitorujący aktywny proces i zliczający czas spędzony przy aplikacjach."""

    def __init__(self, stop_event, poll_interval=1.0, min_session=1.0):
        super().__init__(daemon=True)
        self.stop_event = stop_event
        self.poll_interval = poll_interval
        self.min_session = min_session
        self.totals = {}  # nazwa_procesu -> sekundy
        self.current = None
        self.start_time = time.monotonic()

    def get_active_process(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            return proc.name()
        except Exception:
            return None

    def run(self):
        self.current = None
        self.start_time = time.monotonic()
        while not self.stop_event.is_set():
            name = self.get_active_process()
            now = time.monotonic()
            if name != self.current:
                elapsed = now - self.start_time
                if self.current and elapsed >= self.min_session:
                    self.totals[self.current] = self.totals.get(self.current, 0) + elapsed
                self.current = name
                self.start_time = now
            time.sleep(self.poll_interval)

        # przy zatrzymaniu wątku dolicz ostatnią sesję (jeśli wystarczająco długa)
        now = time.monotonic()
        elapsed = now - self.start_time
        if self.current and elapsed >= self.min_session:
            self.totals[self.current] = self.totals.get(self.current, 0) + elapsed


class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Przypisywanie aplikacji do grup + monitor")

        # lista aplikacji z backendu
        self.apps = listapps.get_sorted_exe_list()

        # Listbox
        self.listbox = tk.Listbox(root, height=20, width=40, font=tkfont.Font(family="Segoe UI", size=12))
        self.listbox.grid(row=1, column=0, rowspan=6, padx=10, pady=10)
        for app in self.apps:
            self.listbox.insert(tk.END, app)

        # przyciski grup
        ttk.Button(root, text="Dodaj do grupy A (produktywne)",
                   command=lambda: self.add_to_group("A")).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(root, text="Dodaj do grupy B (nieproduktywne)",
                   command=lambda: self.add_to_group("B")).grid(row=1, column=1, padx=10, pady=5)
        ttk.Button(root, text="Usuń z grup", command=self.remove_from_group).grid(row=2, column=1, padx=10, pady=5)

        # przycisk: dodaj folder do skanowania
        ttk.Button(root, text="Dodaj folder do skanowania", command=self.add_scan_folder_dialog).grid(row=0, column=0, padx=10, pady=5)

        # pole tekstowe z wynikami grup
        self.output = tk.Text(root, width=50, height=12)
        self.output.grid(row=4, column=1, rowspan=3, padx=10, pady=10)

        # pole z podsumowaniem czasu (aktualizowane okresowo)
        ttk.Label(root, text="Czas (sekundy) spędzony przy procesach:").grid(row=7, column=0, columnspan=2, pady=(5,0))
        self.totals_box = tk.Text(root, width=80, height=10)
        self.totals_box.grid(row=8, column=0, columnspan=2, padx=10, pady=(0,10))

        # monitor w tle
        self.stop_event = threading.Event()
        self.monitor = MonitorThread(self.stop_event, poll_interval=1.0, min_session=1.0)
        self.monitor.start()

        # odświeżanie GUI
        self.refresh_output()
        self.update_totals_periodically()

        # przechwycenie zamknięcia okna
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_scan_folder_dialog(self):
        """Otwiera dialog wyboru folderu, dodaje ścieżkę do backendu i odświeża listę aplikacji."""
        folder = filedialog.askdirectory(title="Wybierz folder do skanowania")
        if not folder:
            return
        added = listapps.add_scan_path(folder)
        if not added:
            messagebox.showinfo("Informacja", "Ścieżka nie została dodana (może już istnieje lub nie jest katalogiem).")
            return
        # odśwież listę aplikacji w GUI
        self.apps = listapps.get_sorted_exe_list()
        self.listbox.delete(0, tk.END)
        for app in self.apps:
            self.listbox.insert(tk.END, app)
        self.refresh_output()
        messagebox.showinfo("Sukces", f"Dodano folder do skanowania:\n{folder}")

    def add_to_group(self, group_letter):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Brak wyboru", "Najpierw wybierz aplikację z listy.")
            return
        idx = selection[0]
        key = self.apps[idx]
        group = 0 if group_letter == "A" else 1
        listapps.add_to_group(key, group)
        self.refresh_output()

    def remove_from_group(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Brak wyboru", "Najpierw wybierz aplikację z listy.")
            return
        idx = selection[0]
        key = self.apps[idx]
        listapps.remove_from_group(key)
        self.refresh_output()

    def refresh_output(self):
        """Odświeża wyświetlanie słownika grup."""
        self.output.delete("1.0", tk.END)
        for k, v in listapps.grupy.items():
            self.output.insert(tk.END, f"{k} -> {v}\n")

    def update_totals_periodically(self):
        """Aktualizuje widok z totals co sekundę (nie blokuje GUI)."""
        totals = dict(self.monitor.totals)
        if self.monitor.current:
            elapsed = time.monotonic() - self.monitor.start_time
            totals[self.monitor.current] = totals.get(self.monitor.current, 0) + elapsed

        self.totals_box.delete("1.0", tk.END)
        for proc, secs in sorted(totals.items(), key=lambda x: -x[1]):
            group = listapps.grupy.get(proc, "—")
            self.totals_box.insert(tk.END, f"{proc} -> {int(secs)} s (grupa: {group})\n")

        self.root.after(1000, self.update_totals_periodically)

    def on_close(self):
        """Zamyka aplikację: zatrzymuje monitor, wypisuje totals i grupy, kończy program."""
        if messagebox.askyesno("Zamknij", "Czy na pewno chcesz zamknąć aplikację?"):
            self.stop_event.set()
            self.monitor.join(timeout=2.0)

            print("Suma czasu (sekundy) per proces:")
            for proc, secs in sorted(self.monitor.totals.items(), key=lambda x: -x[1]):
                print(f"{proc} -> {int(secs)} s")

            print("\nZawartość słownika grup:")
            for k, v in listapps.grupy.items():
                print(f"{k} -> {v}")

            self.root.destroy()


def main():
    root = tk.Tk()
    AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
