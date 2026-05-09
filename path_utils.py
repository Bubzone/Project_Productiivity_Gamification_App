import json
import os
import sys

def resource_path(filename):
    if getattr(sys, 'frozen', False):
        if os.path.exists(os.path.join(sys._MEIPASS, filename)):
            base = sys._MEIPASS 
        else:
            base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)

def resolve_path(path):
    """Rozwiązuje ścieżkę: bezwzględna pozostaje bez zmian, względna względem katalogu aplikacji."""
    path = os.path.expanduser(os.path.expandvars(path.strip()))
    if os.path.isabs(path):
        return path
    return resource_path(path)

def load_json_file(path, default=None):
    full_path = resolve_path(path)
    if not os.path.exists(full_path):
        print(f"Plik {full_path} nie istnieje. Zwracam wartość domyślną.")
        return default
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        print(f"Nie można wczytać pliku {full_path}. Zwracam wartość domyślną.")
        return default

def save_json_file(path, data, indent=4):
    full_path = resolve_path(path)
    try:
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception:
        print(f"Nie można zapisać pliku {full_path}.")
        return False
