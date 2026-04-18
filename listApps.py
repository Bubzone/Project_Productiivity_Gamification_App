#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wypisuje na konsolę nazwy zainstalowanych aplikacji:
- czyta klucze Uninstall (HKLM 64/32, HKCU)
- skanuje katalogi Start Menu (.lnk) i próbuje rozwiązać target (opcjonalnie przez pywin32)
Wynik: unikalne, posortowane nazwy aplikacji wypisane na stdout.
"""

import os
import winreg
from pathlib import Path

# opcjonalnie: do rozwiązywania .lnk (wymaga pywin32)
try:
    import win32com.client
except Exception:
    win32com = None

grupy = {}

def read_uninstall_names(root, subpath, wow64_flag=0):
    """Zwraca listę DisplayName z danej gałęzi Uninstall."""
    names = []
    access = winreg.KEY_READ
    if wow64_flag:
        access |= wow64_flag
    try:
        key = winreg.OpenKey(root, subpath, 0, access)
    except FileNotFoundError:
        return names
    i = 0
    while True:
        try:
            subname = winreg.EnumKey(key, i)
        except OSError:
            break
        i += 1
        try:
            subkey = winreg.OpenKey(key, subname, 0, access)
            try:
                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                if display_name:
                    names.append(str(display_name).strip())
            except OSError:
                pass
            try:
                winreg.CloseKey(subkey)
            except Exception:
                pass
        except Exception:
            # ignoruj błędy pojedynczych podkluczy
            pass
    try:
        winreg.CloseKey(key)
    except Exception:
        pass
    return names

def scan_registry_all():
    """Skanuje główne gałęzie Uninstall i zwraca listę nazw."""
    all_names = []
    # HKLM 64-bit
    all_names += read_uninstall_names(winreg.HKEY_LOCAL_MACHINE,
                                      r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                                      winreg.KEY_WOW64_64KEY)
    # HKLM 32-bit (WOW6432Node)
    all_names += read_uninstall_names(winreg.HKEY_LOCAL_MACHINE,
                                      r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                                      winreg.KEY_WOW64_32KEY)
    # HKCU
    all_names += read_uninstall_names(winreg.HKEY_CURRENT_USER,
                                      r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                                      0)
    return all_names

def resolve_lnk_target(lnk_path):
    """Jeśli pywin32 jest dostępne, zwraca TargetPath skrótu .lnk; w przeciwnym razie None."""
    if win32com is None:
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk_path))
        return shortcut.TargetPath or None
    except Exception:
        return None

def scan_start_menu_names():
    """Skanuje oba katalogi Start Menu i zwraca listę nazw (nazwy skrótów lub targetów)."""
    results = []
    user_start = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    all_start = os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")
    for base in (user_start, all_start):
        p = Path(base)
        if not p.exists():
            continue
        for lnk in p.rglob("*.lnk"):
            # nazwa pliku bez rozszerzenia jako etykieta
            display = lnk.stem.strip()
            results.append(display)
            # spróbuj rozwiązać target i dodać basename exe (opcjonalnie)
            target = resolve_lnk_target(lnk)
            if target:
                results.append(Path(target).name)
    return results

def main():
    names = []
    #names += scan_registry_all()
    names += scan_start_menu_names()

    cleaned = set()
    for n in names:
        if not n:
            continue
        s = str(n).strip()
        if s:
            cleaned.add(s)
    exe_only = {n for n in cleaned if n.lower().endswith(".exe")}
    sorted_names = sorted(exe_only, key=lambda x: x.lower())

    print("\nLista aplikacji (indeks : nazwa):")
    for i, name in enumerate(sorted_names):
        print(f"{i}: {name}")

# zakładam, że masz już listę sorted_names i słownik grupy grupy = {}
# np. sorted_names = ["chrome.exe", "notepad.exe", ...]
    if not sorted_names:
        print("Brak aplikacji do wyświetlenia.")
    else:
        while True:
            print("Wpisz 'koniec' lub '-1' aby wyjść.")

            wybor = input("Podaj numer aplikacji, którą chcesz dodać do grupy: ").strip()
            if wybor.lower() == "koniec" or wybor== "-1":
                break

            # bezpieczne parsowanie int
            try:
                wybor_int = int(wybor)
            except ValueError:
                print("Błąd: podaj liczbę całkowitą odpowiadającą indeksowi aplikacji.")
                continue

            # sprawdzenie zakresu
            if wybor_int < 0 or wybor_int >= len(sorted_names):
                print(f"Błąd: podaj wartość od 0 do {len(sorted_names)-1}.")
                continue

            # wybór grupy (A lub B) - pętla aż do poprawnego wyboru
            while True:
                do_grupy = input("Do której grupy chcesz dodać? A - produktywne, B - nieproduktywne (wpisz 'anuluj' aby przerwać): ").strip().upper()
                if do_grupy == "ANULUJ":
                    print("Anulowano przypisanie tej aplikacji.")
                    break
                if do_grupy in ("A", "B"):
                    key = sorted_names[wybor_int]
                    grupy[key] = 0 if do_grupy == "A" else 1
                    print(f"Dodano {key} do grupy {'produktywne' if do_grupy=='A' else 'nieproduktywne'}.")
                    break
                print("Błąd: wpisz 'A' lub 'B' (lub 'anuluj').")

        print("\nZawartość słownika grupy:")
        for k, v in grupy.items():
            print(f"{k} -> {v}")


if __name__ == "__main__":
    main()
