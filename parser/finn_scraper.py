# finn_project_v1_release/parser/finn_scraper.py #

###
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from config import BASE_URL
import asyncio
import re
###

async def detch_page_data(page_num, browser, car_count_start):
    """
    Парсит первую страницк Finn.no и возвращает список словарей с данными машин.
    """
    page_url = f"{BASE_URL}&page={page_num}"

###

    print(f"[PARSER] Открываем вкладку под страницу {page_num}...")

    page = await browser.new_page()
    try:
        await page.goto(page_url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
#        await page.wait_for_load_state("networkidle")
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

        #Локация (Город / Регион) Псс. в разработке)
        location = "Не указано"
        strings = list(card.stripped_strings)

###

        for text in reversed(strings):
            clean_text = text.replace("•", "").strip()

            if not clean_text or len(clean_text) < 2 or len(clean_text) > 35:
                continue
            if any(word in clean_text.lower() for word in ["forhandler", "privat", "kr", "km", "totalpris", "omreg", "eks.", "inkl.", "solgt", "reservert", "diesel", "bensin", "hybrid", "elektrisitet", "automat", "manuell"]):
                continue
            if re.search(r'\d', clean_text):
                continue
            if clean_text.lower() == title.lower():
                continue

            location = clean_text
            break

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

###

    print(f"[PARSER] <<< Страница {page_num} полностью готова. Найдено машин: {len(page_cars)}")
    return page_cars

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

        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    if json.load(f).get("mode") == "manual":
                        return []  # Экстренно прерываем сбор этой страницы
            except Exception:
                pass

        async with sem:
            page_data = await detch_page_data(page_num, browser, car_count_start=(page_num - 1)* 50)
            completed_pages += 1

            progress_precent = int((completed_pages / max_pages) * 100)

            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                    c_data["status"] = "running"
                    c_data["progress"] = progress_precent
                    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(c_data, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass

            return page_data

###
    results = []
    async with async_playwright() as p:
        print("[PARSER] Запуск общего браузера для параллельных задач...")
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",  # Защита от краша памяти
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
            )

            tasks = [sem_fetch(page_num, browser) for page_num in range(1, max_pages + 1)]
            print(f"[PARSER] Запуск {max_pages} страниц через асинхронную очередь семафора...")

            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"[ERROR] Сбой работы браузера: {e}")
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    cars_list = []
    for page_results in results:
        if isinstance(page_results, list):
            cars_list.extend(page_results)

    return cars_list

