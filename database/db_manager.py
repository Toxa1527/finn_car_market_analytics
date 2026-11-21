# finn_project/database/db_manager.py

###
from datetime import datetime
import aiosqlite
import os

from notifier.tg_bot import notify_car_event, _extract_int
###

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "cars.db")

BAD_LOCATIONS = {"", "Не указано", "Gå til annonsen", None}
###

def clean_location(raw_loc: str) -> str:
    if not raw_loc:
        return "Не указано"
    loc = raw_loc.strip()
    if loc in BAD_LOCATIONS or "annonsen" in loc.lower():
        return "Не указано"
    return loc

###

async def init_db():
    """Создание таблиц в базе данных."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                car_id TEXT PRIMARY KEY,
                title TEXT,
                year INTEGER,
                mileage TEXT,
                fuel TEXT,
                transmission TEXT,
                price TEXT,
                location TEXT,
                url TEXT,
                updated_at TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_history ( 
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id TEXT,
                old_price TEXT,
                new_price TEXT,
                changed_at TEXT,
                FOREIGN KEY (car_id) REFERENCES cars (car_id)
            )
        """)
        await db.commit()
        print("[DB] База данных и таблицы успешно инициализированы.")

###

async def save_or_update_car(car: dict):
    """Сохраняет машину или обновляет её данные с защитой от затирания города."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_location = clean_location(car.get('location'))

    event_to_send = None
    old_price_val = ""
    final_loc_for_tg = new_location

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT price, location FROM cars WHERE car_id = ?", 
            (car['car_id'],)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            old_price, old_location = row
            final_location = new_location if new_location != "Не указано" else (old_location or "Не указано")
            final_loc_for_tg = final_location

            if old_price != car['price']:
                await db.execute("""
                    INSERT INTO price_history (car_id, old_price, new_price, changed_at)
                    VALUES (?, ?, ?, ?)
                """, (car['car_id'], old_price, car['price'], current_time))
                print(f"[DB] Цена {car['car_id']} изменилась: {old_price} -> {car['price']}")

                old_num = _extract_int(old_price)
                new_num = _extract_int(car['price'])
                if old_num > 0 and 0 < new_num < old_num:
                    event_to_send = "price_drop"
                    old_price_val = old_price

            await db.execute("""
                UPDATE cars
                SET title = ?, year = ?, mileage = ?, fuel = ?, transmission = ?, 
                    price = ?, location = ?, url = ?, updated_at = ?
                WHERE car_id = ?
            """, (
                car['title'], car['year'], car['mileage'], car['fuel'], 
                car['transmission'], car['price'], final_location, 
                car['url'], current_time, car['car_id']
            ))
        else:
            await db.execute("""
                INSERT INTO cars (car_id, title, year, mileage, fuel, transmission, price, location, url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                car['car_id'], car['title'], car['year'], car['mileage'], 
                car['fuel'], car['transmission'], car['price'], new_location, 
                car['url'], current_time
            ))
            event_to_send = "new"

        await db.commit()

    if event_to_send:
        car_copy = dict(car)
        car_copy['location'] = final_loc_for_tg
        notify_car_event(car_copy, event_to_send, old_price=old_price_val)

###

async def delete_car(car_id: str):
    """Удаляет проданую или снятую машину из бд и её историю цен."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM price_history WHERE car_id = ?", (car_id,))
        await db.execute("DELETE FROM cars WHERE car_id = ?", (car_id,))
        await db.commit()
        print(f"[DB] Неликвид удалён: {car_id}")

async def get_cars_for_maintenance(only_missing_location: bool = True, limit: int = None):
    """Возвращает список (car_id, url) для проверки актуальности или дозаполнения."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = """
            SELECT car_id, url FROM cars
            WHERE location IN ('Не указано', 'Gå til annonsen') OR location IS NULL
            OR transmission = 'Не указано' OR transmission IS NULL
            OR fuel = 'Не указано' OR fuel IS NULL
            ORDER BY RANDOM()
        """
        if limit:
            query += f" LIMIT {limit}"

        async with db.execute(query) as cursor:
            return await cursor.fetchall()

async def update_car_location(car_id: str, new_location: str):
    """Точечно обновляет город для существующей машины."""
    cleaned = clean_location(new_location)

    if cleaned == "Не указано":
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE cars SET location = ?, updated_at = ? WHERE car_id = ?",
            (cleaned, current_time, car_id)
        )
        await db.commit()
        print(f"[DB] Обновлен город для {car_id} -> {cleaned}")


