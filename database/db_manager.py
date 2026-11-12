# finn_project/database/db_manager.py

###
from datetime import datetime
import aiosqlite
import os
###

#
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "cars.db")


async def init_db():
    """Создание таблицы в базе данных, если они еще не созданы."""
    async with aiosqlite.connect(DB_PATH) as db:
        #таблица актуальных машин
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

        try:
            await db.execute("ALTER TABLE cars ADD COLUMN location TEXT DEFAULT 'Не указано'")
        except Exception:
            pass


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
        print("[DB] База данных и таблицы успешно иницилизированы.")

async def save_or_update_car(car: dict):
    """Cохраняем машину или обновляет её цену с записью в историю."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    location = car.get('location', 'Не указано')
    
    async with aiosqlite.connect(DB_PATH) as db:
        #1 проверяем, есть ли уже такая машина в базе
        async with db.execute("SELECT price FROM cars WHERE car_id = ?", (car['car_id'],)) as cursor:
            row = await cursor.fetchone()

        if row:
            old_price = row[0]
            # если цена изменилась - пишем в историю изменений
            if old_price != car['price']:
                await db.execute("""
                    INSERT INTO price_history (car_id, old_price, new_price, changed_at)
                    VALUES (?, ?, ?, ?)
                """, (car['car_id'], old_price, car['price'], current_time))
                print(f"[DB] Цена машины {car['car_id']} изменилась: {old_price} -> {car['price']}")

            # обновляем данные в основной таблица 
            await db.execute("""
                UPDATE cars
                SET title = ?, year = ?, mileage = ?, fuel = ?, transmission = ?, price = ?, location = ?, url = ?, updated_at = ?
                WHERE car_id = ?
            """, (car['title'], car['year'], car['mileage'], car['fuel'], car['transmission'], car['price'], location, car['url'], current_time, car['car_id']))
        else:
            # машины нет в базе
            await db.execute("""
                INSERT INTO cars (car_id, title, year, mileage, fuel, transmission, price, location, url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (car['car_id'], car['title'], car['year'], car['mileage'], car['fuel'], car['transmission'], car['price'], location,  car['url'], current_time))
    
        await db.commit()
