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
import psutil
import json
import listApps002 as listapps  # backend
import pystray
from PIL import Image
import optionsMinigame
import sites
import monitor

APOCALYPSE_FILE = "apocalypse_state.json"

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
        self.root.title("Produktywność Gamifikowana")
        self.root.geometry("1200x700")

        # === KOLORY TEMATYCZNE ===
        self.COLOR_PRODUCTIVE = "#2ecc71"   # zielony
        self.COLOR_UNPRODUCTIVE = "#e74c3c" # czerwony
        self.COLOR_BG = "#ecf0f1"           # jasny szary
        self.COLOR_TEXT = "#2c3e50"         # ciemny szary
        self.COLOR_BORDER = "#bdc3c7"       # średni szary
        self.COLOR_SUCCESS = "#27ae60"      # ciemny zielony
        self.COLOR_DANGER = "#c0392b"       # ciemny czerwony

        self.blocker_cooldown_until = 0  # timestamp do którego blokera nie pokazujemy
        # czcionka domyślna
        font_path = os.path.abspath("BoldPixels.ttf") # credits BoldPixels Font by Yūki (@YukiPixels)
        ctypes.windll.gdi32.AddFontResourceW(font_path)
        
        self.default_font = tkfont.Font(family="BoldPixels", size=14)
        self.title_font = tkfont.Font(family="BoldPixels", size=16, weight="bold")
        self.small_font = tkfont.Font(family="BoldPixels", size=12)
        
        self.root.option_add("*Font", self.default_font)
        style = ttk.Style(self.root)
        style.configure(".", font=("BoldPixels", 14))

        # lista aplikacji z backendu
        self.apps = listapps.get_sorted_exe_list()
        self.apps_full = list(self.apps)  # pełna niezmieniana lista
        
        # === GÓRNY PASEK STATUSU ===
        status_frame = tk.Frame(root, bg=self.COLOR_TEXT, height=50)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)
        status_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        status_frame.columnconfigure(1, weight=0)

        status_label = tk.Label(status_frame, text="📊 MONITOR AKTYWNOŚCI", 
                               font=self.title_font, fg="white", bg=self.COLOR_TEXT)
        status_label.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self.monitor_status_label = tk.Label(status_frame, text="🔴 Monitoring: ON",
                                            font=self.default_font, fg="#2ecc71", bg=self.COLOR_TEXT)
        self.monitor_status_label.grid(row=0, column=1, padx=15, pady=10, sticky="e")

        # === WYSZUKIWANIE ===
        search_frame = tk.Frame(root, bg=self.COLOR_BG)
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        tk.Label(search_frame, text="Szukaj:", font=self.default_font, bg=self.COLOR_BG, fg=self.COLOR_TEXT).pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=self.default_font, width=50)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_listbox())

        # do obslugi wylaczania procesu z poziomu blokera
        self.blocked_pid = None
        self.blocked_proc_name = None

        #apocalypse mode
        self.apocalypse_enabled = self._load_apocalypse_state()
        
        # === GŁÓWNA ZAWARTOŚĆ - NOTEBOOK (TABY) ===
        main_container = tk.Frame(root, bg=self.COLOR_BG)
        main_container.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        main_container.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        
        self.root.rowconfigure(0, weight=0)   # status bar
        self.root.rowconfigure(1, weight=0)   # search bar
        self.root.rowconfigure(2, weight=1)   # main content
        self.root.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(main_container)
        notebook.grid(row=0, column=0, sticky="nsew")

        # === TAB 1: ZARZĄDZANIE GRUPAMI ===
        tab_groups = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab_groups, text="📋 Zarządzanie Grupami")
        tab_groups.rowconfigure(0, weight=1)
        tab_groups.columnconfigure(0, weight=1)
        tab_groups.columnconfigure(1, weight=1)

        # Left: Listbox
        list_frame = tk.Frame(tab_groups, bg=self.COLOR_BG)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        tk.Label(list_frame, text="DOSTĘPNE APLIKACJE", font=self.title_font, 
                bg=self.COLOR_BG, fg=self.COLOR_TEXT).pack(fill="x", pady=(0, 5))

        self.listbox = tk.Listbox(list_frame, font=self.default_font, bg="white", 
                                  fg=self.COLOR_TEXT, selectmode="single", height=15)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.populate_listbox()

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        # Right: Buttons
        buttons_frame = tk.Frame(tab_groups, bg=self.COLOR_BG)
        buttons_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Section 1: Grupy
        section1 = tk.LabelFrame(buttons_frame, text="PRZYPISZ DO GRUPY", 
                                font=self.title_font, bg=self.COLOR_BG, fg=self.COLOR_TEXT)
        section1.pack(fill="x", pady=10)

        btn_a = tk.Button(section1, text="✅ PRODUKTYWNE (Grupa A)", 
                         font=self.default_font, bg=self.COLOR_PRODUCTIVE, fg="white",
                         command=lambda: self.add_to_group("A"), padx=10, pady=10, relief="raised", bd=2)
        btn_a.pack(fill="x", padx=10, pady=5)

        btn_b = tk.Button(section1, text="❌ NIEPRODUKTYWNE (Grupa B)", 
                         font=self.default_font, bg=self.COLOR_UNPRODUCTIVE, fg="white",
                         command=lambda: self.add_to_group("B"), padx=10, pady=10, relief="raised", bd=2)
        btn_b.pack(fill="x", padx=10, pady=5)

        btn_remove = tk.Button(section1, text="🗑️ USUŃ Z GRUP", 
                              font=self.default_font, bg=self.COLOR_BORDER, fg=self.COLOR_TEXT,
                              command=self.remove_from_group, padx=10, pady=10, relief="raised", bd=2)
        btn_remove.pack(fill="x", padx=10, pady=5)

        # Section 2: Zarządzanie
        section2 = tk.LabelFrame(buttons_frame, text="ZARZĄDZANIE", 
                                font=self.title_font, bg=self.COLOR_BG, fg=self.COLOR_TEXT)
        section2.pack(fill="x", pady=10)

        btn_site = tk.Button(section2, text="➕ DODAJ STRONĘ", 
                            font=self.default_font, bg="#3498db", fg="white",
                            command=self.open_add_site_dialog, padx=10, pady=8, relief="raised", bd=2)
        btn_site.pack(fill="x", padx=10, pady=5)

        btn_folder = tk.Button(section2, text="📁 DODAJ FOLDER DO SKANOWANIA", 
                              font=self.default_font, bg="#9b59b6", fg="white",
                              command=self.add_scan_folder_dialog, padx=10, pady=8, relief="raised", bd=2)
        btn_folder.pack(fill="x", padx=10, pady=5)

        # Section 3: Apocalypse
        section3 = tk.LabelFrame(buttons_frame, text="TRYB APOCALYPSE", 
                                font=self.title_font, bg=self.COLOR_BG, fg=self.COLOR_TEXT)
        section3.pack(fill="x", pady=10)

        btn_apocalypse = tk.Button(section3, text="⚔️ TOGGLE APOCALYPSE MODE", 
                                  font=self.default_font, bg="#e67e22", fg="white",
                                  command=self.try_toggle_apocalypse, padx=10, pady=10, relief="raised", bd=2)
        btn_apocalypse.pack(fill="x", padx=10, pady=5)

        # === TAB 2: GRUPY ===
        tab_overview = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab_overview, text="📊 Przegląd Grup")
        tab_overview.rowconfigure(0, weight=1)
        tab_overview.columnconfigure(0, weight=1)

        self.output = tk.Text(tab_overview, font=self.default_font, bg="white", 
                             fg=self.COLOR_TEXT, wrap="word")
        self.output.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Tagi do kolorowania
        self.output.tag_configure("productive_header", foreground="white", background=self.COLOR_SUCCESS, font=self.title_font)
        self.output.tag_configure("unproductive_header", foreground="white", background=self.COLOR_DANGER, font=self.title_font)
        self.output.tag_configure("productive_text", foreground=self.COLOR_SUCCESS, font=self.default_font)
        self.output.tag_configure("unproductive_text", foreground=self.COLOR_DANGER, font=self.default_font)
        self.output.tag_configure("section_label", foreground=self.COLOR_TEXT, font=self.small_font, underline=True)

        scroll_output = ttk.Scrollbar(tab_overview, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scroll_output.set)
        scroll_output.grid(row=0, column=1, sticky="ns")

        # === TAB 3: STATYSTYKI ===
        tab_stats = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab_stats, text="⏱️ Statystyki Czasu")
        tab_stats.rowconfigure(1, weight=1)
        tab_stats.columnconfigure(0, weight=1)

        # Podsumowanie zarobionego czasu
        summary_frame = tk.Frame(tab_stats, bg=self.COLOR_SUCCESS, bd=2, relief="raised")
        summary_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        tk.Label(summary_frame, text="💰 ZAROBIONY CZAS NA GRUPY A (PRODUKTYWNE):", 
                font=self.title_font, bg=self.COLOR_SUCCESS, fg="white").pack(padx=10, pady=5, side="left")

        self.earned_time_label = tk.Label(summary_frame, text="0 sekund", 
                                         font=self.title_font, bg=self.COLOR_SUCCESS, fg="white")
        self.earned_time_label.pack(padx=10, pady=5, side="right")

        # Tabela czasów
        tk.Label(tab_stats, text="CZAS SPĘDZONY PRZY PROCESACH:", font=self.title_font, 
                bg=self.COLOR_BG, fg=self.COLOR_TEXT).grid(row=1, column=0, padx=10, pady=(10, 5), sticky="nw")

        self.totals_box = tk.Text(tab_stats, font=self.default_font, bg="white", 
                                 fg=self.COLOR_TEXT, wrap="word")
        self.totals_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tab_stats.rowconfigure(2, weight=1)

        scroll_totals = ttk.Scrollbar(tab_stats, orient="vertical", command=self.totals_box.yview)
        self.totals_box.configure(yscrollcommand=scroll_totals.set)
        scroll_totals.grid(row=2, column=1, sticky="ns", padx=(0, 10), pady=(0, 10))

        # Tagi do kolorowania czasu
        self.totals_box.tag_configure("productive", foreground=self.COLOR_SUCCESS)
        self.totals_box.tag_configure("unproductive", foreground=self.COLOR_DANGER)

        # === MONITOR W TLE ===
        self.stop_event = threading.Event()
        self.monitor = monitor.MonitorThread(self.stop_event, poll_interval=1.0, min_session=1.0, on_limit_reached=self.on_limit_reached)
        self.monitor.start()

        # odświeżanie GUI
        self.refresh_output()
        self.update_totals_periodically()
        self.update_monitor_status()

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
        """Odświeża widok grup z kolorystyką tematyczną."""
        self.output.delete("1.0", tk.END)
        
        # Sekcja PRODUKTYWNE
        self.output.insert(tk.END, "\n✅ GRUPA A: APLIKACJE PRODUKTYWNE\n", "productive_header")
        self.output.insert(tk.END, "=" * 50 + "\n", "productive_header")
        
        if any(v == 0 for v in listapps.grupy.values()) or any(v == 0 for v in sites.sites.values()):
            self.output.insert(tk.END, "\n[APLIKACJE]\n", "section_label")
            for k, v in listapps.grupy.items():
                if v == 0:
                    self.output.insert(tk.END, f"  • {k}\n", "productive_text")
            
            self.output.insert(tk.END, "\n[STRONY]\n", "section_label")
            for k, v in sites.sites.items():
                if v == 0:
                    self.output.insert(tk.END, f"  • {k}\n", "productive_text")
        else:
            self.output.insert(tk.END, "  (brak)", "productive_text")
        
        # Sekcja NIEPRODUKTYWNE
        self.output.insert(tk.END, "\n\n\u274c GRUPA B: APLIKACJE NIEPRODUKTYWNE\n", "unproductive_header")
        self.output.insert(tk.END, "=" * 50 + "\n", "unproductive_header")
        
        if any(v == 1 for v in listapps.grupy.values()) or any(v == 1 for v in sites.sites.values()):
            self.output.insert(tk.END, "\n[APLIKACJE]\n", "section_label")
            for k, v in listapps.grupy.items():
                if v == 1:
                    self.output.insert(tk.END, f"  • {k}\n", "unproductive_text")
            
            self.output.insert(tk.END, "\n[STRONY]\n", "section_label")
            for k, v in sites.sites.items():
                if v == 1:
                    self.output.insert(tk.END, f"  • {k}\n", "unproductive_text")
        else:
            self.output.insert(tk.END, "  (brak)", "unproductive_text")



    def update_monitor_status(self):
        """Aktualizuje status monitora w pasku górnym."""
        if hasattr(self, "monitor_status_label"):
            status = "🟢 Monitoring: ON" if not self.stop_event.is_set() else "🔴 Monitoring: OFF"
            self.monitor_status_label.config(text=status)
        self.root.after(2000, self.update_monitor_status)

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

        # Aktualizuj etykietę zarobionego czasu
        hours = int(self.monitor.group_a_total) // 3600
        minutes = (int(self.monitor.group_a_total) % 3600) // 60
        seconds = int(self.monitor.group_a_total) % 60
        time_str = f"{hours}h {minutes}m {seconds}s"
        self.earned_time_label.config(text=time_str)

        # Wyświetl tabela czasów
        self.totals_box.delete("1.0", tk.END)
        
        if not totals:
            self.totals_box.insert(tk.END, "Brak danych do wyświetlenia. Zaczekaj na pierwsze dane z monitora.")
        else:
            self.totals_box.insert(tk.END, f"{'Proces':<40} | {'Czas':>6} | {'Grupa':<20}\n")
            self.totals_box.insert(tk.END, "=" * 75 + "\n")
            
            for proc, secs in sorted(totals.items(), key=lambda x: -x[1]):
                if listapps.grupy.get(proc) is not None:
                    group = listapps.grupy.get(proc)
                    tag = "productive" if group == 0 else "unproductive"
                elif sites.sites.get(proc) is not None:
                    group = sites.sites.get(proc)
                    tag = "productive" if group == 0 else "unproductive"
                else:
                    group = "-"
                    tag = "productive"
                
                group_name = "(A) Produktywne" if group == 0 else "(B) Nieproduktywne" if group == 1 else "(Nieznana)"
                self.totals_box.insert(tk.END, f"{proc:<40} | {int(secs):>5} s | {group_name:<20}\n", tag)

        # zaplanuj kolejne odświeżenie za 10 sekund
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
        if not self.apocalypse_enabled:
            sites.AddSiteDialog(self.root, on_submit=self._on_site_added)
        else:
            messagebox.showwarning("Apocalypse is here!!!", "Najpierw wyłącz apocalypse mode!!!!.")

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
