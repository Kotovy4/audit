import streamlit as st
import pandas as pd
from supabase import create_client, Client # Бібліотека для роботи з Supabase
from datetime import datetime
import locale
import os # Для роботи з секретами
# import sqlite3 # Видаляємо, якщо використовуємо тільки Supabase

# --- Налаштування локалі для відображення гривні ---
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
supabase: Client | None = None # Ініціалізуємо як None
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Успішно підключено до Supabase.")
except Exception as e:
    print(f"Помилка підключення до Supabase: {e}")
    st.error(f"""
        **Не вдалося підключитися до бази даних Supabase.**

        Будь ласка, перевірте наступне:
        1.  Чи правильно налаштовані секрети Streamlit (`secrets.toml` локально або в налаштуваннях Streamlit Cloud)?
        2.  Чи вірні `url` та `key` вашого проекту Supabase?
        3.  Чи є доступ до мережі Інтернет?

        Приклад файлу `.streamlit/secrets.toml`:
        ```toml
        [supabase]
        url = "YOUR_SUPABASE_URL"
        key = "YOUR_SUPABASE_ANON_KEY"
        ```
        Замініть `YOUR_SUPABASE_URL` та `YOUR_SUPABASE_ANON_KEY` на ваші реальні дані з налаштувань проекту Supabase (Project Settings -> API).
    """)

# --- Функції для роботи з даними (через Supabase) ---

@st.cache_data(ttl=60) # Кешуємо дані на 60 секунд
def load_items_from_db():
    """Завантажує товари з Supabase та їх історію продажів."""
    if not supabase:
        st.error("Немає підключення до Supabase для завантаження товарів.")
        return []
    try:
        response = supabase.table('items').select('*').order('id').execute()
        if response.data:
            items_with_history = []
            for item in response.data:
                 # Завантажуємо історію для кожного товару
                 item['sales_history'] = load_sales_history_for_item(item['id'])
                 items_with_history.append(item)
            print(f"Завантажено {len(items_with_history)} товарів з історією.")
            return items_with_history
        else:
            print("База даних товарів порожня або сталася помилка.")
            return []
    except Exception as e:
        st.error(f"Помилка завантаження товарів з БД: {e}")
        return []

# Ця функція не кешується окремо, бо викликається з load_items_from_db, яка кешується
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

# Визначення функції ДО її першого виклику
def get_item_by_db_id(db_id):
    """Знаходить словник товару в кеші inventory_list за його ID з бази даних."""
    items = load_items_from_db() # Використовуємо кешовані дані
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
        # Додаємо перевірку типів на всяк випадок
        if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
             total_sold_qty += qty
             total_sales_value += qty * price
        else:
             print(f"Попередження: некоректні типи даних у записі продажу: qty={qty}, price={price}")


    average_sell_price = total_sales_value / total_sold_qty if total_sold_qty > 0 else 0.0
    return total_sold_qty, average_sell_price

# --- Ініціалізація стану додатку ---
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'view_items'
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
if 'show_statistics' not in st.session_state:
     st.session_state.show_statistics = False
     st.session_state.stats_selected_item_id = None
if 'confirm_delete_id' not in st.session_state:
     st.session_state.confirm_delete_id = None
if 'confirm_delete_sale_id' not in st.session_state:
     st.session_state.confirm_delete_sale_id = None
     st.session_state.confirm_delete_sale_item_id = None

# --- Функції для UI та логіки ---

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

def display_add_item_form():
    """Відображає форму для додавання нового товару."""
    st.subheader("Додати новий товар")
    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("Назва товару*", key="add_name")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, key="add_qty")
        cost_usd = st.number_input("Вартість ($)", min_value=0.0, step=0.01, format="%.2f", key="add_cost")
        shipping_usd = st.number_input("Доставка ($)", min_value=0.0, step=0.01, format="%.2f", key="add_ship")
        rate = st.number_input("Курс $/грн*", min_value=0.01, step=0.01, format="%.4f", key="add_rate")
        customs_uah = st.number_input("Митний платіж (грн)", min_value=0.0, step=0.01, format="%.2f", key="add_customs")
        description = st.text_area("Опис", key="add_desc")

        submitted = st.form_submit_button("Додати товар")
        if submitted:
            if not supabase:
                st.error("Немає підключення до бази даних для додавання товару.")
                return

            if not name or not initial_quantity or not rate:
                st.warning("Будь ласка, заповніть обов'язкові поля: Назва, Початкова к-сть, Курс.")
            else:
                cost_uah = calculate_uah_cost(cost_usd, shipping_usd, rate)
                try:
                    response = supabase.table('items').insert({
                        "name": name,
                        "initial_quantity": initial_quantity,
                        "cost_usd": cost_usd,
                        "shipping_usd": shipping_usd,
                        "rate": rate,
                        "cost_uah": cost_uah,
                        "customs_uah": customs_uah,
                        "description": description
                    }).execute()

                    if response.data:
                        st.success(f"Товар '{name}' успішно додано!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                         st.error(f"Помилка при додаванні товару: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при додаванні товару: {e}")

def display_edit_item_form(item_data):
    """Відображає форму для редагування товару."""
    st.subheader(f"Редагувати товар: {item_data.get('name', 'Н/Д')}")
    with st.form("edit_item_form"):
        name = st.text_input("Назва товару*", value=item_data.get('name', ''), key=f"edit_name_{item_data['id']}")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, value=item_data.get('initial_quantity', 1), key=f"edit_qty_{item_data['id']}")
        # Виправлення TypeError: Явно перетворюємо значення на float
        cost_usd = st.number_input("Вартість ($)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('cost_usd', 0.0)), key=f"edit_cost_{item_data['id']}")
        shipping_usd = st.number_input("Доставка ($)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('shipping_usd', 0.0)), key=f"edit_ship_{item_data['id']}")
        rate = st.number_input("Курс $/грн*", min_value=0.01, step=0.01, format="%.4f", value=float(item_data.get('rate', 0.0)), key=f"edit_rate_{item_data['id']}")
        customs_uah = st.number_input("Митний платіж (грн)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('customs_uah', 0.0)), key=f"edit_customs_{item_data['id']}")
        description = st.text_area("Опис", value=item_data.get('description', ''), key=f"edit_desc_{item_data['id']}")

        sold_qty, _ = get_item_sales_info_cached(item_data)
        if sold_qty > 0:
            st.caption(f"(Вже продано: {sold_qty} од.)")

        col1, col2 = st.columns(2)
        with col1:
             submitted = st.form_submit_button("Зберегти зміни")
        with col2:
             cancelled = st.form_submit_button("Скасувати")

        if submitted:
            if not supabase:
                st.error("Немає підключення до бази даних для збереження змін.")
                return

            if not name or not initial_quantity or not rate:
                st.warning("Будь ласка, заповніть обов'язкові поля: Назва, Початкова к-сть, Курс.")
            elif initial_quantity < sold_qty:
                 st.error(f"Нова початкова кількість ({initial_quantity}) не може бути меншою за вже продану ({sold_qty})!")
            else:
                cost_uah = calculate_uah_cost(cost_usd, shipping_usd, rate)
                try:
                    response = supabase.table('items').update({
                        "name": name,
                        "initial_quantity": initial_quantity,
                        "cost_usd": cost_usd,
                        "shipping_usd": shipping_usd,
                        "rate": rate,
                        "cost_uah": cost_uah,
                        "customs_uah": customs_uah,
                        "description": description
                    }).eq('id', item_data['id']).execute()

                    if response.data:
                        st.success(f"Дані товару '{name}' оновлено!")
                        st.cache_data.clear()
                        st.session_state.editing_item_id = None
                        st.rerun()
                    else:
                        st.error(f"Помилка при оновленні товару: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при оновленні товару: {e}")
        if cancelled:
             st.session_state.editing_item_id = None
             st.rerun()

def display_items_view():
    """Відображає список товарів, фільтри, пошук та кнопки дій."""
    st.subheader("Список товарів")

    col1, col2 = st.columns([2, 3])
    with col1:
        search_term = st.text_input("Пошук за назвою", key="search_input")
    with col2:
        filter_status = st.radio(
            "Фільтр:",
            ('all', 'in_stock', 'sold'),
            format_func=lambda x: {'all': 'Усі', 'in_stock': 'В наявності', 'sold': 'Продані'}.get(x, x),
            horizontal=True,
            key="filter_radio"
        )

    items_data = load_items_from_db()
    filtered_items = []
    search_term_lower = search_term.lower()

    for item in items_data:
        # Пошук
        if search_term_lower and search_term_lower not in item.get('name', '').lower():
            continue

        # Розрахунок для фільтрації
        initial_qty = item.get('кількість', 0)
        sold_qty, avg_price = get_item_sales_info_cached(item)
        remaining_qty = initial_qty - sold_qty
        has_sales = sold_qty > 0

        # Фільтрація
        if filter_status == 'sold' and not has_sales:
            continue
        if filter_status == 'in_stock' and remaining_qty <= 0:
            continue

        # Додаємо розраховані поля для зручності
        item['remaining_qty'] = remaining_qty
        item['has_sales'] = has_sales
        item['can_sell'] = remaining_qty > 0
        item['avg_sell_price'] = avg_price

        filtered_items.append(item)

    if filtered_items:
        display_data = []
        for item in filtered_items:
            display_data.append({
                "ID": item['id'],
                "Назва": item.get('назва', ''),
                "Залишок": item['remaining_qty'],
                "Вартість (₴)": format_currency(item.get('cost_uah', 0.0)),
                "Мито (₴)": format_currency(item.get('customs_uah', 0.0)),
                "Сер. ціна продажу (₴/од.)": format_currency(item['avg_sell_price']) if item['has_sales'] else "---",
                "Опис": item.get('опис', '')
            })

        df = pd.DataFrame(display_data)
        st.dataframe(df, hide_index=True, use_container_width=True)

        st.write("Дії з вибраним товаром:")
        item_options = {item['id']: f"{item['id']}: {item.get('назва', 'Без назви')}" for item in filtered_items}
        current_selection_id = st.session_state.get('selected_item_id', None)
        if current_selection_id not in item_options:
             current_selection_id = None

        # Встановлюємо індекс за замовчуванням на 0, якщо немає вибору або вибір недійсний
        default_index = 0
        if current_selection_id and current_selection_id in item_options:
             try:
                 default_index = list(item_options.keys()).index(current_selection_id)
             except ValueError:
                 default_index = 0 # Якщо ID не знайдено в ключах (малоймовірно)

        selected_id = st.selectbox(
             "Виберіть товар (ID: Назва)",
             options=list(item_options.keys()),
             format_func=lambda x: item_options.get(x, "Невідомий ID"),
             index=default_index,
             key="item_selector",
             label_visibility="collapsed"
        )

        st.session_state.selected_item_id = selected_id

        selected_item_data = None
        if selected_id is not None:
             for item in filtered_items:
                 if item['id'] == selected_id:
                      selected_item_data = item
                      break

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("Редагувати", key="edit_btn", disabled=selected_item_data is None):
                st.session_state.editing_item_id = selected_id
                st.rerun()
        with col2:
            if st.button("Видалити", key="delete_btn", disabled=selected_item_data is None):
                if selected_item_data:
                    st.session_state.confirm_delete_id = selected_id
                    st.rerun()
                else:
                    st.warning("Спочатку виберіть товар.")
        with col3:
            can_sell = selected_item_data.get('can_sell', False) if selected_item_data else False
            if st.button("Продати", key="sell_btn", disabled=not can_sell):
                 st.session_state.selling_item_id = selected_id
                 st.rerun()
        with col4:
            has_sales = selected_item_data.get('has_sales', False) if selected_item_data else False
            if st.button("Історія продажів", key="history_btn", disabled=not has_sales):
                 st.session_state.viewing_history_item_id = selected_id
                 st.rerun()
        with col5:
             if st.button("Статистика", key="stats_btn"):
                  st.session_state.show_statistics = True
                  st.session_state.stats_selected_item_id = selected_id if selected_item_data else None
                  st.rerun()

        # --- Підтвердження видалення товару ---
        if 'confirm_delete_id' in st.session_state and st.session_state.confirm_delete_id is not None:
             item_to_delete = get_item_by_db_id(st.session_state.confirm_delete_id)
             item_name = item_to_delete.get('назва', 'Н/Д') if item_to_delete else 'Н/Д'
             st.warning(f"**Ви впевнені, що хочете видалити товар '{item_name}' (ID: {st.session_state.confirm_delete_id}) та всю його історію продажів?**")
             c1, c2, _ = st.columns([1,1,5])
             if c1.button("Так, видалити", key="confirm_delete_yes"):
                  db_id_to_delete = st.session_state.confirm_delete_id
                  st.session_state.confirm_delete_id = None
                  if not supabase:
                      st.error("Немає підключення до бази даних для видалення.")
                      return
                  try:
                      response = supabase.table('items').delete().eq('id', db_id_to_delete).execute()
                      st.success(f"Товар '{item_name}' видалено.")
                      st.cache_data.clear()
                      st.session_state.selected_item_id = None
                      st.rerun()
                  except Exception as e:
                      st.error(f"Помилка видалення з БД: {e}")

             if c2.button("Ні, скасувати", key="confirm_delete_no"):
                  st.session_state.confirm_delete_id = None
                  st.rerun()

    else:
        st.info("Немає товарів, що відповідають поточним фільтрам та пошуку.")

def display_sell_item_form(item_data):
    """Відображає форму для продажу одиниць товару."""
    st.subheader(f"Продаж товару: {item_data.get('назва', 'Н/Д')}")
    initial_qty = item_data.get('кількість', 0)
    sold_qty, avg_price = get_item_sales_info_cached(item_data)
    available_qty = initial_qty - sold_qty

    st.write(f"Доступно для продажу: **{available_qty}** од.")

    with st.form("sell_item_form"):
        quantity_to_sell = st.number_input("Кількість для продажу*", min_value=1, max_value=available_qty, step=1, value=1, key="sell_qty")
        last_sale_price = None
        if item_data.get('sales_history'):
            last_sale_price = item_data['sales_history'][-1].get('price_per_unit_uah')
        suggested_price = last_sale_price if last_sale_price is not None else avg_price
        unit_sell_price = st.number_input("Ціна за одиницю (грн)*", min_value=0.0, step=0.01, format="%.2f", value=float(suggested_price) if suggested_price > 0 else 0.01, key="sell_price") # Явне перетворення на float

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Зареєструвати продаж")
        with col2:
            cancelled = st.form_submit_button("Скасувати")

        if submitted:
            if not supabase:
                 st.error("Немає підключення до бази даних для реєстрації продажу.")
                 return

            if not quantity_to_sell or unit_sell_price is None:
                st.warning("Вкажіть кількість та ціну продажу.")
            elif quantity_to_sell > available_qty:
                 st.error(f"Кількість для продажу ({quantity_to_sell}) не може перевищувати доступну ({available_qty}).")
            else:
                try:
                    timestamp = datetime.now().isoformat()
                    response = supabase.table('sales').insert({
                        "item_id": item_data['id'],
                        "quantity_sold": quantity_to_sell,
                        "price_per_unit_uah": unit_sell_price,
                        "sale_timestamp": timestamp
                    }).execute()

                    if response.data:
                        st.success(f"Продано {quantity_to_sell} од. товару '{item_data.get('назва', '')}'.")
                        st.cache_data.clear()
                        st.session_state.selling_item_id = None
                        st.rerun()
                    else:
                         st.error(f"Помилка при реєстрації продажу: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при реєстрації продажу: {e}")
        if cancelled:
            st.session_state.selling_item_id = None
            st.rerun()

def display_sales_history(item_data):
    """Відображає історію продажів для товару та кнопки управління."""
    st.subheader(f"Історія продажів: {item_data.get('назва', 'Н/Д')}")
    sales_history = item_data.get('sales_history', [])

    if not sales_history:
        st.info("Історія продажів для цього товару порожня.")
        if st.button("Назад до списку", key="back_from_empty_history"):
            st.session_state.viewing_history_item_id = None
            st.rerun()
        return

    history_display_data = []
    for sale in sales_history:
         timestamp_display = "Н/Д"
         try:
             dt_object = datetime.fromisoformat(sale.get('sale_timestamp', ''))
             timestamp_display = dt_object.strftime('%Y-%m-%d %H:%M:%S')
         except (TypeError, ValueError):
             timestamp_display = str(sale.get('sale_timestamp', 'Н/Д'))

         history_display_data.append({
             "ID Продажу": sale['id'],
             "Кількість": sale.get('quantity_sold', 0),
             "Ціна за од. (₴)": format_currency(sale.get('price_per_unit_uah', 0.0)),
             "Дата/Час": timestamp_display
         })

    df_history = pd.DataFrame(history_display_data)
    st.dataframe(df_history, hide_index=True, use_container_width=True)

    st.write("Дії з вибраним продажем:")
    sale_options = {sale['id']: f"ID: {sale['id']} ({sale.get('quantity_sold', 0)} од. по {format_currency(sale.get('price_per_unit_uah', 0.0))})" for sale in sales_history}
    selected_sale_id_str = st.selectbox(
         "Виберіть продаж",
         options=list(sale_options.keys()),
         format_func=lambda x: sale_options.get(x, "Невідомий ID"),
         index=0,
         key="sale_selector",
         label_visibility="collapsed"
    )
    selected_sale_id = int(selected_sale_id_str) if selected_sale_id_str else None

    col1, col2, col3 = st.columns([1,1,5])
    with col1:
         if st.button("Редагувати", key="edit_sale_btn", disabled=selected_sale_id is None):
             st.session_state.editing_sale_id = selected_sale_id
             st.session_state.editing_sale_item_id = item_data['id']
             st.rerun()
    with col2:
        if st.button("Видалити", key="delete_sale_btn", disabled=selected_sale_id is None):
             st.session_state.confirm_delete_sale_id = selected_sale_id
             st.session_state.confirm_delete_sale_item_id = item_data['id']
             st.rerun()

    # --- Підтвердження видалення продажу ---
    if 'confirm_delete_sale_id' in st.session_state and st.session_state.confirm_delete_sale_id is not None:
        sale_id_to_delete = st.session_state.confirm_delete_sale_id
        st.warning(f"**Ви впевнені, що хочете видалити запис про продаж ID: {sale_id_to_delete}?**")
        c1, c2, _ = st.columns([1,1,5])
        if c1.button("Так, видалити продаж", key="confirm_delete_sale_yes"):
            item_id_for_update = st.session_state.confirm_delete_sale_item_id
            st.session_state.confirm_delete_sale_id = None
            st.session_state.confirm_delete_sale_item_id = None
            if not supabase:
                 st.error("Немає підключення до бази даних для видалення продажу.")
                 return
            try:
                response = supabase.table('sales').delete().eq('id', sale_id_to_delete).execute()
                st.success(f"Запис про продаж ID: {sale_id_to_delete} видалено.")
                st.cache_data.clear()
                st.session_state.viewing_history_item_id = item_id_for_update
                st.rerun()
            except Exception as e:
                st.error(f"Помилка видалення продажу з БД: {e}")

        if c2.button("Ні, скасувати", key="confirm_delete_sale_no"):
            st.session_state.confirm_delete_sale_id = None
            st.session_state.confirm_delete_sale_item_id = None
            st.rerun()

    if st.button("Назад до списку товарів", key="back_from_history"):
        st.session_state.viewing_history_item_id = None
        st.rerun()

def display_edit_sale_form(item_data, sale_data):
    """Відображає форму для редагування конкретного продажу."""
    st.subheader(f"Редагувати продаж ID: {sale_data['id']} для товару: {item_data.get('назва', 'Н/Д')}")
    initial_item_qty = item_data.get('кількість', 0)

    with st.form("edit_sale_form"):
        quantity_sold = st.number_input(
            "Продана кількість*",
            min_value=1,
            step=1,
            value=sale_data.get('quantity_sold', 1),
            key=f"edit_sale_qty_{sale_data['id']}"
        )
        price_per_unit = st.number_input(
            "Ціна за одиницю (грн)*",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            value=float(sale_data.get('price_per_unit_uah', 0.0)), # Явне перетворення
            key=f"edit_sale_price_{sale_data['id']}"
        )

        other_sales_qty = 0
        for sale in item_data.get('sales_history', []):
            if sale.get('id') != sale_data['id']:
                other_sales_qty += sale.get('quantity_sold', 0)
        max_allowed_here = initial_item_qty - other_sales_qty
        st.caption(f"Максимально допустима кількість для цього продажу: {max_allowed_here}")

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Зберегти зміни продажу")
        with col2:
            cancelled = st.form_submit_button("Скасувати редагування")

        if submitted:
            if not supabase:
                 st.error("Немає підключення до бази даних для збереження змін продажу.")
                 return
            if not quantity_sold or price_per_unit is None:
                st.warning("Вкажіть кількість та ціну.")
            elif quantity_sold > max_allowed_here:
                 st.error(f"Нова кількість ({quantity_sold}) перевищує максимально допустиму ({max_allowed_here}) для цього продажу.")
            else:
                try:
                    response = supabase.table('sales').update({
                        "quantity_sold": quantity_sold,
                        "price_per_unit_uah": price_per_unit
                    }).eq('id', sale_data['id']).execute()

                    if response.data:
                        st.success(f"Дані продажу ID: {sale_data['id']} оновлено.")
                        st.cache_data.clear()
                        st.session_state.editing_sale_id = None
                        st.session_state.editing_sale_item_id = None
                        st.session_state.viewing_history_item_id = item_data['id']
                        st.rerun()
                    else:
                         st.error(f"Помилка при оновленні продажу: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при оновленні продажу: {e}")

        if cancelled:
            st.session_state.editing_sale_id = None
            st.session_state.editing_sale_item_id = None
            st.session_state.viewing_history_item_id = item_data['id']
            st.rerun()

def display_statistics():
    """Відображає вікно статистики."""
    st.subheader("Статистика товарів")

    items_data = load_items_from_db()
    total_initial_items_sum = 0
    total_sold_items_sum = 0
    entries_with_sales = 0
    unsold_entries = 0
    total_expenses = 0.0
    total_income_actual = 0.0
    unsold_items_cost = 0.0

    for item in items_data:
        initial_qty = item.get('кількість', 0)
        cost_uah = item.get('вартість_uah', 0.0)
        customs_uah = item.get('мито_uah', 0.0)
        unit_cost = (cost_uah + customs_uah) / initial_qty if initial_qty > 0 else 0

        total_initial_items_sum += initial_qty
        total_expenses += cost_uah + customs_uah

        item_sold_qty, _ = get_item_sales_info_cached(item)
        item_income = 0.0
        sales_history = item.get('sales_history', [])

        if sales_history:
            entries_with_sales += 1
            for sale in sales_history:
                qty = sale.get('quantity_sold', 0)
                price = sale.get('price_per_unit_uah', 0.0)
                item_income += qty * price
        else:
            unsold_entries += 1

        total_sold_items_sum += item_sold_qty
        total_income_actual += item_income

        remaining_qty = initial_qty - item_sold_qty
        if remaining_qty > 0:
            unsold_items_cost += remaining_qty * unit_cost

    overall_profit_loss = total_income_actual - total_expenses

    st.markdown("#### Загальна статистика")
    col1, col2 = st.columns(2)
    col1.metric("Кількість записів", len(items_data))
    col1.metric("Загальна початкова к-сть од.", total_initial_items_sum)
    col1.metric("Загально продано од.", total_sold_items_sum)
    col2.metric("Записи з продажами", entries_with_sales)
    col2.metric("Записи без продаж", unsold_entries)

    st.markdown("---")
    col1, col2 = st.columns(2)
    col1.metric("Загальні витрати (на всі од.)", format_currency(total_expenses))
    col1.metric("Загальний дохід (з проданих од.)", format_currency(total_income_actual))
    col2.metric("Прибуток / Збиток (Дохід - Всі витрати)", format_currency(overall_profit_loss))
    col2.metric("Вартість одиниць в наявності", format_currency(unsold_items_cost))

    st.markdown("---")
    st.markdown("#### Статистика вибраного запису")
    selected_item_id = st.session_state.get('stats_selected_item_id', None)
    selected_item_data = None
    if selected_item_id:
         for item in items_data:
              if item['id'] == selected_item_id:
                   selected_item_data = item
                   break

    if selected_item_data:
        s_initial_qty = selected_item_data.get('кількість', 0)
        s_cost_uah = selected_item_data.get('вартість_uah', 0.0)
        s_customs_uah = selected_item_data.get('мито_uah', 0.0)
        s_sales_history = selected_item_data.get('sales_history', [])

        s_expenses = s_cost_uah + s_customs_uah
        s_unit_cost = s_expenses / s_initial_qty if s_initial_qty > 0 else 0
        s_sold_qty, s_avg_sell_price = get_item_sales_info_cached(selected_item_data)
        s_income = s_sold_qty * s_avg_sell_price if s_sold_qty > 0 else 0.0
        s_remaining_qty = s_initial_qty - s_sold_qty
        s_profit_loss = s_income - (s_sold_qty * s_unit_cost) if s_sold_qty > 0 else None

        st.write(f"**Назва:** {selected_item_data.get('назва', 'Н/Д')}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Початкова к-сть", s_initial_qty)
        col2.metric("Продано к-сть", s_sold_qty)
        col3.metric("Залишок к-сть", s_remaining_qty)

        col1, col2 = st.columns(2)
        col1.metric("Витрати (на весь запис)", format_currency(s_expenses))
        col2.metric("Витрати на 1 од.", format_currency(s_unit_cost))
        col1.metric("Середня ціна продажу (за 1 од.)", format_currency(s_avg_sell_price) if s_sold_qty > 0 else "---")
        col2.metric("Дохід (з проданих од.)", format_currency(s_income))
        st.metric("Прибуток / Збиток (з проданих)", format_currency(s_profit_loss) if s_profit_loss is not None else "---")

    else:
        st.info("Товар не вибрано у списку для детальної статистики.")

    if st.button("Назад до списку", key="back_from_stats"):
        st.session_state.show_statistics = False
        st.session_state.stats_selected_item_id = None
        st.rerun()

# --- Головний UI ---

st.set_page_config(layout="wide", page_title="Облік товарів")
st.title("📊 Програма обліку товарів")

st.sidebar.title("Навігація")
view_choice = st.sidebar.radio(
    "Оберіть дію:",
    ('Перегляд товарів', 'Додати товар'),
    key='navigation_radio'
)

# Визначаємо поточний вид на основі стану
if view_choice == 'Додати товар':
    st.session_state.current_view = 'add_item'
    # Скидаємо інші стани
    st.session_state.editing_item_id = None
    st.session_state.selling_item_id = None
    st.session_state.viewing_history_item_id = None
    st.session_state.editing_sale_id = None
    st.session_state.show_statistics = False
else: # Якщо вибрано 'Перегляд товарів' або нічого не вибрано
    if st.session_state.get('editing_item_id') is not None:
        st.session_state.current_view = 'edit_item'
    elif st.session_state.get('selling_item_id') is not None:
        st.session_state.current_view = 'sell_item'
    elif st.session_state.get('viewing_history_item_id') is not None:
         if st.session_state.get('editing_sale_id') is not None:
              st.session_state.current_view = 'edit_sale'
         else:
              st.session_state.current_view = 'view_history'
    elif st.session_state.get('show_statistics'):
         st.session_state.current_view = 'statistics'
    else: # За замовчуванням показуємо список
        st.session_state.current_view = 'view_items'


# --- Відображення відповідного контенту ---

if st.session_state.current_view == 'add_item':
    display_add_item_form()
elif st.session_state.current_view == 'edit_item':
    if st.session_state.editing_item_id:
        item_to_edit = get_item_by_db_id(st.session_state.editing_item_id)
        if item_to_edit:
            display_edit_item_form(item_to_edit)
        else:
            st.error("Помилка: не знайдено товар для редагування (ID: {}). Повернення до списку.".format(st.session_state.editing_item_id))
            st.session_state.editing_item_id = None
            st.session_state.current_view = 'view_items'
            st.rerun()
    else:
         st.warning("Не вибрано товар для редагування. Повернення до списку.")
         st.session_state.current_view = 'view_items'
         st.rerun()

elif st.session_state.current_view == 'sell_item':
     if st.session_state.selling_item_id:
         item_to_sell = get_item_by_db_id(st.session_state.selling_item_id)
         if item_to_sell:
             display_sell_item_form(item_to_sell)
         else:
             st.error("Помилка: не знайдено товар для продажу (ID: {}). Повернення до списку.".format(st.session_state.selling_item_id))
             st.session_state.selling_item_id = None
             st.session_state.current_view = 'view_items'
             st.rerun()
     else:
          st.warning("Не вибрано товар для продажу. Повернення до списку.")
          st.session_state.current_view = 'view_items'
          st.rerun()

elif st.session_state.current_view == 'view_history':
     if st.session_state.viewing_history_item_id:
         item_for_history = get_item_by_db_id(st.session_state.viewing_history_item_id)
         if item_for_history:
              display_sales_history(item_for_history)
         else:
              st.error("Помилка: не знайдено товар для перегляду історії (ID: {}). Повернення до списку.".format(st.session_state.viewing_history_item_id))
              st.session_state.viewing_history_item_id = None
              st.session_state.current_view = 'view_items'
              st.rerun()
     else:
          st.warning("Не вибрано товар для перегляду історії. Повернення до списку.")
          st.session_state.current_view = 'view_items'
          st.rerun()

elif st.session_state.current_view == 'edit_sale':
     if st.session_state.editing_sale_item_id and st.session_state.editing_sale_id:
         item_for_sale_edit = get_item_by_db_id(st.session_state.editing_sale_item_id)
         sale_to_edit = None
         if item_for_sale_edit:
              for sale in item_for_sale_edit.get('sales_history', []):
                   if sale.get('id') == st.session_state.editing_sale_id:
                        sale_to_edit = sale
                        break
         if item_for_sale_edit and sale_to_edit:
              display_edit_sale_form(item_for_sale_edit, sale_to_edit)
         else:
              st.error("Помилка: не знайдено продаж для редагування (Sale ID: {}, Item ID: {}). Повернення до історії.".format(st.session_state.editing_sale_id, st.session_state.editing_sale_item_id))
              st.session_state.editing_sale_id = None
              st.session_state.editing_sale_item_id = None
              if st.session_state.viewing_history_item_id:
                   st.session_state.current_view = 'view_history'
              else:
                   st.session_state.current_view = 'view_items'
              st.rerun()
     else:
          st.warning("Не вибрано продаж для редагування. Повернення до списку.")
          st.session_state.current_view = 'view_items'
          st.session_state.editing_sale_id = None
          st.session_state.editing_sale_item_id = None
          st.session_state.viewing_history_item_id = None
          st.rerun()

elif st.session_state.current_view == 'statistics':
     display_statistics()
else: # 'view_items'
    display_items_view()

# --- Додатково: кнопка для очищення кешу (для відладки) ---
# st.sidebar.button("Очистити кеш даних", on_click=st.cache_data.clear)

