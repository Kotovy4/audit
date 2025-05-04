import streamlit as st
from datetime import datetime
# Імпортуємо спільні функції та клієнт supabase з основного файлу
try:
    from apppp import (
        supabase,
        calculate_uah_cost,
        format_currency # Може знадобитись для відображення розрахункової ціни
    )
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py' або необхідні функції.")
    st.stop()

def display_add_item_form():
    """Відображає форму для додавання нового товару."""
    # st.subheader("Додати новий товар") # Заголовок тепер береться з назви файлу
    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("Назва товару*", key="add_name")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, key="add_qty")
        cost_usd = st.number_input("Вартість ($)", min_value=0.0, step=0.01, format="%.2f", key="add_cost")
        shipping_usd = st.number_input("Доставка ($)", min_value=0.0, step=0.01, format="%.2f", key="add_ship")
        # Встановлюємо значення за замовчуванням value=42.0
        rate = st.number_input(
            "Курс $/грн*",
            min_value=0.01,
            step=0.01,
            format="%.4f",
            value=42.0, # <--- ДОДАНО ЗНАЧЕННЯ ЗА ЗАМОВЧУВАННЯМ
            key="add_rate"
            )
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
                        st.cache_data.clear() # Очищуємо кеш, щоб інші сторінки побачили зміни
                        # Немає потреби в rerun, форма очиститься автоматично
                    else:
                         st.error(f"Помилка при додаванні товару: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при додаванні товару: {e}")

# --- Головна частина сторінки ---
# Заголовок буде взято з назви файлу "1_➕_Додати_товар"
# st.header("➕ Додати новий товар")
display_add_item_form()

