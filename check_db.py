# finn_project/check_db.py

###
from database.db_manager import DB_PATH
import sqlite3
###

def view_database():
    # Подключаемся к файлу базы данных
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n=== ЧТО СЕЙЧАС ЛЕЖИТ В БАЗЕ ДАННЫХ ===")
    
    try:
        # Пишем обычный SQL-запрос: выбрать ID, заголовок, год и цену 
        # из таблицы cars и показать первые 10 штук
        cursor.execute("SELECT car_id, title, year, price FROM cars LIMIT 10;")
        rows = cursor.fetchall()
        
        for row in rows:
            print(f"ID: {row[0]} | {row[1]} [{row[2]} г.] --- Цена: {row[3]}")
            
    except sqlite3.OperationalError as e:
        print(f"[ERROR] Ошибка чтения базы: {e}")
        print("Возможно, таблица еще не создана или файл пустой.")
        
    conn.close()
    print("======================================\n")

if __name__ == "__main__":
    view_database()
