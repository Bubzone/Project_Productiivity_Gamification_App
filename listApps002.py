# listApps002.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path

# opcjonalnie: do rozwiązywania .lnk (wymaga pywin32)
try:
    import win32com.client
except Exception:
    win32com = None

GRUPY_FILE = "grupy.json"
SCAN_PATHS_FILE = "scan_paths.json"
grupy = {}           # słownik: nazwa.exe -> 0/1
_scan_paths = []     # lista dodatkowych ścieżek do skanowania (string)


# ---------------- ZAPIS / ODCZYT GRUP I SCAN PATHS ----------------

def load_groups():
    """Wczytuje słownik grup z pliku JSON, jeśli istnieje."""
    global grupy
    if not os.path.exists(GRUPY_FILE):
        grupy = {}
        return
    try:
        with open(GRUPY_FILE, "r", encoding="utf-8") as f:
            grupy = json.load(f)
    except Exception:
        grupy = {}


def save_groups():
    """Zapisuje słownik grup do pliku JSON."""
    try:
        with open(GRUPY_FILE, "w", encoding="utf-8") as f:
            json.dump(grupy, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def load_scan_paths():
    """Wczytuje listę dodatkowych ścieżek do skanowania."""
    global _scan_paths
    if not os.path.exists(SCAN_PATHS_FILE):
        _scan_paths = []
        return
    try:
        with open(SCAN_PATHS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _scan_paths = [str(p) for p in data if p and Path(p).exists()]
            else:
                _scan_paths = []
    except Exception:
        _scan_paths = []


def save_scan_paths():
    """Zapisuje listę dodatkowych ścieżek do pliku JSON."""
    try:
        with open(SCAN_PATHS_FILE, "w", encoding="utf-8") as f:
            json.dump(_scan_paths, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def add_scan_path(path_str: str):
    """
    Dodaje nową ścieżkę do listy skanowanych folderów.
    Zwraca True jeśli dodano, False jeśli nie (np. nieistniejąca ścieżka lub już dodana).
    """
    p = Path(path_str).expanduser()
    if not p.exists() or not p.is_dir():
        return False
    sp = str(p.resolve())
    if sp in _scan_paths:
        return False
    _scan_paths.append(sp)
    save_scan_paths()
    return True


# ---------------- SKANOWANIE APLIKACJI ----------------

def resolve_lnk_target(lnk_path):
    """
    Jeśli pywin32 jest dostępne, zwraca TargetPath skrótu .lnk; w przeciwnym razie None.
    """
    if win32com is None:
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk_path))
        return shortcut.TargetPath or None
    except Exception:
        return None


def scan_start_menu_and_desktop():
    """
    Skanuje Start Menu (user + all) oraz pulpit użytkownika i publiczny.
    Obsługuje pliki .lnk (rozwiązuje target) oraz dodaje nazwy skrótów.
    Zwraca set nazw (mogą zawierać nazwy plików .exe).
    """
    results = set()

    user_start = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    all_start = os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")
    user_desktop = Path.home() / "Desktop"
    public_desktop = Path(os.path.expandvars(r"%PUBLIC%\Desktop"))

    bases = [user_start, all_start, str(user_desktop), str(public_desktop)]

    for base in bases:
        p = Path(base)
        if not p.exists():
            continue

        # dodaj bezpośrednie pliki .exe w katalogu (i podkatalogach)
        for exe in p.rglob("*.exe"):
            try:
                results.add(exe.name)
            except Exception:
                continue

        # .lnk: dodaj nazwę skrótu i (jeśli możliwe) basename targetu
        for lnk in p.rglob("*.lnk"):
            try:
                display = lnk.stem.strip()
                if display:
                    results.add(display)
                target = resolve_lnk_target(lnk)
                if target:
                    results.add(Path(target).name)
            except Exception:
                continue

    return results


def scan_folder_for_exes(folder_path: str):
    """
    Skanuje podany folder rekurencyjnie i zwraca set nazw plików .exe (basename).
    Użyteczne do skanowania katalogów z grami.
    """
    results = set()
    try:
        p = Path(folder_path)
        if not p.exists() or not p.is_dir():
            return results
        for f in p.rglob("*.exe"):
            try:
                results.add(f.name)
            except Exception:
                continue
    except Exception:
        pass
    return results


def get_sorted_exe_list():
    """
    Zwraca posortowaną listę nazw kończących się na .exe znalezionych w Start Menu,
    na pulpicie oraz w dodatkowych ścieżkach (_scan_paths).
    """
    results = set()

    # podstawowy skan Start Menu + Desktop
    results.update(scan_start_menu_and_desktop())

    # dodatkowe ścieżki wskazane przez użytkownika
    for sp in list(_scan_paths):
        results.update(scan_folder_for_exes(sp))

    # filtruj tylko nazwy kończące się na .exe
    exe_only = {n for n in results if isinstance(n, str) and n.lower().endswith(".exe")}
    cleaned = [str(x).strip() for x in exe_only if x and str(x).strip()]
    return sorted(set(cleaned), key=lambda s: s.lower())


# ---------------- OPERACJE NA GRUPACH (API) ----------------

def add_to_group(app_name: str, group: int):
    """Dodaj/aktualizuj aplikację w grupie (0 lub 1). Zapisuje plik."""
    if not app_name:
        return
    grupy[app_name] = int(group)
    save_groups()


def remove_from_group(app_name: str):
    """Usuń aplikację ze słownika grup (jeśli istnieje). Zapisuje plik."""
    if app_name in grupy:
        del grupy[app_name]
        save_groups()


# inicjalizacja przy imporcie
load_groups()
load_scan_paths()
