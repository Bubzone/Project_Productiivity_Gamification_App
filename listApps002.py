#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import winreg
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# opcjonalnie: do rozwiązywania .lnk (wymaga pywin32)
try:
    import win32com.client
except Exception:
    win32com = None

grupy = {}  # słownik: nazwa.exe -> 0/1


# ---------------- BACKEND (bez zmian poza kosmetyką) ----------------

def read_uninstall_names(root, subpath, wow64_flag=0):
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
            winreg.CloseKey(subkey)
        except Exception:
            pass

    winreg.CloseKey(key)
    return names


def resolve_lnk_target(lnk_path):
    if win32com is None:
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk_path))
        return shortcut.TargetPath or None
    except Exception:
        return None


def scan_start_menu_names():
    results = []
    user_start = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    all_start = os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")

    for base in (user_start, all_start):
        p = Path(base)
        if not p.exists():
            continue
        for lnk in p.rglob("*.lnk"):
            display = lnk.stem.strip()
            results.append(display)
            target = resolve_lnk_target(lnk)
            if target:
                results.append(Path(target).name)
    return results


def get_sorted_exe_list():
    names = scan_start_menu_names()

    cleaned = {str(n).strip() for n in names if n}
    exe_only = {n for n in cleaned if n.lower().endswith(".exe")}
    return sorted(exe_only, key=lambda x: x.lower())


# ---------------- GUI ----------------

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Przypisywanie aplikacji do grup")

        # lista aplikacji
        self.apps = get_sorted_exe_list()

        # Listbox
        self.listbox = tk.Listbox(root, height=20, width=40)
        self.listbox.grid(row=0, column=0, rowspan=6, padx=10, pady=10)

        for app in self.apps:
            self.listbox.insert(tk.END, app)

        # przyciski grup
        ttk.Button(root, text="Dodaj do grupy A (produktywne)",
                   command=lambda: self.add_to_group("A")).grid(row=0, column=1, padx=10, pady=5)

        ttk.Button(root, text="Dodaj do grupy B (nieproduktywne)",
                   command=lambda: self.add_to_group("B")).grid(row=1, column=1, padx=10, pady=5)

        # pole tekstowe z wynikami
        self.output = tk.Text(root, width=40, height=15)
        self.output.grid(row=2, column=1, rowspan=4, padx=10, pady=10)

        self.refresh_output()

    def add_to_group(self, group):
        """Dodaje wybraną aplikację do grupy."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Brak wyboru", "Najpierw wybierz aplikację z listy.")
            return

        idx = selection[0]
        key = self.apps[idx]

        grupy[key] = 0 if group == "A" else 1
        self.refresh_output()

    def refresh_output(self):
        """Odświeża wyświetlanie słownika grup."""
        self.output.delete("1.0", tk.END)
        for k, v in grupy.items():
            self.output.insert(tk.END, f"{k} -> {v}\n")


def main():
    root = tk.Tk()
    AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
