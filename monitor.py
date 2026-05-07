import threading
import win32process
import win32gui
import psutil
import time
import json
import os
import sites

import listApps002 as listapps  # backend


TIMES_PATH_FILE = "times_path.json"   # plik przechowujący ścieżkę do times.json
DEFAULT_TIMES_FILE = "times.json"     # domyślna lokalizacja
times_file_path = DEFAULT_TIMES_FILE  # aktualnie używana ścieżka


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

