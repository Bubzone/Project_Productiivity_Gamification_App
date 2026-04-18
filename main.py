import time
import win32gui, win32process
import psutil
import ctypes, win32con
from pathlib import Path


grupy = {}

def get_active_process():
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except Exception:
        name = None
    return name, title

def add_to_group(name):
        wybor_grupy = ctypes.windll.user32.MessageBoxW(None, "Czy dodać do grupy produktywnych? (kliknięcie NIE doda do grupy drugiej)", "Wybór grupy", win32con.MB_YESNO)
        if wybor_grupy == win32con.IDYES:
            A.append(name)
        elif wybor_grupy == win32con.IDNO:
            B.append(name)

def program_start():
    p = Path(Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs")
    for f in p.rglob("*.lnk"):
        print(f)

def monitor(poll_interval=1.0, min_session=1.0):
    current = None
    start = time.monotonic()
    totals = {}
    program_start()
    try:
        while True:
            name, title = get_active_process()
            now = time.monotonic()
            
            if name in grupy:
                add_to_group(name)

            if name != current:
                elapsed = now - start
                if current and elapsed >= min_session:
                    totals[current] = totals.get(current, 0) + elapsed
                current = name
                start = now
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("Zakończono. Suma:", totals)
        print(grupy)

if __name__ == "__main__":
    monitor()
