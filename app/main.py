#app/main.py

###
from streamlit_autorefresh import st_autorefresh
import streamlit as st
from lang import TEXTS
import pandas as pd
import subprocess
import sqlite3
import asyncio #?
import json
import time
import sys
import os

from filters import apply_car_filters
###

st.set_page_config(page_title="Finn.no Аналитика", layout="wide")
st.title("Панель мониторинга авторынка Норвегии")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "cars.db")

@st.fragment(run_every="15s")
def snow_data_tables():
    def load_actual_data():
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT car_id, title, year, mileage, fuel, transmission, price, updated_at, url FROM cars", conn)
        conn.close()
        return df

    def load_history_data():
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT
                h.car_id AS ID,
                c.title AS Модель,
                h.old_price AS Старая_цена,
                h.new_price AS Новая_цена,
                h.changed_at AS Дата_изменения,
                c.url AS Ссылка
            FROM price_history h
            LEFT JOIN cars c ON h.car_id = c.car_id
            ORDER BY h.changed_at DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
 
    df_actual = load_actual_data()
    df_history = load_history_data()

    tab1, tab2, tab3 = st.tabs([
        "Актуальные объявления",
        "История цен",
        "Аналитика рынка"
    ])

### #1
    with tab1:
        st.subheader("Фильтры поиска")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            all_transmissions = ["Все"] + [t for t in df_actual['transmission'].unique() if t != "Не указано"]
            selected_trans = st.selectbox("Кoробка передач:", all_transmissions)
        with col2:
            all_fuels = ["Все"] + [f for f in df_actual['fuel'].unique() if f != "Не указано"]
            selected_fuel = st.selectbox("Тип топлива:", all_fuels)
        with col3:
            search_query = st.text_input("Поиск:", "")
        with col4:
            sort_mode = st.selectbox("Сортировка цен:", ["Без сортировки", "Цена: Сначала дешевые", "Цена: Сначала дорогие"])

        st.markdown("---")
        slider_col1, slider_col2 = st.columns(2)

        with slider_col1:
            min_years_val = int(df_actual['year'].min()) if not df_actual.empty else 1990
            max_years_val = int(df_actual['year'].max()) if not df_actual.empty else 2026
            selected_years = st.slider("Фильтр по годам выпуска:", min_value=min_years_val, max_value=max_years_val, value=(min_years_val, max_years_val))
        with slider_col2:
            max_mileage_input = st.slider("Максимальный пробег(км):", min_value=0, max_value=500000, value=500000, step=5000)

        df_display = apply_car_filters(
            df_actual, selected_trans, selected_fuel, search_query, sort_mode,
            min_year=selected_years[0],
            max_year=selected_years[1],
            max_mileage=max_mileage_input,
            geo_query="Все"
        )

        st.metric(label="Найдено машин по фильтрам", value=len(df_display))
        st.dataframe(
            df_display, 
            width="stretch",
            column_config={
                "url": st.column_config.LinkColumn("Объявление на Finn.no", display_text="Открыть")
            }
        )

### #2
    with tab2:
        st.subheader("Лог изменения цен на машины")
        if len(df_history) == 0:
            st.info("История изменения цен пока пуста...")
        else:
            st.dataframe(
            df_history,
            width="stretch",
            column_config={"Ссылка": st.column_config.LinkColumn("Объявление на Finn.no", display_text="Открыть")}
            )

### #3
    with tab3:
        st.subheader("Топ-15 популярных марок на рынке")
        if len(df_actual) > 0:
            df_actual['brand'] = df_actual['title'].apply(lambda x: x.split()[0] if len(x.split()) > 0 else "Unknown")

            brand_counts = df_actual['brand'].value_counts().head(15)

            m1, m2, m3 = st.columns(3)
            m1.metric("Всего авто в базе", len(df_actual))
            m2.metric("Уникальных марок", df_actual['brand'].nunique())
            m3.metric("Лидер рынка", f"{brand_counts.index[0]} ({brand_counts.iloc[0]} шт.)")

            st.markdown("---")

            chart_col, table_col = st.columns([2, 1])

            with chart_col:
                st.write("**Распределение по количеству объявлений**")
                st.bar_chart(brand_counts, horizontal=True)

            with table_col:
                st.write("**Доля рынка (%)**")
                df_brands = pd.DataFrame({
                    "Марка": brand_counts.index,
                    "Кол-во": brand_counts.values,
                    "Доля (%)": ((brand_counts.values / len(df_actual)) * 100).round(1)
                })
                st.dataframe(df_brands, hide_index=True, width="stretch")

snow_data_tables()

st.markdown("---")
st.subheader("Настройки и управление")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def ensure_auto_runner_alive():
    """Проверяет, запущен ли auto_runner.py в системе. Если нет — запускает его в фоне."""
    try:
        output = subprocess.check_output(["pgrep", "-f", "auto_runner.py"], text=True)
    except subprocess.CalledProcessError:

        runner_path = os.path.join(BASE_DIR, "auto_runner.py")
        subprocess.Popen(
            [sys.executable, runner_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  
        )

ensure_auto_runner_alive()

saved_mode = "Ручной запуск"
saved_interval = 5
saved_pages = 3

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            current_cfg = json.load(f)
            if current_cfg.get("mode") == "auto":
                saved_mode = "Автоматический"
            saved_interval = current_cfg.get("interval_minutes", 5)
            saved_pages = current_cfg.get ("max_pages", 3) 
    except Exception:
        pass

default_index = 1 if saved_mode == "Автоматический" else 0
mode = st.radio("Режим работы парсера:", ["Ручной запуск", "Автоматический"], index=default_index)

#4
if mode == "Автоматический":
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=1000, key="timer_pulse")
    except Exception:
        pass

    current_status = "sleeping"
    time_left = 0
    current_progress = 0

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            current_status = cfg.get("status", "sleeping")
            time_left = cfg.get("time_left_seconds", 0)
            current_progress = cfg.get("progress", 0)
    except Exception:
        pass

    if current_status == "running":
        st.warning(f"Скачано: {current_progress}%")
        st.progress(current_progress / 100.0)
    else:
        mins, secs = divmod(time_left, 60)
        st.success(f"Статус: Планировщик активен. До следующего сбора осталось: **{mins:02d} мин {secs:02d} сек**")

    interval = st.slider(f"Интервал обновления (в минутах)", min_value=1, max_value=60, value=saved_interval, step=1)
    pages_to_scrape = st.slider("Глубина парсинга (сколько страниц собирать?):", min_value=1, max_value=20, value=saved_pages, step=1)

    btn_col1, btn_col2 = st.columns(2)

###

    with btn_col1:
        if st.button("Принять изменения", type="secondary", use_container_width=True):
            config_data = {
                "mode": "auto",
                "interval_minutes": interval,
                "max_pages": pages_to_scrape,
                "status": "sleeping",
                "time_left_seconds": interval * 60,
                "progress": 0
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            st.success(f"Настройки сохранены, интервал {interval} мин.")
            time.sleep(1.5)
            st.rerun()

###

    with btn_col2:
        if st.button("Остановить авто-парсинг", type="primary"):
            config_data = {
                "mode": "manual",
                "interval_minutes": saved_interval,
                "max_pages": saved_pages,
                "status": "sleeping",
                "time_left_seconds": 0,
                "progress": 0
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            st.error("Автоматический режим выключен")
            time.sleep(1.5)
            st.rerun()
#4.1 
else:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("mode") != "manual":
                cfg["mode"] = "manual"
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    st.write("В ручном режиме вы можете запуск сбор данных в реальном времени")

    if st.button("Запустить сбор данных с Finn.no", type="primary", use_container_width=True):
            with st.spinner("Эй, бро, я запустил Playwright который... Короче, подожди чутка..."):
                try:
                    run_script_path = os.path.join(BASE_DIR, "run.py")
                    result = subprocess.run(
                        ["python3", run_script_path],
                        capture_output=True,
                        text=True,
                        check=True
                )
                    st.success("Готово. Cтраница сама обновиться)")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Что-то пошло не так при парсинге. Возможно я налажал где-то): {e}")


