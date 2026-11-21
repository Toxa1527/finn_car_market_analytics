# finn_project/app/main.py

###
from streamlit_autorefresh import st_autorefresh
import streamlit as st
import pandas as pd
import subprocess
import sqlite3
import asyncio #?
import signal
import json
import time
import sys
import os

from filters import apply_car_filters
from notifier.tg_bot import load_tg_config, save_tg_config, send_telegram_message
###

def save_config(data):
    tmp = f"{CONFIG_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)

def is_scraper_running():
    res = subprocess.run(["pgrep", "-f", "run.py"], capture_output=True)
    return res.returncode == 0

st.set_page_config(page_title="Finn.no Аналитика", layout="wide")
st.title("Панель мониторинга авторынка Норвегии")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "cars.db")

@st.fragment(run_every="15s")
def snow_data_tables():
    def load_actual_data():
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT car_id, title, year, mileage, fuel, transmission, price, location,  url, updated_at FROM cars", conn)
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

    #1
    with tab1:
        st.subheader("Фильтры поиска")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            all_transmissions = ["Все"] + sorted([t for t in df_actual['transmission'].dropna().unique() if t != "Не указано"])
            selected_trans = st.selectbox("Кoробка передач:", all_transmissions)
        with col2:
            all_fuels = ["Все"] + sorted([f for f in df_actual['fuel'].dropna().unique() if f != "Не указано"])
            selected_fuel = st.selectbox("Тип топлива:", all_fuels)
        with col3:
            search_query = st.text_input("Поиск:", "")
        with col4:
            sort_mode = st.selectbox("Сортировка цен:", ["Без сортировки", "Цена: Сначала дешевые", "Цена: Сначала дорогие"])

        with col5:
            if 'location' in df_actual.columns and not df_actual.empty:
                geo_options = ["Все"] + sorted([loc for loc in df_actual['location'].dropna().unique() if loc and loc != "Не указано"])
            else:
                geo_options = ["Все"]
            selected_geo = st.selectbox("Регион / Город:", geo_options)

        st.markdown("---")
        slider_col1, slider_col2 = st.columns(2)

        with slider_col1:
            min_years_val = int(df_actual['year'].min()) if not df_actual.empty else 1990
            max_years_val = int(df_actual['year'].max()) if not df_actual.empty else 2026
            selected_years = st.slider("Фильтр по годам выпуска:", min_value=min_years_val, max_value=max_years_val, value=(min_years_val, max_years_val))
        with slider_col2:
            max_mileage_input = st.slider("Максимальный пробег(км):", min_value=0, max_value=500000, value=500000, step=5000)

        price_col1, price_col2 = st.columns(2)
        with price_col1:
            min_price_input = st.number_input("Цена от (kr):", min_value=0, value=0, step=5000)
        with price_col2:
            max_price_input = st.number_input("Цена до (kr):", min_value=0, value=0, step=5000)

        df_display = apply_car_filters(
            df_actual, selected_trans, selected_fuel, search_query, sort_mode,
            min_year=selected_years[0],
            max_year=selected_years[1],
            max_mileage=max_mileage_input,
            geo_query=selected_geo,
            min_price=min_price_input,
            max_price=max_price_input
        )

    #

        tg_col1, tg_col2 = st.columns([3, 1])
        with tg_col2:
            if st.button(" Отслеживать поиск в TG", use_container_width=True, key="btn_track_tg"):
                tg_cfg = load_tg_config()
                tg_cfg["filters"] = {
                    "transmission": selected_trans,
                    "fuel": selected_fuel,
                    "search": search_query,
                    "geo": selected_geo,
                    "min_year": selected_years[0],
                    "max_year": selected_years[1],
                    "max_mileage": max_mileage_input,
                    "min_price": min_price_input,
                    "max_price": max_price_input
                }
                save_tg_config(tg_cfg)
                st.toast("Фильтры для Telegram-уведомлений обновлены!", icon="")

                token = tg_cfg.get("bot_token", "")
                chat_id = tg_cfg.get("chat_id", "")
                if token and chat_id:
                    confirm_msg = (
                        "Отслеживание поиска обновлено\n\n"
                        f"Поиск: {search_query or 'Все авто'}\n"
                        f"Цена: от {min_price_input:,} до {max_price_input:,} kr\n"#.replace(",", " ")
                        f"Город: {selected_geo}\n"
                        f"КПП: {selected_trans} | Топливо: {selected_fuel}\n"
                        f"Года: {selected_years[0]} - {selected_years[1]}\n"
                        f"Пробег до: {max_mileage_input:,} km".replace(",", " ")
                    )
                    send_telegram_message(token, chat_id, confirm_msg)

    #

        df_display = df_display[
            (df_display["location"] != "Не указано") &
            (df_display["transmission"] != "Не указано") &
            (df_display["fuel"] != "Не указано")
        ]

    #

        st.metric(label="Найдено машин по фильтрам", value=len(df_display))
        st.dataframe(
            df_display,
            width="stretch",
            column_order=("car_id", "title", "year", "mileage", "fuel", "transmission", "price", "location", "updated_at", "url"),
            column_config={
                    "url": st.column_config.LinkColumn("Объявление на Finn.no", display_text="Открыть")
            }
        )

    #2

    with tab2:
        st.subheader("Лог изменения цен на машины")
        if len(df_history) == 0:
            st.info("История изменения цен пока пуста...")
        else:
            st.dataframe(
                df_history, 
                width="stretch",
                column_config={
                    "Ссылка": st.column_config.LinkColumn("Объявление на Finn.no", display_text="Открыть")
                }
            )

    #3

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

default_idx = 1 if saved_mode == "auto" else 0
mode = st.radio("Режим работы парсера:", ["Ручной запуск", "Автоматический"], index=default_idx)

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

#

    scraper_active = is_scraper_running()

    with btn_col1:
        if st.button(
            "Принять изменения",
            type="primary",
            use_container_width=True,
            disabled=scraper_active,
            key="btn_apply_auto"
        ):
            config_data = {
                "mode": "auto",
                "interval_minutes": interval,
                "max_pages": pages_to_scrape,
                "status": "sleeping",
                "time_left_seconds": interval * 60,
                "progress": 0
            }
            save_config(config_data)

            runner_path = os.path.join(BASE_DIR, "auto_runner.py")
            check_proc = subprocess.run(["pgrep", "-f", runner_path], capture_output=True)
            if check_proc.returncode != 0:
                subprocess.Popen(
                    [sys.executable, runner_path],
                    cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )

            st.success(f"Настройки сохранены, интервал {interval} мин.")
            time.sleep(1.5)
            st.rerun()

    with btn_col2:
        if st.button("Остановить авто-парсинг", type="primary", use_container_width=True, key="btn_stop_auto"):
            config_data = {
                "mode": "manual",
                "interval_minutes": saved_interval,
                "max_pages": saved_pages,
                "status": "sleeping",
                "time_left_seconds": 0,
                "progress": 0
            }
            save_config(config_data)

            subprocess.run(["pkill", "-9", "-f", "auto_runner.py"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "run.py"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "finn_profile"], capture_output=True)
            if os.path.exists(os.path.join(BASE_DIR, "runner.pid")):
                os.remove(os.path.join(BASE_DIR, "runner.pid"))

            st.error("Автоматический режим полностью остановлен")
            time.sleep(1.5)
            st.rerun()

#

else:
    current_progress = 0
    file_running = False

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    current_progress = cfg.get("progress", 0)

    scraper_active = is_scraper_running() or file_running

    if scraper_active:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=1000, key="manual_pulse")
        except Exception:
            pass
        st.warning(f"Скачано: {current_progress}%")
        st.progress(current_progress / 100.0)
    else:
        st.write("В ручном режиме вы можете запустить сбор данных в реальном времени")

    manual_pages = st.slider(
        "Глубина парсинга (сколько страниц собирать?):",
        min_value=1,
        max_value=20,
        value=saved_pages,
        step=1,
        disabled=scraper_active,
        key="manual_pages_slider"
    )

    m_col1, m_col2 = st.columns(2)

    with m_col1:
        if st.button(
            "Запустить сбор данных с Finn.no",
            type="primary",
            use_container_width=True,
            disabled=scraper_active,
            key="btn_manual_start"
        ):
            cfg_start = {
                "mode": "manual",
                "interval_minutes": saved_interval,
                "max_pages": manual_pages,
                "status": "running",
                "time_left_seconds": 0,
                "progress": 0,
            }
            save_config(cfg_start)

            run_script_path = os.path.join(BASE_DIR, "run.py")
            subprocess.Popen(
                [sys.executable, run_script_path],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            st.rerun()

    with m_col2:
        if st.button(
            "Остановить сбор",
            type="primary",
            use_container_width=True,
            disabled=not scraper_active,
            key="btn_manual_stop"
        ):
            subprocess.run(["pkill", "-9", "-f", "run.py"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "finn_profile"], capture_output=True)

            cfg_stop = {
                "mode": "manual",
                "interval_minutes": saved_interval,
                "max_pages": manual_pages,
                "status": "sleeping",
                "time_left_seconds": 0,
                "progress": 0,
            }
            save_config(cfg_stop)

            st.error("Сбор данных остановлен")
            time.sleep(1)
            st.rerun()

#

st.markdown("---")
st.subheader("Уведомления в Telegram")

tg_cfg = load_tg_config() or {}

tg_enabled = st.toggle(
    "Включить уведомления о новых авто и снижении цен",
    value=tg_cfg.get("enabled", False),
    key="tg_enabled_toggle"
)

tg_col1, tg_col2 = st.columns(2)
with tg_col1:
    tg_token = st.text_input(
        "Bot Token (от @BotFather):",
        value=tg_cfg.get("bot_token", ""),
        type="password",
        key="tg_token_input"
    )
with tg_col2:
    tg_chat_id = st.text_input(
        "Chat ID (от @userinfobot):",
        value=tg_cfg.get("chat_id", ""),
        key="tg_chat_id_input"
    )

#

saved_f = tg_cfg.get("filters", {})
if saved_f:
    st.caption(
        f"Активный фильтр отслеживания: **{saved_f.get('search') or 'Все марки'}** | "
        f"КПП: **{saved_f.get('transmission', 'Все')}** | "
        f"Топливо: **{saved_f.get('fuel', 'Все')}** | "
        f"Город: **{saved_f.get('geo', 'Все')}** | "
        f"Года: **{saved_f.get('min_year', '—')}–{saved_f.get('max_year', '—')}**"
        f"Цена: **{saved_f.get('min_price', 0)}–{saved_f.get('max_price') or '∞'} kr**"
    )
else:
    st.caption("Активный фильтр отслеживания: **Все новые машины без ограничений** (можно настроить во вкладке «Актуальные авто» кнопкой).")

tg_btn1, tg_btn2 = st.columns(2)
with tg_btn1:
    if st.button("Сохранить настройки Telegram", type="primary", use_container_width=True, key="btn_save_tg"):
        tg_cfg["enabled"] = tg_enabled
        tg_cfg["bot_token"] = tg_token.strip()
        tg_cfg["chat_id"] = tg_chat_id.strip()
        save_tg_config(tg_cfg)
        st.success("Настройки Telegram сохранены!")

with tg_btn2:
    if st.button("Отправить тестовое сообщение", use_container_width=True, key="btn_test_tg"):
        if not tg_token.strip() or not tg_chat_id.strip():
            st.error("Сначала введи Bot Token и Chat ID!")
        else:
            ok = send_telegram_message(
                tg_token.strip(),
                tg_chat_id.strip(),
                "Связь установлена!\nПарсер FINN.no успешно подключен к твоему Telegram."
            )
            if ok:
                st.success("Тестовое сообщение отправлено! Проверь Telegram.")
            else:
                st.error("Ошибка отправки. Проверь токен, Chat ID и нажат ли /start в боте.")
