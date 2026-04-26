#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
import win32gui
import win32process
import psutil
import json
import listApps002 as listapps  # backend

TIMES_FILE = "times.json"


class MonitorThread(threading.Thread):
    def __init__(self, stop_event, poll_interval=1.0, min_session=1.0):
        """
        Inicjalizacja wątku monitorującego.
        - stop_event: threading.Event do zatrzymania pętli.
        - poll_interval: jak często (s) sprawdzać aktywne okno.
        - min_session: minimalna długość sesji (s), aby ją zaliczyć.
        Ustawia strukturę totals, aktualny proces, czas startu oraz wczytuje
        zapisany czas dla grupy A.
        """
        super().__init__(daemon=True)
        self.stop_event = stop_event
        self.poll_interval = poll_interval
        self.min_session = min_session
        self.totals = {}  # nazwa_procesu -> sekundy
        self.current = None
        self.start_time = time.monotonic()
        # wczytaj zapisany czas grupy A (jeśli istnieje)
        self.group_a_total = float(self.load_times() or 0)


    def get_active_process(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            return proc.name()
        except Exception:
            return None

   
    def run(self):
        """Co poll_interval sprawdza aktywny proces, dolicza czas poprzedniej sesji
         jeśli przekroczyła min_session i aktualizuje totals oraz group_a_total."""
        grupa = 2
        while not self.stop_event.is_set():
            name = self.get_active_process()
            now = time.monotonic()

            if name != self.current:
                elapsed = now - self.start_time
                if self.current:
                    self.totals[self.current] = self.totals.get(self.current, 0) + elapsed
                    if grupa == 0:
                        self.group_a_total += elapsed
                    elif grupa == 1: 
                        if self.group_a_total < elapsed:
                            self.group_a_total = 0
                        else:
                            self.group_a_total -= elapsed
                self.current = name
                self.start_time = now
                grupa = listapps.grupy.get(self.current)
            
            if grupa == 1:
                elapsed = now - self.start_time
                if elapsed >= self.group_a_total:
                    messagebox.showinfo("Koniec czasu", "Twój czas na aplikacje nieproduktywne się skończył.")
                    self.group_a_total = 0
                

            time.sleep(self.poll_interval)

        # przy zatrzymaniu wątku dolicz ostatnią sesję (jeśli wystarczająco długa)
        now = time.monotonic()
        elapsed = now - self.start_time
        if self.current and elapsed >= self.min_session:
            self.totals[self.current] = self.totals.get(self.current, 0) + elapsed
            if grupa == 0:
                self.group_a_total += elapsed
            elif grupa == 1:
                if self.group_a_total < elapsed:
                    self.group_a_total = 0
                else:
                    self.group_a_total -= elapsed


    def save_times(self):
        """Zapisuje czas grupy A do pliku JSON."""
        try:
            data = {"group_a_seconds": int(self.group_a_total)}
            with open(TIMES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass


    def load_times(self):
        """Wczytuje zapisany czas grupy A (jeśli istnieje). Zwraca liczbę sekund lub 0."""
        if not os.path.exists(TIMES_FILE):
            return 0
        try:
            with open(TIMES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("group_a_seconds", 0))
        except Exception:
            return 0


class AppGUI:
    # Tworzy okno, listę aplikacji, przyciski do przypisywania grup,
    # uruchamia wątek monitorujący i obsługuje zamknięcie aplikacji.
    def __init__(self, root):
        """
        Inicjalizacja GUI.
        - root: instancja tk.Tk()
        Ustawia czcionki, style, listę aplikacji, elementy interfejsu,
        uruchamia MonitorThread i harmonogram odświeżania.
        """
        self.root = root
        self.root.title("Przypisywanie aplikacji do grup + monitor")

        # czcionka domyślna
        self.default_font = tkfont.Font(family="Segoe UI", size=12)
        self.root.option_add("*Font", self.default_font)
        style = ttk.Style(self.root)
        style.configure(".", font=("Segoe UI", 12))

        # lista aplikacji z backendu
        self.apps = listapps.get_sorted_exe_list()

        # Listbox
        self.listbox = tk.Listbox(root, height=20, width=40, font=self.default_font)
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
        self.output = tk.Text(root, width=50, height=12, font=self.default_font)
        self.output.grid(row=4, column=1, rowspan=3, padx=10, pady=10)

        # pole z podsumowaniem czasu (aktualizowane okresowo)
        ttk.Label(root, text="Czas (sekundy) spędzony przy procesach:").grid(row=7, column=0, columnspan=2, pady=(5, 0))
        self.totals_box = tk.Text(root, width=80, height=10, font=self.default_font)
        self.totals_box.grid(row=8, column=0, columnspan=2, padx=10, pady=(0, 10))

        # monitor w tle
        self.stop_event = threading.Event()
        self.monitor = MonitorThread(self.stop_event, poll_interval=1.0, min_session=1.0)
        self.monitor.start()

        # odświeżanie GUI
        self.refresh_output()
        # pierwsze natychmiastowe uaktualnienie, potem co 60s (60000 ms)
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
        """Pobiera zaznaczenie i wywołuje backendową funkcję dodającą do grupy."""
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
        """Pobiera zaznaczenie i wywołuje backendową funkcję usuwającą nazwe z grupy."""
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
        """
        Aktualizuje widok z totals i oblicza czas spędzony w grupie A.
        Odświeżanie ustawione na x sekund dla optymalizacji.
        """
        # snapshot totals z wątku monitorującego
        totals = dict(self.monitor.totals) 
        # jeśli aktualnie trwa sesja, pokaż jej czas także (ale nie modyfikujemy totals w wątku)
        if self.monitor.current:
            elapsed = time.monotonic() - self.monitor.start_time
            totals[self.monitor.current] = totals.get(self.monitor.current, 0) + elapsed

        # wyświetl totals
        self.totals_box.delete("1.0", tk.END)
        for proc, secs in sorted(totals.items(), key=lambda x: -x[1]):
            group = listapps.grupy.get(proc, "—")
            self.totals_box.insert(tk.END, f"{proc} -> {int(secs)} s (grupa: {group})\n")

        # zaplanuj kolejne odświeżenie za 60 sekund
        self.root.after(10000, self.update_totals_periodically)


    def on_close(self):
        """Zamyka aplikację: zatrzymuje monitor, zapisuje czas grupy A i kończy program."""
        if messagebox.askyesno("Zamknij", "Czy na pewno chcesz zamknąć aplikację?"):
            # zatrzymaj wątek monitorujący
            self.stop_event.set()
            self.monitor.join(timeout=2.0)

            # przed zapisem dolicz bieżącą sesję jeśli trwa i należy do grupy A
            try:
                if self.monitor.current and listapps.grupy.get(self.monitor.current) == 0:
                    elapsed = time.monotonic() - self.monitor.start_time
                    if elapsed >= self.monitor.min_session:
                        self.monitor.group_a_total += elapsed
                        # również zaktualizuj totals dla kompletności
                        self.monitor.totals[self.monitor.current] = self.monitor.totals.get(self.monitor.current, 0) + elapsed
            except Exception:
                pass

            # zapisz skumulowany czas grupy A
            self.monitor.save_times()

            # opcjonalnie wypisz do konsoli (przydatne do debugu)
            print("Zapisano czas grupy A (produktywne):", int(self.monitor.group_a_total), "s")

            self.root.destroy()


def main():
    # Etykieta: Punkt wejścia aplikacji GUI.
    root = tk.Tk()
    AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
