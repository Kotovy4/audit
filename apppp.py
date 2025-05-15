import streamlit as st
# from supabase import create_client, Client # Більше не потрібен прямий клієнт тут
from datetime import datetime
import locale
import os
import requests # Для HTTP-запитів
import math # Потрібен для math.ceil у сторінці перегляду

# --- Налаштування сторінки (має бути першою командою Streamlit) ---
st.set_page_config(layout="wide", page_title="AUDIT Облік")

# --- Додаємо заголовок до бічної панелі ---
st.sidebar.title("AUDIT")

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

# --- Налаштування API ---
# Для локального тестування FastAPI має бути запущений на цьому порту
# У майбутньому це буде URL вашого розгорнутого FastAPI-сервісу
API_BASE_URL = "http://127.0.0.1:8000"

# --- Спільні функції для роботи з даними через API ---

@st.cache_data(ttl=60)
def load_items_from_api(limit=None, offset=None, search_term=None):
    """
    Завантажує товари з FastAPI з пагінацією та пошуком.
    Повертає список товарів та загальну кількість (якщо API це підтримує).
    """
    endpoint = f"{API_BASE_URL}/products/"
    params = {}
    if limit is not None:
        params['limit'] = limit
    if offset is not None:
        params['skip'] = offset # FastAPI використовує 'skip'
    if search_term:
        params['search'] = search_term

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status() # Генерує помилку для кодів 4xx/5xx
        data = response.json()
        
        # Припускаємо, що FastAPI повертає список товарів.
        # Якщо FastAPI повертає також загальну кількість, потрібно буде її обробити.
        # Наразі, для простоти, припустимо, що total_count ми не отримуємо від цього ендпоінту,
        # або він повертає тільки поточну сторінку.
        # Для коректної пагінації нам потрібен total_count.
        # Поки що повернемо довжину отриманого списку як total_count для цієї сторінки.
        # Це потрібно буде вдосконалити на боці FastAPI.
        items_data = data if isinstance(data, list) else []
        
        # ТИМЧАСОВО: Оскільки FastAPI /products/ ще не повертає sales_history,
        # ми ініціалізуємо його порожнім списком.
        # Це означає, що розрахунки середньої ціни продажу в таблиці будуть нульовими.
        for item in items_data:
            if 'sales_history' not in item:
                item['sales_history'] = [] # Потрібно для get_item_sales_info_cached

        # TODO: FastAPI /products/ має повертати загальну кількість елементів для коректної пагінації
        # Поки що, якщо limit є, припускаємо, що total_count може бути більшим.
        # Це не ідеально, але дозволить UI пагінації працювати.
        # Краще, щоб FastAPI повертав total_count.
        # Для простоти, якщо search_term є, ми не можемо знати total_count без окремого запиту.
        if search_term:
            # Якщо є пошук, ми не знаємо загальну кількість без окремого запиту до API
            # Можна зробити ще один запит до API /products/count?search=... або подібного
            # Поки що, для простоти, якщо є пошук, total_count буде довжиною поточного результату
            total_count_for_pagination = len(items_data) if limit is None else (offset + len(items_data) + (ITEMS_PER_PAGE if len(items_data) == ITEMS_PER_PAGE else 0) )

        elif limit is not None:
            # Якщо це не остання сторінка, припускаємо, що є ще
            total_count_for_pagination = offset + len(items_data) + (ITEMS_PER_PAGE if len(items_data) == ITEMS_PER_PAGE else 0)
        else:
            total_count_for_pagination = len(items_data)


        print(f"API: Завантажено {len(items_data)} товарів (ліміт: {limit}, зсув: {offset}, пошук: '{search_term}'). Приблизна заг. кількість: {total_count_for_pagination}")
        return items_data, total_count_for_pagination # Повертаємо список та "загальну кількість"

    except requests.exceptions.RequestException as e:
        st.error(f"Помилка з'єднання з API при завантаженні товарів: {e}")
        return [], 0
    except Exception as e:
        st.error(f"Помилка обробки даних з API: {e}")
        return [], 0


@st.cache_data(ttl=300)
def get_item_by_db_id(db_id): # Назва функції залишається, але логіка змінюється
    """Завантажує ОДИН товар за його ID через FastAPI."""
    if db_id is None:
        return None
    endpoint = f"{API_BASE_URL}/items/{db_id}"
    try:
        response = requests.get(endpoint)
        response.raise_for_status()
        item_data = response.json()
        # TODO: FastAPI /items/{id} має повертати sales_history
        if item_data and 'sales_history' not in item_data:
            # Якщо FastAPI не повертає історію, ми можемо її завантажити окремо
            # або залишити порожньою, якщо це обробляється далі
            item_data['sales_history'] = [] # Тимчасово
            # item_data['sales_history'] = load_sales_history_for_item_api(db_id) # Потрібен новий ендпоінт
        return item_data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Товар з ID {db_id} не знайдено через API.")
            return None
        st.error(f"HTTP помилка при завантаженні товару ID {db_id}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Помилка з'єднання з API при завантаженні товару ID {db_id}: {e}")
        return None
    except Exception as e:
        st.error(f"Помилка обробки даних товару ID {db_id} з API: {e}")
        return None


def get_item_sales_info_cached(item_data):
    """Розраховує продану кількість та середню ціну, використовуючи кешовану історію."""
    # Ця функція залишається такою ж, але тепер вона залежить від того,
    # чи заповнено 'sales_history' у item_data.
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
        cost = float(cost_original or 0.0)
        shipping = float(shipping_original or 0.0)
        rate_val = float(rate or 0.0)
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
# Перевіряємо, чи є підключення до API (можна зробити тестовий запит)
try:
    # Простий тестовий запит до кореневого ендпоінту FastAPI
    test_response = requests.get(API_BASE_URL, timeout=2)
    if test_response.status_code == 200:
        st.info("Це головна сторінка. Основний функціонал знаходиться в розділах бічного меню. API доступний.")
    else:
        st.warning(f"API на {API_BASE_URL} відповів зі статусом {test_response.status_code}. Перевірте, чи запущено FastAPI сервер.")
except requests.exceptions.ConnectionError:
    st.error(f"Не вдалося підключитися до API за адресою: {API_BASE_URL}. Переконайтеся, що ваш FastAPI сервер запущено локально.")
except Exception as e:
    st.error(f"Невідома помилка при спробі з'єднання з API: {e}")

