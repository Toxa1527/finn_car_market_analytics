# finn_project/run.py

###
from database.db_manager import init_db, save_or_update_car
from parser.finn_scraper import scrape_finn_cars
from notifier.tg_bot import flush_car_events
import asyncio
import time
###

async def main():
    print("[MAIN] Запуск пороцесса...")

    total_start_time = time.time()

    #bd 
    db_start = time.time()
    await init_db()
    db_end = time.time()
    db_duration = db_end - db_start
    print(f"[BENCHMARK]) Инициализация БД заняла : {db_duration:.2f} сек.")

    #parser
    parser_start = time.time()
    cars = await scrape_finn_cars()
    parser_end = time.time()
    parser_duration = parser_end - parser_start
    print(f"\n[BENCHMARK] Сбор {len(cars)} машин через Playwright занял: {parser_duration:.2f} сек.")
    print(f"\n[MAIN] Успех, мдуль парсера отработал. Всего собрано машин...")

    #db 
    db_write_start = time.time()
    for car in cars:
        await save_or_update_car(car)
    flush_car_events()
    db_write_end = time.time()
    db_write_duration = db_write_end - db_write_start
    print(f"[BENCHMARK] Синхронизация {len(cars)} машин SQLite заняла: {db_write_duration:.2f} сек.")
    print("[MAIN]Данные синхронизированы с BD")

    total_duration = time.time() - total_start_time
    print(f"\n[MAIN] === Финиш БЕНЧМАРКА ===")
    print(f"[MAIN] Общее время выполнения всего скрипта: {total_duration:.2f} сек.")
if __name__ == "__main__":
    asyncio.run(main())
