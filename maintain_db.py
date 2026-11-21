# finn_project/maintain_db.py

###
import asyncio
from playwright.async_api import async_playwright
from database.db_manager import get_cars_for_maintenance
from parser.finn_scraper import check_single_car_url
###

async def run_maintenance():

    cars = (await get_cars_for_maintenance(only_missing_location=True))[:4615]
    print("=== ЗАПУСК ОБСЛУЖИВАНИЯ БД ===")
    print(f"Найдено машин для обновления: {len(cars)}")

    if not cars:
        print("Все данные актуальны!")
        return

    async with async_playwright() as p:

        context = await p.chromium.launch_persistent_context(
            user_data_dir="./finn_profile",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        sem = asyncio.Semaphore(1)
        total = len(cars)
        for idx, (cid, curl) in enumerate(cars, start=1):
            if curl:
                print(f"\n--- Прогресс: [{idx}/{total}] ---")
                await check_single_car_url(context, cid, curl, sem)

 #       sem = asyncio.Semaphore(1)
 #       tasks = [check_single_car_url(context, cid, curl, sem) for cid, curl in cars if curl]
 #       await asyncio.gather(*tasks)
 #       await context.close()

    print("=== ОБСЛУЖИВАНИЕ ЗАВЕРШЕНО ===")

if __name__ == "__main__":
    asyncio.run(run_maintenance())
