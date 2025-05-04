import streamlit as st
from datetime import datetime
# Імпортуємо весь модуль apppp
try:
    import apppp
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py'. Переконайтесь, що він існує в кореневій папці.")
    st.stop()

def display_add_item_form():
    """Відображає форму для додавання нового товару з вибором країни/валюти."""
    # st.subheader("Додати новий товар") # Заголовок тепер береться з назви файлу

    # Вибір країни - виносимо за межі форми, щоб UI оновлювався динамічно
    selected_country = st.selectbox(
        "Країна походження*",
        options=list(apppp.CURRENCY_SETTINGS.keys()), # Використовуємо apppp.CURRENCY_SETTINGS
        key="add_country_select" # Ключ для збереження вибору
    )

    # Отримуємо налаштування для вибраної країни
    settings = apppp.CURRENCY_SETTINGS[selected_country] # Використовуємо apppp.CURRENCY_SETTINGS
    currency_symbol = settings["symbol"]
    currency_code = settings["code"]
    default_rate = settings["default_rate"]
    rate_label = settings["rate_label"]

    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("Назва товару*", key="add_name")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, key="add_qty")

        # Поля вартості та доставки з динамічним символом валюти
        cost_original = st.number_input(f"Вартість ({currency_symbol})*", min_value=0.0, step=0.01, format="%.2f", key="add_cost_original")
        shipping_original = st.number_input(f"Доставка ({currency_symbol})*", min_value=0.0, step=0.01, format="%.2f", key="add_shipping_original")

        # Поле курсу з динамічною міткою та значенням за замовчуванням
        rate = st.number_input(
            rate_label,
            min_value=0.01,
            step=0.01,
            format="%.4f",
            value=default_rate, # Встановлюємо значення за замовчуванням
            key="add_rate_dynamic" # Використовуємо новий ключ, щоб value оновлювалось
            )

        customs_uah = st.number_input("Митний платіж (грн)", min_value=0.0, step=0.01, format="%.2f", key="add_customs")
        description = st.text_area("Опис", key="add_desc")

        submitted = st.form_submit_button("Додати товар")
        if submitted:
            # Звертаємось до supabase через apppp.supabase
            if not apppp.supabase:
                st.error("Немає підключення до бази даних для додавання товару.")
                return

            # Валідація основних полів
            if not name or not initial_quantity or not cost_original or not shipping_original or not rate:
                st.warning(f"Будь ласка, заповніть обов'язкові поля: Назва, Початкова к-сть, Вартість ({currency_symbol}), Доставка ({currency_symbol}), {rate_label}.")
                return

            # Звертаємось до функції через apppp.calculate_uah_cost
            cost_uah = apppp.calculate_uah_cost(cost_original, shipping_original, rate)

            try:
                insert_data = {
                    "name": name,
                    "initial_quantity": initial_quantity,
                    "origin_country": selected_country, # Зберігаємо країну
                    "original_currency": currency_code, # Зберігаємо код валюти
                    "cost_original": cost_original,     # Зберігаємо оригінальну вартість
                    "shipping_original": shipping_original, # Зберігаємо оригінальну доставку
                    "rate": rate,                       # Зберігаємо використаний курс
                    "cost_uah": cost_uah,               # Зберігаємо розраховану вартість в грн
                    "customs_uah": customs_uah,
                    "description": description
                }
                # Звертаємось до supabase через apppp.supabase
                response = apppp.supabase.table('items').insert(insert_data).execute()

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
