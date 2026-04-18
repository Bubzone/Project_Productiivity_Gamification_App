import time
import win32gui, win32process
import psutil
from pathlib import Path
import listApps002

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

def monitor(poll_interval=1.0, min_session=1.0):
    listApps002.main()
    grupy = listApps002.grupy
    current = None
    start = time.monotonic()
    totals = {}
    try:
        while True:
            name, title = get_active_process()
            now = time.monotonic()

            if name != current:
                elapsed = now - start
                if current and elapsed >= min_session:
                    totals[current] = totals.get(current, 0) + elapsed
                current = name
                start = now
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("Zakończono. Suma:", totals)

if __name__ == "__main__":
    monitor()
