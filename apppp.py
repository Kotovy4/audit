import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import locale
import os

# --- Налаштування сторінки (має бути першою командою Streamlit) ---
st.set_page_config(layout="wide", page_title="AUDIT Облік")

# --- Додаємо заголовок до бічної панелі (ПЕРЕМІЩЕНО СЮДИ) ---
st.sidebar.title("AUDIT") # <--- МАЄ БУТИ ТУТ, ОДРАЗУ ПІСЛЯ set_page_config

# --- Налаштування локалі ---
try:
    locale.setlocale(locale.LC_ALL, 'uk_UA.UTF-8')
except locale.Error:
    print("Українська локаль 'uk_UA.UTF-8' не доступна, спроба 'uk_UA'.")
    try:
        locale.setlocale(locale.LC_ALL, 'uk_UA')
    except locale.Error:
        print("Локаль 'uk_UA' також недоступна, використовується стандартне форматування.")
        def format_currency(value):
            if value is None: return "---"
            try: return f"{value:,.2f} ₴"
            except (ValueError, TypeError): return "Помилка"
else:
    def format_currency(value):
        if value is None: return "---"
        try: return locale.currency(value, symbol='₴', grouping=True)
        except (ValueError, TypeError): return "Помилка"

# --- Підключення до Supabase ---
@st.cache_resource
def init_supabase_client():
    """Ініціалізує та повертає клієнт Supabase."""
    try:
        SUPABASE_URL = st.secrets["supabase"]["url"]
        SUPABASE_KEY = st.secrets["supabase"]["key"]
        print("Спроба підключення до Supabase...")
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Підключення до Supabase успішне.")
        return client
    except Exception as e:
        print(f"Помилка підключення до Supabase: {e}")
        st.error(f"""
            **Не вдалося підключитися до бази даних Supabase.**
            Перевірте налаштування секретів Streamlit та дані проекту Supabase.
            Помилка: {e}
        """)
        return None

supabase = init_supabase_client() # Створюємо клієнт

# --- Спільні функції для роботи з даними ---

@st.cache_data(ttl=60)
def load_items_from_db(limit=None, offset=None, search_term=None):
    """
    Завантажує товари з Supabase з можливістю пагінації та пошуку,
    оптимізовано для уникнення N+1 запитів для історії продажів.
    Повертає список товарів для поточної сторінки та загальну кількість товарів, що відповідають критеріям.
    """
    if not supabase:
        return [], 0

    try:
        # 1. Завантажуємо основні дані товарів, вибираючи конкретні колонки
        # Колонки, необхідні для відображення та розрахунків
        item_columns_to_select = "id, name, initial_quantity, cost_uah, customs_uah, description, origin_country, original_currency, cost_original, shipping_original, rate, created_at"
        
        query = supabase.table('items').select(item_columns_to_select, count='exact')

        if search_term:
            query = query.ilike('name', f'%{search_term}%')
        
        # Загальна кількість записів (з урахуванням пошуку)
        # Цей запит виконується до застосування limit/offset для пагінації
        count_response = query.execute() # Виконуємо окремий запит для count, якщо це ефективніше
        total_count = count_response.count if count_response.count is not None else 0
        
        # Застосовуємо пагінацію для основного запиту
        if limit is not None and offset is not None:
            query = query.range(offset, offset + limit - 1)
        
        items_response = query.order('id').execute() # Сортуємо для консистентності
        items_data = items_response.data if items_response.data else []

        if not items_data:
            return [], total_count # Повертаємо 0, якщо після фільтрації/пагінації нічого немає

        # 2. Збираємо ID товарів для завантаження їх історії продажів
        item_ids = [item['id'] for item in items_data]

        # 3. Завантажуємо всю історію продажів для цих товарів ОДНИМ запитом
        sales_data_for_items = []
        if item_ids:
            # Вибираємо тільки потрібні колонки з sales
            sales_columns_to_select = "id, item_id, quantity_sold, price_per_unit_uah, sale_timestamp"
            sales_response = supabase.table('sales').select(sales_columns_to_select).in_('item_id', item_ids).order('sale_timestamp').execute()
            sales_data_for_items = sales_response.data if sales_response.data else []

        # 4. Розподіляємо історію продажів по товарах
        sales_by_item_id = {}
        for sale in sales_data_for_items:
            item_id = sale['item_id']
            if item_id not in sales_by_item_id:
                sales_by_item_id[item_id] = []
            sales_by_item_id[item_id].append(sale)

        # 5. Додаємо історію продажів до кожного товару
        for item in items_data:
            item['sales_history'] = sales_by_item_id.get(item['id'], [])

        print(f"Завантажено {len(items_data)} товарів (ліміт: {limit}, зсув: {offset}, пошук: '{search_term}'). Загалом знайдено: {total_count}. Завантажено історію продажів.")
        return items_data, total_count

    except Exception as e:
        st.error(f"Помилка завантаження товарів з БД: {e}")
        return [], 0

def load_sales_history_for_item(item_id):
    """Завантажує історію продажів для конкретного товару."""
    if not supabase:
        return []
    try:
        sales_columns_to_select = "id, item_id, quantity_sold, price_per_unit_uah, sale_timestamp"
        response = supabase.table('sales').select(sales_columns_to_select).eq('item_id', item_id).order('sale_timestamp').execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Помилка завантаження історії продажів для товару {item_id}: {e}")
        return []

@st.cache_data(ttl=300)
def get_item_by_db_id(db_id):
    """Ефективно завантажує ОДИН товар за його ID з бази даних, включаючи історію продажів."""
    if not supabase:
        return None
    try:
        item_columns_to_select = "id, name, initial_quantity, cost_uah, customs_uah, description, origin_country, original_currency, cost_original, shipping_original, rate, created_at"
        response = supabase.table('items').select(item_columns_to_select).eq('id', db_id).maybe_single().execute()
        if response.data:
            item = dict(response.data)
            item['sales_history'] = load_sales_history_for_item(item['id'])
            return item
        return None
    except Exception as e:
        st.error(f"Помилка завантаження товару ID {db_id} з БД: {e}")
        return None

def get_item_sales_info_cached(item_data):
    """Розраховує продану кількість та середню ціну, використовуючи кешовану історію."""
    sales_history = item_data.get('sales_history', [])
    total_sold_qty = 0
    total_sales_value = 0.0
    if not sales_history:
        return 0, 0.0

    for sale in sales_history:
        qty = sale.get('quantity_sold', 0)
        price = sale.get('price_per_unit_uah', 0.0)
        if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
             total_sold_qty += qty
             total_sales_value += qty * price
        else:
             print(f"Попередження: некоректні типи даних у записі продажу: qty={qty}, price={price}")

    average_sell_price = total_sales_value / total_sold_qty if total_sold_qty > 0 else 0.0
    return total_sold_qty, average_sell_price

def calculate_uah_cost(cost_original, shipping_original, rate):
    """Розраховує вартість в UAH на основі оригінальної вартості та курсу."""
    try:
        cost = float(cost_original or 0)
        shipping = float(shipping_original or 0)
        rate_val = float(rate or 0)
        if rate_val > 0:
            return (cost + shipping) * rate_val
        else:
            return 0.0
    except (ValueError, TypeError):
        return 0.0

CURRENCY_SETTINGS = {
    "USA": {"symbol": "$", "code": "USD", "default_rate": 42.0, "rate_label": "Курс $/грн*"},
    "Poland": {"symbol": "zł", "code": "PLN", "default_rate": 11.11, "rate_label": "Курс zł/грн*"},
    "England": {"symbol": "£", "code": "GBP", "default_rate": 55.0, "rate_label": "Курс £/грн*"}
}

# --- Ініціалізація стану додатку ---
if 'selected_item_id' not in st.session_state:
    st.session_state.selected_item_id = None
if 'editing_item_id' not in st.session_state:
    st.session_state.editing_item_id = None
if 'selling_item_id' not in st.session_state:
    st.session_state.selling_item_id = None
if 'viewing_history_item_id' not in st.session_state:
    st.session_state.viewing_history_item_id = None
if 'editing_sale_id' not in st.session_state:
    st.session_state.editing_sale_id = None
    st.session_state.editing_sale_item_id = None
if 'confirm_delete_id' not in st.session_state:
     st.session_state.confirm_delete_id = None
if 'confirm_delete_sale_id' not in st.session_state:
     st.session_state.confirm_delete_sale_id = None
     st.session_state.confirm_delete_sale_item_id = None
if 'current_page_view_items' not in st.session_state:
    st.session_state.current_page_view_items = 1


# --- Головна сторінка ---
st.title("📊 Програма обліку товарів")
st.write("Оберіть потрібний розділ на бічній панелі зліва.")
st.info("Це головна сторінка. Основний функціонал знаходиться в розділах бічного меню.")

