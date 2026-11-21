### finn_project/notifier/tg_bot.py

###
import urllib.request
import urllib.parse
import json
import re
import os
###

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TG_CONFIG_PATH = os.path.join(BASE_DIR, "tg_config.json")

###

def load_tg_config() -> dict:
    if os.path.exists(TG_CONFIG_PATH):
        try:
            with open(TG_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "filters": {}
    }


def save_tg_config(data: dict):
    tmp = f"{TG_CONFIG_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, TG_CONFIG_PATH)


def send_telegram_message(bot_token: str, chat_id: str, text: str, silent: bool = False) -> bool:
    if not bot_token or not chat_id:
        return False

    base = "https://" + "api.telegram.org/bot"
    url = f"{base}{bot_token.strip()}/sendMessage"

    payload = {
        "chat_id": chat_id.strip(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "disable_notification": False
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[TG ERROR] Не удалось отправить сообщение: {e}")
        return False


def _extract_int(val) -> int:
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    digits = re.sub(r"\D", "", str(val))
    return int(digits) if digits else 0

def car_matches_filters(car: dict, filters: dict) -> bool:
    print(f"[TG DEBUG] Проверяем авто: {car.get('title')} | цена={car.get('price')}")
    if not filters:
        return True

    # 1 kpp
    f_trans = filters.get("transmission", "Все")
    if f_trans != "Все" and car.get("transmission") != f_trans:
        return False

    # 2 fuel
    f_fuel = filters.get("fuel", "Все")
    if f_fuel != "Все" and car.get("fuel") != f_fuel:
        return False

    # 3 geo
    f_geo = filters.get("geo", "Все")
    if f_geo != "Все" and car.get("location") != f_geo:
        return False

    # 4 search
    f_search = filters.get("search", "").strip().lower()
    if f_search and f_search not in str(car.get("title", "")).lower():
        return False

    # 5 years
    year = int(car.get("year") or 0)
    if year > 0:
        min_y = filters.get("min_year", 1900)
        max_y = filters.get("max_year", 2100)
        if isinstance(min_y, (list, tuple)):
            min_y = min_y[0]
        if isinstance(max_y, (list, tuple)):
            max_y = max_y[-1]
        if year < int(min_y) or year > int(max_y):
            return False

    # 6 mileage
    max_mileage = filters.get("max_mileage", 9999999)
    car_mileage = _extract_int(car.get("mileage"))
    if car_mileage > 0 and car_mileage > max_mileage:
        return False

    # 7 max_price
    min_price = filters.get("min_price", 0)
    max_price = filters.get("max_price", 0)
    if (min_price and min_price > 0) or (max_price and max_price > 0):
        car_price = _extract_int(car.get("price"))
        print(f"[TG DEBUG] Цена авто={car_price}, фильтр={min_price}..{max_price}")
        if car_price > 0:
            if min_price and car_price < int(min_price):
                return False
            if max_price and car_price > int(max_price):
                return False

    return True

_PENDING_EVENTS = []

def notify_car_event(car: dict, event_type: str, old_price: str = ""):
    """Вызывается при появлении новой машины ('new') или снижении цены ('price_drop')."""
    cfg = load_tg_config()
    if not cfg.get("enabled"):
        print("[TG SKIP] Уведомления выключены в tg_config.json")
        return

    if not car_matches_filters(car, cfg.get("filters", {})):
        print(f"[TG SKIP] Машина не прошла фильтры: {car.get('title')}")
        return

    _PENDING_EVENTS.append({
        "car": car,
        "event_type": event_type,
        "old_price": old_price
    })


    title = car.get("title", "Автомобиль")
    year = car.get("year", "-")
    price = car.get("price", "Цена не указана")
    loc = car.get("location", "Не указана")
    fuel = car.get("fuel", "-")
    trans = car.get("transmission", "-")
    mileage = car.get("mileage", "-")
    url = car.get("url", "")

def flush_car_events():
    """Отправляем все накопеленые за цикл машины одним сообнием."""
    global _PENDING_EVENTS
    if not _PENDING_EVENTS:
        return

    cfg = load_tg_config()
    if not cfg.get("enabled"):
        _PENDING_EVENTS.clear()
        return

    events = list(_PENDING_EVENTS)
    _PENDING_EVENTS.clear()

    total = len(events)

###

    if total == 1:
        item = events[0]
        car = item["car"]
        title = car.get("title", "Автомобиль")
        year = car.get("year", "-")
        price = car.get("price", "Цена не указана")
        loc = car.get("location", "Не указана")
        fuel = car.get("fuel", "-")
        trans = car.get("transmission", "-")
        mileage = car.get("mileage", "-")
        url = car.get("url", "")

        if item["event_type"] == "price_drop":
            header = "Снижение цены по твоим фильтрам:"
            price_line = f"Цена: {item['old_price']} -> {price}"
        else:
            header = "Новая машина по твоим фильтрам:"
            price_line = f"Цена: {price}"

#        msg = (
#            f"{header}\n\n"
#            f"{title} {year}\n"
#            f"{price_line}\n"
#            f"Город: {loc}\n"
#            f"Кпп: {trans}\n"
#            f"Топливо: {fuel}\n"
#            f"Пробег: {mileage}\n"
#            f"<a href=\"{url}\">Открыть объявление на Finn.no</a>"
#        )
        msg = (
            f"{header}\n\n"
            f"1. <a href=\"{url}\">{title} ({year})</a> - {price_line} ({loc})\n"
            f"КПП: {trans} | Топливо: {fuel} | Пробег: {mileage}"
        )

    else:
        lines = [f"Найдено изменений по фильтрам: {total}\n"]
        for i, item in enumerate(events[:15], start=1):
            car = item["car"]
            title = car.get("title", "Автомобиль")
            year = car.get("year", "-")
            price = car.get("price", "Цена не указана")
            loc = car.get("location", "Не указана")
            fuel = car.get("fuel", "-")
            url = car.get("url", "")
            tag = " " if item["event_type"] == "price_drop" else " "
            lines.append(f"{i}, {tag} <a href=\"{url}\">{title} ({year})</a> - <b>{price}</b> ({loc})")

        if total > 15:
            lines.append(f"\n<i>...и ещё {total - 15} авто. Все машины уже доступны в таблице парсера.</i>")

        msg = "\n".join(lines)

    send_telegram_message(
        cfg.get("bot_token", ""),
        cfg.get("chat_id", ""),
        msg,
        silent=False
    )
