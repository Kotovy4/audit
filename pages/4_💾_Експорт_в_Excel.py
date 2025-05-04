import streamlit as st
import pandas as pd
import io
# Імпортуємо спільні функції та клієнт supabase з основного файлу
try:
    from apppp import (
        supabase,
        load_items_from_db,
        get_item_sales_info_cached,
        format_currency # Може знадобитись для форматування, але краще експортувати числа
    )
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py' або необхідні функції.")
    st.stop()

# --- Функція для конвертації DataFrame в Excel ---
# (Дублюємо її тут або імпортуємо з apppp.py, якщо винести її туди)
def dataframe_to_excel(df):
    """Конвертує Pandas DataFrame у байтовий потік Excel-файлу."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventory Export')
    processed_data = output.getvalue()
    return processed_data

# --- Головна логіка сторінки експорту ---
st.header("💾 Експорт даних в Excel")

st.write("Виберіть колонки, які ви хочете включити до файлу експорту.")

# Завантажуємо всі дані
items_data = load_items_from_db()

if not items_data:
    st.warning("Немає даних для експорту.")
else:
    # Визначаємо всі можливі колонки для експорту
    # Ключі - як у словнику item, Значення - як хочемо бачити в multiselect
    all_export_columns = {
        "id": "ID",
        "name": "Назва",
        "initial_quantity": "Початкова к-сть",
        "remaining_qty": "Залишок", # Розрахункове поле
        "sold_qty": "Продано к-сть", # Розрахункове поле
        "cost_usd": "Вартість ($)",
        "shipping_usd": "Доставка ($)",
        "rate": "Курс $/грн",
        "cost_uah": "Вартість (грн)",
        "customs_uah": "Мито (грн)",
        "total_expenses_per_item": "Загальні витрати (грн/запис)", # Розрахункове поле
        "avg_sell_price": "Сер. ціна продажу (грн/од.)", # Розрахункове поле
        "total_income_per_item": "Загальний дохід (грн/запис)", # Розрахункове поле
        "profit_loss_per_item": "Прибуток/Збиток (грн/запис)", # Розрахункове поле
        "description": "Опис",
        "created_at": "Дата створення запису" # З Supabase
        # Додайте інші поля з таблиці items, якщо потрібно
    }

    # Список назв колонок для multiselect
    column_options = list(all_export_columns.values())
    # Вибираємо колонки за замовчуванням
    default_export_columns = ["ID", "Назва", "Залишок", "Вартість (грн)", "Мито (грн)", "Сер. ціна продажу (грн/од.)", "Загальний дохід (грн/запис)", "Прибуток/Збиток (грн/запис)"]

    selected_column_names = st.multiselect(
        "Виберіть колонки для експорту:",
        options=column_options,
        default=default_export_columns,
        key="export_column_selector"
    )

    if not selected_column_names:
        st.warning("Будь ласка, виберіть хоча б одну колонку для експорту.")
    else:
        # Готуємо дані для експорту
        export_data = []
        for item in items_data:
            sold_qty, avg_price = get_item_sales_info_cached(item)
            initial_qty = item.get('initial_quantity', 0)
            remaining_qty = initial_qty - sold_qty
            cost_uah = item.get('cost_uah', 0.0)
            customs_uah = item.get('customs_uah', 0.0)
            total_expenses = (cost_uah if cost_uah else 0.0) + (customs_uah if customs_uah else 0.0)
            total_income = sold_qty * avg_price
            unit_cost = total_expenses / initial_qty if initial_qty > 0 else 0
            profit_loss = total_income - (sold_qty * unit_cost) if sold_qty > 0 else 0.0 # Прибуток з проданих

            item_export_data = {
                "id": item.get('id'),
                "name": item.get('name', ''),
                "initial_quantity": initial_qty,
                "remaining_qty": remaining_qty,
                "sold_qty": sold_qty,
                "cost_usd": item.get('cost_usd'),
                "shipping_usd": item.get('shipping_usd'),
                "rate": item.get('rate'),
                "cost_uah": cost_uah,
                "customs_uah": customs_uah,
                "total_expenses_per_item": total_expenses,
                "avg_sell_price": avg_price if sold_qty > 0 else None, # None якщо не продано
                "total_income_per_item": total_income,
                "profit_loss_per_item": profit_loss if sold_qty > 0 else None, # None якщо не продано
                "description": item.get('description', ''),
                "created_at": item.get('created_at')
            }
            export_data.append(item_export_data)

        # Створюємо DataFrame з усіма підготовленими даними
        df_export_full = pd.DataFrame(export_data)

        # Вибираємо тільки ті колонки, які обрав користувач
        # Спочатку знаходимо відповідні ключі словника за вибраними назвами
        selected_keys = [key for key, value in all_export_columns.items() if value in selected_column_names]

        # Переконуємося, що вибрані ключі існують як колонки у DataFrame
        valid_export_keys = [key for key in selected_keys if key in df_export_full.columns]

        if valid_export_keys:
            df_export_selected = df_export_full[valid_export_keys]
            # Перейменовуємо колонки у DataFrame відповідно до вибраних назв
            df_export_selected.columns = [all_export_columns[key] for key in valid_export_keys]

            # Генеруємо Excel файл
            excel_bytes = dataframe_to_excel(df_export_selected)

            st.download_button(
                label="📥 Завантажити вибрані дані в Excel",
                data=excel_bytes,
                file_name='inventory_selected_export.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key='export_selected_button'
            )
        else:
            st.warning("Не вдалося сформувати дані для експорту з вибраними колонками.")

