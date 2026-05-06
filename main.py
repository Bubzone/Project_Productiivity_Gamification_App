#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ctypes
import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
import win32gui
import win32con
import win32process
import psutil
import json
import listApps002 as listapps  # backend
import pystray
from PIL import Image
import threading
import optionsMinigame
import sites

TIMES_PATH_FILE = "times_path.json"   # plik przechowujący ścieżkę do times.json
DEFAULT_TIMES_FILE = "times.json"     # domyślna lokalizacja
times_file_path = DEFAULT_TIMES_FILE  # aktualnie używana ścieżka

APOCALYPSE_FILE = "apocalypse_state.json"
BROWSER_EXES = {"chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe"}

class MonitorThread(threading.Thread):
    def __init__(self, stop_event, poll_interval=1.0, min_session=1.0, on_limit_reached=None):
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
        self.on_limit_reached = on_limit_reached
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

            # zbuduj klucz aktywności: dla przeglądarki -> "site:<nazwa>", w przeciwnym razie nazwa procesu
            active_key = None
            site=False
            if name:
                if name.lower() in BROWSER_EXES:
                    try:
                        # pobierz tytuł okna i spróbuj wyciągnąć nazwę strony
                        hwnd = win32gui.GetForegroundWindow()
                        title = win32gui.GetWindowText(hwnd) if hwnd else ""
                        for k, v in sites.sites.items():
                            if k.lower() in title.lower():
                                active_key = k
                                site = True
                                break
                            active_key=name
                            site=False

                    except Exception:
                        print(Exception)
                        active_key = name
                    
                else:
                    active_key = name
                    site = False
            else:
                active_key = None
                site = False

            if active_key != self.current:
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
                self.current = active_key
                self.start_time = now
                if site:
                    grupa = sites.sites[self.current]
                else:
                    grupa = listapps.grupy.get(self.current)
            
            if grupa == 1:
                elapsed = now - self.start_time
                if elapsed >= self.group_a_total:
                    if self.on_limit_reached:
                        # sygnał do GUI – bez blokowania
                        hwnd = win32gui.GetForegroundWindow()
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        self.on_limit_reached(pid)
                    self.group_a_total = 0
                

            time.sleep(self.poll_interval)

        # przy zatrzymaniu wątku dolicz ostatnią sesję (jeśli wystarczająco długa)
        now = time.monotonic()
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


    def save_times(self):
        """Zapisuje czas grupy A do pliku JSON."""
        try:
            data = {"group_a_seconds": int(self.group_a_total)}
            with open(times_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass


    def load_times(self):
        """Wczytuje zapisany czas grupy A (jeśli istnieje). Zwraca liczbę sekund lub 0."""
        if not os.path.exists(times_file_path):
            return 0
        try:
            with open(times_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("group_a_seconds", 0))
        except Exception:
            return 0
        
    def load_times_path():
        """
        Wczytuje ścieżkę do pliku times.json z pliku times_path.json.
        Jeśli plik nie istnieje lub jest błędny → używa domyślnej ścieżki.
        """
        global times_file_path

        if not os.path.exists(TIMES_PATH_FILE):
            times_file_path = DEFAULT_TIMES_FILE
            return
        try:
            with open(TIMES_PATH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_path = data.get("times_file")

                if isinstance(custom_path, str) and custom_path.strip():
                    times_file_path = custom_path.strip()
                else:
                    times_file_path = DEFAULT_TIMES_FILE
        except Exception:
            times_file_path = DEFAULT_TIMES_FILE
    def save_times_path(new_path: str):
        """
        Zapisuje nową ścieżkę do pliku times_path.json i aktualizuje zmienną globalną.
        """
        global times_file_path
        new_path = new_path.strip()

        if not new_path:
            return False

        try:
            with open(TIMES_PATH_FILE, "w", encoding="utf-8") as f:
                json.dump({"times_file": new_path}, f, indent=4, ensure_ascii=False)

            times_file_path = new_path
            return True

        except Exception:
            return False




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


        self.blocker_cooldown_until = 0  # timestamp do którego blokera nie pokazujemy
        # czcionka domyślna
        font_path = os.path.abspath("BoldPixels.ttf") # credits BoldPixels Font by Yūki (@YukiPixels)
        ctypes.windll.gdi32.AddFontResourceW(font_path)
        
        self.default_font = tkfont.Font(family="BoldPixels", size=16)
        self.root.option_add("*Font", self.default_font)
        style = ttk.Style(self.root)
        style.configure(".", font=("BoldPixels", 16))

        # lista aplikacji z backendu
        self.apps = listapps.get_sorted_exe_list()

        self.apps_full = list(self.apps)  # pełna niezmieniana lista
        # pole wyszukiwania
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(root, textvariable=self.search_var, width=40)
        self.search_entry.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_listbox())

        # do obslugi wylaczania procesu z poziomu blokera
        self.blocked_pid = None
        self.blocked_proc_name = None

        #apocalypse mode
        self.apocalypse_enabled = self._load_apocalypse_state()
        
        # Listbox
        self.listbox = tk.Listbox(root, height=20, width=40, font=self.default_font)
        self.listbox.grid(row=1, column=0, rowspan=6, padx=10, pady=10)
        self.populate_listbox()

        # przyciski grup
        ttk.Button(root, text="Dodaj do grupy A (produktywne)",
                   command=lambda: self.add_to_group("A")).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(root, text="Dodaj do grupy B (nieproduktywne)",
                   command=lambda: self.add_to_group("B")).grid(row=1, column=1, padx=10, pady=5)
        ttk.Button(root, text="Usuń z grup", command=self.remove_from_group).grid(row=2, column=1, padx=10, pady=5)
        
        ttk.Button(root, text="Dodaj stronę", command=self.open_add_site_dialog).grid(row=3, column=1, padx=10, pady=5)

        # przycisk: dodaj folder do skanowania
        ttk.Button(root, text="Dodaj folder do skanowania", command=self.add_scan_folder_dialog).grid(row=7, column=0, padx=10, pady=5)

        #przycisk do przełaczania apocalypse mode
        ttk.Button(root, text="Toggle Apocalypse Mode", command=self.try_toggle_apocalypse).grid(row=7, column=1, padx=10, pady=5)

        # pole tekstowe z wynikami grup
        self.output = tk.Text(root, width=50, height=12, font=self.default_font)
        self.output.grid(row=4, column=1, rowspan=3, padx=10, pady=10)

        # pole z podsumowaniem czasu (aktualizowane okresowo)
        ttk.Label(root, text="Czas (sekundy) spędzony przy procesach:").grid(row=8, column=0, columnspan=2, pady=(5, 0))
        self.totals_box = tk.Text(root, width=80, height=10, font=self.default_font)
        self.totals_box.grid(row=9, column=0, columnspan=2, padx=10, pady=(0, 10))

        # monitor w tle
        self.stop_event = threading.Event()
        self.monitor = MonitorThread(self.stop_event, poll_interval=1.0, min_session=1.0, on_limit_reached=self.on_limit_reached)
        self.monitor.start()

        # odświeżanie GUI
        self.refresh_output()
        # pierwsze natychmiastowe uaktualnienie, potem co 60s (60000 ms)
        self.update_totals_periodically()

        # przechwycenie zamknięcia okna
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)


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
        if not self.apocalypse_enabled:
            selection = self.listbox.curselection()
            if not selection:
                messagebox.showwarning("Brak wyboru", "Najpierw wybierz aplikację z listy.")
                return
            idx = selection[0]
            key = self.apps[idx]
            group = 0 if group_letter == "A" else 1
            listapps.add_to_group(key, group)
            self.refresh_output()
        else: 
            messagebox.showwarning("Apocalypse is here!!!", "Najpierw wyłącz apocalypse mode!!!!.")

    def remove_from_group(self):
        """Pobiera zaznaczenie i wywołuje backendową funkcję usuwającą nazwe z grupy."""
        if not self.apocalypse_enabled:
            selection = self.listbox.curselection()
            if not selection:
                messagebox.showwarning("Brak wyboru", "Najpierw wybierz aplikację z listy.")
                return
            idx = selection[0]
            key = self.apps[idx]
            listapps.remove_from_group(key)
            self.refresh_output()
        else:
            messagebox.showwarning("Apocalypse is here!!!", "Najpierw wyłącz apocalypse mode!!!!.")


    def refresh_output(self):
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "--------PRODUKTYWNE-------- \n\n -----aplikacje-----\n")
        for k, v in listapps.grupy.items():
            if v==0:
                self.output.insert(tk.END, f"{k}\n")
        self.output.insert(tk.END, "-----strony-----\n")
        for k, v in sites.sites.items():
            if v==0:
                self.output.insert(tk.END, f"{k}\n")

        self.output.insert(tk.END, "--------NIEPRODUKTYWNE-------- \n\n -----aplikacje-----\n")
        for k, v in listapps.grupy.items():
            if v==1:
                self.output.insert(tk.END, f"{k}\n")
        self.output.insert(tk.END, "-----strony-----\n")
        for k, v in sites.sites.items():
            if v==1:
                self.output.insert(tk.END, f"{k}\n")



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
        self.totals_box.insert(tk.END, f"ilosc czasu zarobionego -> {int(self.monitor.group_a_total)}\n\n")
        for proc, secs in sorted(totals.items(), key=lambda x: -x[1]):
            if listapps.grupy.get(proc) is not None:
                group = listapps.grupy.get(proc)
            elif sites.sites.get(proc) is not None:
                group = sites.sites.get(proc)
            else:
                group = "-"
            self.totals_box.insert(tk.END, f"{proc} -> {int(secs)} s (grupa: {group})\n")

        # zaplanuj kolejne odświeżenie za 60 sekund
        self.root.after(10000, self.update_totals_periodically)

    def cleanup(self):
        # zatrzymaj wątek monitorujący
        self.stop_event.set()
        self.monitor.join(timeout=2.0)

        self._save_apocalypse_state()


        # zapisz skumulowany czas grupy A
        self.monitor.save_times()

        self.root.destroy()

    def on_close(self):
        """Zamyka aplikację: zatrzymuje monitor, zapisuje czas grupy A i kończy program."""
        if messagebox.askyesno("Zamknij", "Czy na pewno chcesz zamknąć aplikację?"):
            self.cleanup()

    def on_limit_reached(self, pid=None, name=None):
        """Wywoływane z wątku monitorującego – przekierowanie do głównego wątku Tk."""
        self.blocked_pid = pid
        self.blocked_proc_name = name
        now = time.time()
        if now < self.blocker_cooldown_until:
            return
        self.root.after(0, self.show_blocker_overlay)


    def show_blocker_overlay(self):
        """Tworzy pełnoekranową nakładkę blokującą dalszą pracę."""
        if hasattr(self, "blocker_window") and self.blocker_window is not None:
            return

        self.blocker_window = tk.Toplevel(self.root)
        self.blocker_window.title("Blokada")
        self.blocker_window.attributes("-topmost", True)
        self.blocker_window.attributes("-fullscreen", True)
        self.blocker_window.configure(bg="black")
        self.blocker_window.overrideredirect(True)

        # Tekst
        label = tk.Label(
            self.blocker_window,
            text="Twój czas na aplikacje nieproduktywne się skończył.",
            fg="white",
            bg="black",
            font=("Segoe UI", 32)
        )
        label.pack(pady=80)

        # Przycisk: zamknij aplikację
        btn_close = tk.Button(
            self.blocker_window,
            text="Zamknij tę aplikację",
            font=("Segoe UI", 24),
            command=self.close_nonproductive_app
        )
        btn_close.pack(pady=40)

        # Przycisk: daj mi 2 minuty
        btn_delay = tk.Button(
            self.blocker_window,
            text="Daj mi minute na zapisanie",
            font=("Segoe UI", 24),
            command=self.delay_blocker
        )
        btn_delay.pack(pady=40)

        # zabezpieczenie przed Alt+F4
        self.blocker_window.protocol("WM_DELETE_WINDOW", lambda: None)

        # minimalizuj aktualne okno (nieproduktywne)
        self.minimize_active_window()

        # utrzymuj topmost
        self.enforce_blocker_topmost()

    def minimize_active_window(self):
        """Minimalizuje aktualne okno (np. nieproduktywnej aplikacji)."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        except Exception:
            pass


    def enforce_blocker_topmost(self):
        """Co pewien czas ponownie wymusza topmost na oknie blokady."""
        if hasattr(self, "blocker_window") and self.blocker_window is not None:
            try:
                self.blocker_window.attributes("-topmost", True)
            except Exception:
                pass
            self.root.after(2000, self.enforce_blocker_topmost)


    def close_blocker_overlay(self):
        if hasattr(self, "blocker_window") and self.blocker_window is not None:
            try:
                self.blocker_window.destroy()
            except Exception:
                pass
            self.blocker_window = None


    def close_nonproductive_app(self):
        try:
            if self.blocked_pid:
                p = psutil.Process(self.blocked_pid)
                p.terminate()
                p.wait(timeout=3)
        except Exception:
            pass
        self.close_blocker_overlay()


        # zamknij blokera
        self.close_blocker_overlay()

    def delay_blocker(self):
        """Zamyka blokera i ustawia 2-minutowy cooldown."""
        self.blocker_cooldown_until = time.time() + 120  # 2 minuty
        self.close_blocker_overlay()

    def populate_listbox(self):
        """Wypełnia listbox zawartością self.apps (widoczną listą)."""
        self.listbox.delete(0, tk.END)
        for app in self.apps:
            self.listbox.insert(tk.END, app)

    def filter_listbox(self):
        """Filtruje self.apps_full według wpisu w self.search_var (case-insensitive, substring)."""
        q = self.search_var.get().lower()
        if q == "":
            self.apps = list(self.apps_full)
        else:
            self.apps = [a for a in self.apps_full if q in a.lower()]
        self.populate_listbox()

    def minimize_to_tray(self):
    # ukryj okno
        self.root.withdraw()
        # przygotuj ikonę (ikonę możesz załadować z pliku .ico lub PIL Image)
        image = Image.open("app_icon.png")
        menu = pystray.Menu(
            pystray.MenuItem("Pokaż", lambda icon, item: self._tray_show(icon)),
            pystray.MenuItem("Wyjdź", lambda icon, item: self._tray_quit(icon))
        )
        self.tray_icon = pystray.Icon("app", image, "Monitor", menu)
        # uruchom ikonę w osobnym wątku, żeby nie blokować Tk
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_show(self, icon):
        icon.stop()
        # bezpiecznie przywróć okno w głównym wątku Tk
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift(), self.root.focus_force()))


    def _tray_quit(self, icon):
        # zatrzymaj ikonę i wykonaj pełne zamknięcie
        icon.stop()
        self.cleanup()

    def try_toggle_apocalypse(self):
        if (self.apocalypse_enabled):
            optionsMinigame.ApocalypseDialog(self.root, self.toggle_apocalypse)
        else:
            self.toggle_apocalypse()

    def toggle_apocalypse(self):
        self.apocalypse_enabled = not self.apocalypse_enabled
        state = "ON" if self.apocalypse_enabled else "OFF"
        messagebox.showinfo("Apocalypse Mode", f"Apocalypse mode: {state}")

    def _load_apocalypse_state(self):
        """Wczytuje stan Apocalypse z pliku. Zwraca bool."""
        try:
            path = APOCALYPSE_FILE
            if not os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("apocalypse_enabled", False))
        except Exception:
            return False

    def _save_apocalypse_state(self):
        """Zapisuje aktualny stan self.apocalypse_enabled do pliku (atomowo)."""
        try:
            path = APOCALYPSE_FILE
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"apocalypse_enabled": bool(self.apocalypse_enabled)}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
            
    def open_add_site_dialog(self):
        sites.AddSiteDialog(self.root, on_submit=self._on_site_added)

    def _on_site_added(self, keyword: str, group: int):
        # zapis do sites.py
        sites.add_site(keyword, group)
        # odśwież widoki (np. output i ewentualne listy)
        self.refresh_output()
        messagebox.showinfo("Dodano", f"Dodano stronę '{keyword}' do grupy {'A' if group==0 else 'B'}.")



def main():
    # Etykieta: Punkt wejścia aplikacji GUI.
    root = tk.Tk()
    AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
