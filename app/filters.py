# finn_project/app/filters.py

###
import pandas as pd
import re
###

def apply_car_filters(df, selected_trans, selected_fuel, search_query, sort_mode, min_year, max_year, max_mileage, geo_query):
    """
    Функции фильтрации и сортировки.
    """
    if df.empty:
        return df

    df_filtered = df.copy()

    df_filtered = df_filtered[df_filtered['price'] != 'Цена не указана']
    df_filtered = df_filtered[df_filtered['transmission'] != 'Не указано']
    df_filtered = df_filtered[df_filtered['fuel'] != 'Не указано']
    df_filtered = df_filtered[df_filtered['mileage'] != 'Пробег не указан']

    # 1. КПП
    if selected_trans != "Все":
        df_filtered = df_filtered[df_filtered['transmission'] == selected_trans]

    # 2. Топливо
    if selected_fuel != "Все":
        df_filtered = df_filtered[df_filtered['fuel'] == selected_fuel]

    # 3. Названию/модели
    if search_query:
        df_filtered = df_filtered[df_filtered['title'].str.contains(search_query, case=False, na=False)]
    #4
    df_filtered = df_filtered[(df_filtered['year'] >= min_year) & (df_filtered['year'] <= max_year)]
    #5
    def clean_mileage(x):
        if pd.isna(x) or not isinstance(x, str):
            return 0
        nums = re.sub(r'\n|\s+|km', '', x)
        return int(nums) if nums.isdigit() else 0

    df_filtered['mileage_numeric'] = df_filtered['mileage'].apply(clean_mileage)
    df_filtered = df_filtered[df_filtered['mileage_numeric'] <= max_mileage]

    #6
    df_filtered['price_numeric'] = df_filtered['price'].str.replace('kr', '', regex=False)
    df_filtered['price_numeric'] = df_filtered['price_numeric'].str.replace(r'\s+', '', regex=True)
    df_filtered['price_numeric'] = pd.to_numeric(df_filtered['price_numeric'], errors='coerce').fillna(0).astype(int)

    #7 
    if sort_mode == "Цена: Сначала дешевые":
        df_filtered = df_filtered.sort_values(by='price_numeric', ascending=True)
    elif sort_mode == "Цена: Сначала дорогие":
        df_filtered = df_filtered.sort_values(by='price_numeric', ascending=False)

#    #8 гео. в разработке...
#    if geo_query and geo_query != "Все" and 'location' in df_filtered.columns:
#        df_filtered = df_filtered[df_filtered['location'] == geo_query]

###

    df_display = df_filtered.drop(columns=['price_numeric', 'mileage_numeric'])

    return df_display


