# listApps002.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
import winreg
from path_utils import load_json_file, save_json_file


# opcjonalnie: do rozwiązywania .lnk (wymaga pywin32)
try:
    import win32com.client
except Exception:
    win32com = None

GRUPY_FILE = "grupy.json"
SCAN_PATHS_FILE = "scan_paths.json"
grupy = {}           # słownik: nazwa.exe -> 0/1
_scan_paths = []     # lista dodatkowych ścieżek do skanowania (string)

LAUNCHER_REGISTRY_PATHS = {
    "Steam": [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ],
    "Epic": [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher", "AppDataPath"),
    ],
    "GOG": [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\GalaxyClient", "path"),
    ],
    "Ubisoft": [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Ubisoft\Launcher", "InstallDir"),
    ],
    "EA": [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Electronic Arts\EA Desktop", "InstallLocation"),
    ],
    "BattleNet": [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Blizzard Entertainment\Battle.net", "InstallPath"),
    ],
}

# ---------------- ZAPIS / ODCZYT GRUP I SCAN PATHS ----------------

def load_groups():
    """Wczytuje słownik grup z pliku JSON, jeśli istnieje."""
    global grupy
    grupy = load_json_file(GRUPY_FILE, {}) or {}


def save_groups():
    """Zapisuje słownik grup do pliku JSON."""
    save_json_file(GRUPY_FILE, grupy)


def load_scan_paths():
    """Wczytuje listę dodatkowych ścieżek do skanowania."""
    global _scan_paths
    data = load_json_file(SCAN_PATHS_FILE, [])
    if isinstance(data, list):
        _scan_paths = [str(p) for p in data if p and Path(p).exists()]
    else:
        _scan_paths = []


def save_scan_paths():
    """Zapisuje listę dodatkowych ścieżek do pliku JSON."""
    save_json_file(SCAN_PATHS_FILE, _scan_paths, indent=2)


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
def find_paths_in_registry(registry_entries):
    """
    registry_entries: lista krotek (root, subkey, value_name)
    Zwraca listę istniejących ścieżek (Path).
    """
    found = []

    for root, subkey, value_name in registry_entries:
        try:
            key = winreg.OpenKey(root, subkey)
            value, _ = winreg.QueryValueEx(key, value_name)
            p = Path(value)
            if p.exists():
                found.append(p)
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return found

def find_all_launcher_paths():
    all_paths = []

    for entries in LAUNCHER_REGISTRY_PATHS.values():
        paths = find_paths_in_registry(entries)
        all_paths.extend(paths)
    
    return all_paths

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

def scan_common_locations():
    """
    Jedna funkcja skanująca typowe lokalizacje
    """
    results = set()

    # -------------------------
    # 1. Start Menu + Desktop
    # -------------------------
    user_start = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    all_start = os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")
    user_desktop = Path.home() / "Desktop"
    public_desktop = Path(os.path.expandvars(r"%PUBLIC%\Desktop"))

    bases = [user_start, all_start, str(user_desktop), str(public_desktop)]

    for base in bases:
        p = Path(base)
        if not p.exists():
            continue

        # .exe w Start Menu / Desktop
        for exe in p.rglob("*.exe"):
            results.add(exe.name)

        # .lnk → nazwa skrótu + target
        for lnk in p.rglob("*.lnk"):
            display = lnk.stem.strip()
            if display:
                results.add(display)
            target = resolve_lnk_target(lnk)
            if target:
                results.add(Path(target).name)
    # -------------------------
    # 2. Launchery gier/gry
    # -------------------------
    for launcher_path in find_all_launcher_paths():
        results.update(scan_folder_for_exes(str(launcher_path)))

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
    results.update(scan_common_locations())

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
