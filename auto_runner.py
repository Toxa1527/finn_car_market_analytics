#auto_runner.py

###
from datetime import datetime
import subprocess
import json
import time
import sys
import os
###

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
RUN_SCRIPT_PATH = os.path.join(BASE_DIR, "run.py")
PID_PATH = os.path.join(BASE_DIR, "runner.pid")

###

with open(PID_PATH, "w") as f:
    f.write(str(os.getpid()))


def save_config(data):
    tmp = f"{CONFIG_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)

print(f"[{datetime.now().strftime('%H:%M:%S')}] Фоновый планировщик автозапуска запущен...")

###

time_left_seconds = -1

while True:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            mode = config.get("mode", "manual")
            interval_minutes = config.get("interval_minutes", 5)
            max_pages = config.get("max_pages", 3)

            if mode == "auto":

                if time_left_seconds < 0:
                    time_left_seconds = interval_minutes * 60

                if time_left_seconds == 0:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Таймер сработал. Запуск на {max_pages} стр...")

                    config["status"] = "running"
                    config["progress"] = 0
                    config["time_left_seconds"] = 0

                    save_config(config)

                    process = subprocess.Popen([sys.executable, RUN_SCRIPT_PATH], start_new_session=True)

                    process.wait()

                    config["progress"] = 100

                    save_config(config)

                    time.sleep(1)

                    time_left_seconds = interval_minutes * 60
                    config["status"] = "sleeping"
                    config["progress"] = 0
                    config["time_left_seconds"] = time_left_seconds

                    save_config(config)

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Фоновый парсинг завершен. Таймер поставлен на {interval_minutes} мин.\n")

                else:
                    time_left_seconds -= 1

                    config["status"] = "sleeping"
                    config["progress"] = 0
                    config["time_left_seconds"] = max(0, time_left_seconds)

                    save_config(config)

            elif mode == "manual":
                time_left_seconds = -1

        except Exception as e:
            print(f"[ERROR] Ошибка планировщика... {e}")

    time.sleep(1)
