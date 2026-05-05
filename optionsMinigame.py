# apocalypse_mode.py
import tkinter as tk
from tkinter import ttk, messagebox

class ApocalypseDialog(tk.Toplevel):
    """
    Modalny dialog minigry: użytkownik musi przepisać dokładnie podany cytat.
    Sprawdzenie odbywa się po każdej wpisanej literze. Przy pierwszym błędzie
    pokazuje się komunikat i pole jest resetowane.
    - parent: okno nadrzędne (tk root)
    - on_success: callable bez argumentów wywoływane po poprawnym przepisaniu
    - title: tytuł okna
    """

    def __init__(self, parent, on_success, title="Apocalypse challenge"):
        super().__init__(parent)
        self.parent = parent
        # tutaj ustaw swój długi cytat; możesz też przekazać go jako argument jeśli wolisz
        self.quote = (
            "To be, or not to be, that is the question:\n"
            "Whether 'tis nobler in the mind to suffer\n"
            "The slings and arrows of outrageous fortune,"
        )
        self.on_success = on_success

        self.title(title)
        self.transient(parent)
        self.resizable(False, False)

        # modalność
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)

        # UI
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            frm,
            text="Przepisz dokładnie poniższy tekst (bez zmian):",
            wraplength=800
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        quote_box = tk.Text(
            frm,
            height=6,
            width=80,
            wrap="word",
            state="disabled",
            bg=self.cget("bg"),
            relief="flat"
        )
        quote_box.grid(row=1, column=0, sticky="we")
        quote_box.configure(state="normal")
        quote_box.insert("1.0", self.quote)
        quote_box.configure(state="disabled")

        ttk.Label(frm, text="Wpisz tutaj:").grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.entry = tk.Text(frm, height=8, width=80, wrap="word")
        self.entry.grid(row=3, column=0, sticky="we", pady=(4, 8))

        # blokuj wklejanie (Ctrl+V, Shift+Insert) i menu kontekstowe
        self.entry.bind("<Control-v>", lambda e: "break")
        self.entry.bind("<Control-V>", lambda e: "break")
        self.entry.bind("<Shift-Insert>", lambda e: "break")
        self.entry.bind("<Button-3>", lambda e: "break")  # prawy przycisk myszy

        # zamiast przycisku "Sprawdź" - sprawdzamy po każdej zmianie
        # użyjemy KeyRelease, ale też obsłużymy wklejenie (choć zablokowane)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        # obsługa wstawiania przez inne mechanizmy (np. IME)
        self.entry.bind("<<Modified>>", self._on_modified)

        # focus
        self.entry.focus_set()

        # zapobiegaj zamykaniu przez Alt+F4
        self.bind_all("<Alt-F4>", lambda e: "break")

        # centrowanie okna względem parent
        self.update_idletasks()
        self._center_over_parent()

        # blokada wielokrotnego uruchomienia callbacka
        self._finished = False
        # flaga, żeby nie pokazywać wielu okien błędu jednocześnie
        self._error_shown = False

    def _center_over_parent(self):
        try:
            self.update_idletasks()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()

            w = self.winfo_width()
            h = self.winfo_height()

            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_close_request(self):
        # pozwalamy na zamknięcie okna (np. w trybie debug), ale zwalniamy grab
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _reset_entry(self):
        self.entry.delete("1.0", "end")
        # zresetuj flagę błędu, żeby kolejne wpisy mogły być sprawdzane
        self._error_shown = False

    def _on_key_release(self, event):
        # po każdym klawiszu sprawdź aktualny tekst
        self._check_progress()

    def _on_modified(self, event):
        # zabezpieczenie: niektóre widgety ustawiają flagę Modified
        try:
            self.entry.edit_modified(False)
        except Exception:
            pass
        self._check_progress()

    def _check_progress(self):
        """
        Sprawdza, czy aktualnie wpisany tekst jest prefiksem cytatu.
        - jeśli nie: pokaż komunikat o błędzie i zresetuj pole
        - jeśli tak i jest pełne dopasowanie: wywołaj sukces
        """
        typed = self.entry.get("1.0", "end-1c")
        # porównanie prefiksowe: typed musi być dokładnym początkiem quote
        expected_prefix = self.quote[:len(typed)]
        if typed == "":
            return

        if typed != expected_prefix:
            # błąd: pokaż komunikat tylko raz na błąd i zresetuj pole
            if not self._error_shown:
                self._error_shown = True
                # użyj after, żeby messagebox nie kolidował z eventami klawiatury
                self.after(10, lambda: messagebox.showwarning("Błąd", "Tekst nie zgadza się dokładnie. Zacznij od nowa."))
                # zresetuj pole po krótkim opóźnieniu, żeby użytkownik zobaczył komunikat
                self.after(50, self._reset_entry)
            return

        # jeśli prefiks się zgadza i długość równa długości cytatu -> sukces
        if len(typed) == len(self.quote):
            if not self._finished:
                self._finished = True
                try:
                    self.grab_release()
                except Exception:
                    pass
                try:
                    self.on_success()
                except Exception:
                    pass
                self.destroy()
