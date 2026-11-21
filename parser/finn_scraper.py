#parser/finn_scraper.py

###
from playwright.async_api import async_playwright
from parser.geo_parser import extract_location
from bs4 import BeautifulSoup
from config import BASE_URL
import asyncio
import random
import re
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

###

def save_config(data):
    tmp = f"{CONFIG_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)

###

async def detch_page_data(page_num, browser, car_count_start):
    """
    Парсит первую страницк Finn.no и возвращает список словарей с данными машин.
    """
    page_url = f"{BASE_URL}&page={page_num}"

### # №1. Какую конкретно страницу мы парсим.
    print(f"[PARSER] Открываем вкладку под страницу {page_num}...")

    page = await browser.new_page()
    try:
        await page.goto(page_url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        html_content = await page.content()
    except Exception as e:
        print(f"[ERROR] {page_num}: {e}")
        await page.close()
        return []

    await page.close()

###

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("article")

    page_cars = []
    local_count = car_count_start

    for card in cards:
        link_tag = card.find("a", href=lambda h: h and "/mobility/item" in h)
        if not link_tag:
            continue
        local_count += 1
        href = link_tag["href"]
        full_url = href if href.startswith("http") else f"https://finn.no{href}"
        title_tag = card.find("h2")
        title = title_tag.text.strip() if title_tag else "Без названия"
        full_card_text = card.get_text(separator=" ", strip=True)

###

        # Год
        year_match = re.search(r'(19\d{2}|20\d{2})', full_card_text)
        year = int(year_match.group(0)) if year_match else None
        #Пробег
        mileage_match = re.search(r'(\d[\d\s]*)\s*km', full_card_text)
        mileage = mileage_match.group(0).strip() if mileage_match else "Пробег не указан"
        #Топливо
        fuel = "Не указано"
        fuel_match = re.search(r'(Diesel|Bensin|Hybrid|Elektrisitet|\bEl\b|Ladbar)', full_card_text, re.IGNORECASE)
        if fuel_match:
            fuel_word = fuel_match.group(0).lower()
            if fuel_word == 'diesel': fuel = "Diesel"
            elif fuel_word == 'bensin': fuel = "Bensin"
            elif fuel_word == 'hybrid': fuel = "Hybrid"
            elif fuel_word in ['elektrisitet', 'el']: fuel = "Electro" 
            elif fuel_word == "ladbar": fuel = "Plug-in Hybrid"
        #КПП
        transmission = "Не указано"
        if "automat" in full_card_text.lower() or fuel in ["Electro", "Hybrid", "Plug-in Hybrid"]:
            transmission = "Automat"
        elif "manuell" in full_card_text.lower(): 
            transmission = "Manuell"
        #Цена 
        price = "Цена не указана"
        price_match = re.search(r'\d[\d\s]*kr', full_card_text)
        if price_match:
            price = price_match.group(0).strip()
        else:
            totalpris_match = re.search(r'totalopris[:\s]*([\d\s]+)', full_card_text)
            if totalpris_match:
                price = f"Totalpris: {totalpris_match.group(1).strip()}"
        #ID
        id_match = re.search(r'/(\d+)(?:\?|$)', href)
        car_id = id_match.group(1) if id_match else f"id_{local_count}"

        # Локация (Город / Регион)
        location = extract_location(card)

        car_data = {
            "car_id": car_id,
            "title": title,
            "year": year,
            "mileage": mileage,
            "fuel": fuel,
            "transmission": transmission,
            "price": price,
            "location": location,
            "url": full_url
        }

        page_cars.append(car_data)
        print(f" Собрано: {title} [{year} --- {price}]")

### # №2. Страница полностью отработала и сколько на ней машин.
    print(f"[PARSER] <<< Страница {page_num} полностью готова. Найдено машин: {len(page_cars)}")
    return page_cars

###

from database.db_manager import delete_car, get_cars_for_maintenance, update_car_location

async def check_single_car_url(browser, car_id: str, url: str, sem: asyncio.Semaphore):
    """Проверяет одну машину по прямой ссылке: удаляет неликвид или обновляет город."""
    async with sem:
        print(f"[CHECK] Проверяю {car_id}...")

        page = await browser.new_page()

        try:
            await asyncio.sleep(random.uniform(3.5, 6.5))
            resp = await page.goto(url, timeout=30000, wait_until="domcontentloaded")

            if resp and resp.status in (404, 410):
                await delete_car(car_id)
                return

            await page.wait_for_timeout(2500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            page_text = soup.get_text(" ", strip=True)

            if "Access is temporarily restricted" in html:
                print("[BAN] FINN временно ограничил доступ! Останавливаемся.")
                raise RuntimeError("IP_BANNED")

            if any(flag in page_text for flag in [
                "Denne annonsen er ikke lenger tilgjengelig",
                "Bilen er solgt",
                "Annonsen er utløpt",
                "Annonsen er slettet"
            ]):
                await delete_car(car_id)
                return

            new_loc = "Не указано"

            map_link = soup.select_one('a[href*="/map?"]')
            if map_link:
                raw_addr = map_link.get_text(" ", strip=True)
                clean_match = re.search(r'\b\d{4}\s+(.+)$', raw_addr)
                new_loc = clean_match.group(1).strip() if clean_match else raw_addr


            if new_loc == "Не указано":
                print(f"[DEBUG] Title: {soup.title.string if soup.title else 'None'} | Snippet: {page_text[:250]}")
                print(f"[DEBUG] URL: {page.url} | Title: {await page.title()}")

            print(f"[FOUND] {car_id} -> {new_loc}")
            await update_car_location(car_id, new_loc)

        except Exception as e:
            print(f"[CLEANER ERR] {car_id}: {e}")
        finally:
            await page.close()

###

async def scrape_finn_cars():
    """
    Главный диспетчер парсера. Запускает параллельный сбор страниц.
    """

###
    import json
    import os
###

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
    max_pages = 3

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                max_pages = cfg.get("max_pages", 3)
        except Exception:
            pass

    print(f"[PARSER] Получена команда собрать страниц: {max_pages}")

    completed_pages = 0
    sem = asyncio.Semaphore(1)

    async def sem_fetch(page_num, browser):

        nonlocal completed_pages

        async with sem:
            page_data = await detch_page_data(page_num, browser, car_count_start=(page_num - 1)* 50)
            completed_pages += 1

            progress_precent = int((completed_pages / max_pages) * 85)

            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                    c_data["status"] = "running"
                    c_data["progress"] = progress_precent
                    c_data["status"] = "running"
                    c_data["progress"] = max(c_data.get("progress", 0), progress_precent)
                    save_config(c_data)

                except Exception:
                    pass

            return page_data

###

    async with async_playwright() as p:
        print("[PARSER] Запуск общего браузера для параллельных задач...")


        HEADLESS_MODE = True

        browser = await p.chromium.launch_persistent_context(
            user_data_dir="./finn_profile",
            headless=HEADLESS_MODE,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--headless=new" if HEADLESS_MODE else ""
            ]
        )

        tasks = [sem_fetch(page_num, browser) for page_num in range(1, max_pages + 1)]
        print(f"[PARSER] Запуск {max_pages} страниц через асинхронную очередь семафора...")

        results =  await asyncio.gather(*tasks)

###

        old_cars = await get_cars_for_maintenance(only_missing_location=False, limit=15)
        if old_cars:
            print(f"[CLEANER] Тихая проверка {len(old_cars)} старых машин из БД...")
            clean_sem = asyncio.Semaphore(1)
            for idx, (cid, curl) in enumerate(old_cars, start=1):
                if curl:
                    try:
                        await check_single_car_url(browser, cid, curl, clean_sem)
                        if os.path.exists(CONFIG_PATH):
                            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                                c_data = json.load(f)
                            c_data["progress"] = 85 + int((idx / len(old_cars)) *15)
                            save_config(c_data)
                    except RuntimeError as e:
                        if "IP_BANNED" in str(e):
                            print("[CLEANER] Пауза фоновой проверки до следующего цикла.")
                            break
        await browser.close()

###

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                c_data = json.load(f)
            c_data["status"] = "sleeping"
            c_data["progress"] = 0
            save_config(c_data)
        except Exception:
            pass

###

    cars_list = []
    for page_results in results:
        cars_list.extend(page_results)

    return cars_list
