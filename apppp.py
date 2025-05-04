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
        # Функція для простого форматування, якщо локаль недоступна
        def format_currency(value):
            if value is None: return "---"
            try: return f"{value:,.2f} ₴"
            except (ValueError, TypeError): return "Помилка"
else:
    # Функція форматування з використанням locale
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
def load_items_from_db():
    """Завантажує товари з Supabase та їх історію продажів."""
    if not supabase:
        # st.error("Немає підключення до Supabase для завантаження товарів.")
        return []
    try:
        response = supabase.table('items').select('*').order('id').execute()
        if response.data:
            items_with_history = []
            for item in response.data:
                 item['sales_history'] = load_sales_history_for_item(item['id'])
                 items_with_history.append(item)
            print(f"Завантажено {len(items_with_history)} товарів з історією.")
            return items_with_history
        else:
            print("База даних товарів порожня.")
            return []
    except Exception as e:
        st.error(f"Помилка завантаження товарів з БД: {e}")
        return []

def load_sales_history_for_item(item_id):
    """Завантажує історію продажів для конкретного товару."""
    if not supabase:
        return []
    try:
        response = supabase.table('sales').select('*').eq('item_id', item_id).order('sale_timestamp').execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Помилка завантаження історії продажів для товару {item_id}: {e}")
        return []

def get_item_by_db_id(db_id):
    """Знаходить словник товару в кеші inventory_list за його ID з бази даних."""
    items = load_items_from_db()
    for item in items:
        if item.get('id') == db_id:
            return item
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

def calculate_uah_cost(cost_usd, shipping_usd, rate):
    """Розраховує вартість в UAH."""
    try:
        cost = float(cost_usd or 0)
        shipping = float(shipping_usd or 0)
        rate_val = float(rate or 0)
        if rate_val > 0:
            return (cost + shipping) * rate_val
        else:
            return 0.0
    except (ValueError, TypeError):
        return 0.0

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
# Видаляємо непотрібні стани, пов'язані зі старим способом навігації
# (Залишаємо цей код на випадок, якщо старі стани ще існують)
if 'current_view' in st.session_state:
     del st.session_state['current_view']
if 'show_statistics' in st.session_state:
     del st.session_state['show_statistics']
if 'stats_selected_item_id' in st.session_state:
     del st.session_state['stats_selected_item_id']


# --- Головна сторінка ---
# Цей код виконається тільки якщо не вибрано жодної сторінки в pages
# Або якщо користувач перейде на головну сторінку (якщо вона є)
st.title("📊 Програма обліку товарів")
st.write("Оберіть потрібний розділ на бічній панелі зліва.")
st.info("Це головна сторінка. Основний функціонал знаходиться в розділах бічного меню.")

# --- Додатково: кнопка для очищення кешу (для відладки) ---
# st.sidebar.button("Очистити кеш даних", on_click=st.cache_data.clear)
