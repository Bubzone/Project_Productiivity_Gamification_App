# sites.py
import os
import json
from typing import Dict
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog

SITES_FILE = "sites.json"
sites = {}
# struktura: {"keyword": group} gdzie group: 0 = produktywne, 1 = nieproduktywne
def load_sites() -> Dict[str, int]:
    global sites

    if not os.path.exists(SITES_FILE):
        sites = {}
    try:
        with open(SITES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # upewnij się, że klucze są lowercase i wartości int
            sites = data
    except Exception:
        sites = {}

def save_sites() -> None:
    global sites
    try:
        with open(SITES_FILE, "w", encoding="utf-8") as f:
            json.dump(sites, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def add_site(keyword: str, group: int) -> None:
    global sites
    keyword = keyword.strip().lower()
    if not keyword:
        return
    sites[keyword] = int(group)
    save_sites()

def remove_site(keyword: str) -> None:
    global sites
    keyword = keyword.strip().lower()
    if keyword in sites:
        del sites[keyword]
        save_sites()

class AddSiteDialog(tk.Toplevel):
    def __init__(self, parent, on_submit):
        super().__init__(parent)
        self.title("Dodaj stronę")
        self.resizable(False, False)
        self.on_submit = on_submit

        ttk.Label(self, text="Nazwa strony (fragment tytułu):").grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.entry_var, width=40)
        self.entry.grid(row=1, column=0, padx=10, pady=5)
        self.entry.focus_set()

        ttk.Label(self, text="Wybierz grupę:").grid(row=2, column=0, padx=10, pady=(10, 0), sticky="w")
        self.group_var = tk.IntVar(value=1)  # domyślnie nieproduktywne
        rb_frame = ttk.Frame(self)
        rb_frame.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        ttk.Radiobutton(rb_frame, text="Produktywne (A)", variable=self.group_var, value=0).pack(side="left", padx=(0,10))
        ttk.Radiobutton(rb_frame, text="Nieproduktywne (B)", variable=self.group_var, value=1).pack(side="left")

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0, padx=10, pady=10, sticky="e")
        ttk.Button(btn_frame, text="Anuluj", command=self.destroy).pack(side="right", padx=(0,5))
        ttk.Button(btn_frame, text="Dodaj", command=self._submit).pack(side="right")

        # zamknij dialog przy Esc
        self.bind("<Escape>", lambda e: self.destroy())

    def _submit(self):
        kw = self.entry_var.get().strip()
        if not kw:
            messagebox.showwarning("Brak nazwy", "Wpisz nazwę strony (np. 'youtube' lub 'chatgpt').")
            return
        grp = int(self.group_var.get())
        try:
            self.on_submit(kw, grp)
        finally:
            self.destroy()

load_sites()