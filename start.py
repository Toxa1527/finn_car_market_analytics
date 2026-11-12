# finn_project_v1_release/start.py #

###
import subprocess
import webbrowser
import threading
import time
import sys
import os
###

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(BASE_DIR, "app", "main.py")

def get_python_executable():
    """Автоматически находит Python внутри .venv или venv, если скрипт запущен без активации окружения."""
    possible_venvs = [
        os.path.join(BASE_DIR, ".venv", "bin", "python"),      # Linux / WSL
        os.path.join(BASE_DIR, "venv", "bin", "python"),       # Linux / WSL (альтернатива)
        os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe"), # Windows
        os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")   # Windows (альтернатива)
    ]
    for path in possible_venvs:
        if os.path.exists(path):
            return path
    return sys.executable

def open_browser():
    """Ждёт 3 секунды и открывает вкладку в браузере (с поддержкой WSL)."""
    time.sleep(3)
    url = "http://localhost:8501"

    is_wsl = "microsoft" in os.uname().release.lower() if hasattr(os, "uname") else False

    if is_wsl:
        subprocess.run(["cmd.exe", "/c", "start", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(url)

if __name__ == "__main__":
    print("🚀 Подготовка и запуск Finn.no Analytics...")
    python_exec = get_python_executable()

    threading.Thread(target=open_browser, daemon=True).start()

    subprocess.run([
        python_exec, "-m", "streamlit", "run", APP_PATH,
        "--server.headless", "true"
    ])
