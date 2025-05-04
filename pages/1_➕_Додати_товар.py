import streamlit as st
from datetime import datetime
# Імпортуємо весь модуль apppp
try:
    import apppp
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py'. Переконайтесь, що він існує в кореневій папці.")
    st.stop()

# Словник для налаштувань валют (можна залишити тут або перенести в apppp.py)
CURRENCY_SETTINGS = {
    "USA": {"symbol": "$", "code": "USD", "default_rate": 42.0, "rate_label": "Курс $/грн*"},
    "Poland": {"symbol": "zł", "code": "PLN", "default_rate": 11.11, "rate_label": "Курс zł/грн*"}
}

def display_add_item_form():
    """Відображає форму для додавання нового товару з вибором країни/валюти."""
    selected_country = st.selectbox(
        "Країна походження*",
        options=list(apppp.CURRENCY_SETTINGS.keys()), # Використовуємо apppp.CURRENCY_SETTINGS
        key="add_country_select"
    )

    settings = apppp.CURRENCY_SETTINGS[selected_country] # Використовуємо apppp.CURRENCY_SETTINGS
    currency_symbol = settings["symbol"]
    currency_code = settings["code"]
    default_rate = settings["default_rate"]
    rate_label = settings["rate_label"]

    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("Назва товару*", key="add_name")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, key="add_qty", value=1) # Додано value=1 за замовчуванням
        cost_original = st.number_input(f"Вартість ({currency_symbol})*", min_value=0.0, step=0.01, format="%.2f", key="add_cost_original", value=0.0) # Додано value=0.0
        shipping_original = st.number_input(f"Доставка ({currency_symbol})*", min_value=0.0, step=0.01, format="%.2f", key="add_shipping_original", value=0.0) # Додано value=0.0
        rate = st.number_input(
            rate_label,
            min_value=0.01,
            step=0.01,
            format="%.4f",
            value=default_rate,
            key="add_rate_dynamic"
            )
        customs_uah = st.number_input("Митний платіж (грн)", min_value=0.0, step=0.01, format="%.2f", key="add_customs", value=0.0) # Додано value=0.0
        description = st.text_area("Опис", key="add_desc")

        submitted = st.form_submit_button("Додати товар")
        if submitted:
            if not apppp.supabase:
                st.error("Немає підключення до бази даних для додавання товару.")
                return

            # --- Оновлена валідація ---
            validation_error = False
            error_messages = []
            # Перевіряємо назву
            if not name:
                validation_error = True
                error_messages.append("Назва товару")
            # Перевіряємо кількість (має бути цілим числом > 0)
            if initial_quantity is None or initial_quantity <= 0:
                 validation_error = True
                 error_messages.append("Початкова кількість (має бути > 0)")
            # Перевіряємо курс (має бути числом > 0)
            if rate is None or rate <= 0:
                 validation_error = True
                 error_messages.append(f"{rate_label} (має бути > 0)")
            # Перевіряємо, чи числові поля для валюти не є None (хоча можуть бути 0.0)
            if cost_original is None:
                 validation_error = True
                 error_messages.append(f"Вартість ({currency_symbol})")
            if shipping_original is None:
                 validation_error = True
                 error_messages.append(f"Доставка ({currency_symbol})")

            if validation_error:
                st.warning(f"Будь ласка, заповніть або перевірте обов'язкові поля: {', '.join(error_messages)}.")
                return # Зупиняємо виконання, якщо є помилка валідації
            # --- Кінець оновленої валідації ---


            cost_uah = apppp.calculate_uah_cost(cost_original, shipping_original, rate) # Використовуємо apppp.

            try:
                insert_data = {
                    "name": name,
                    "initial_quantity": initial_quantity,
                    "origin_country": selected_country,
                    "original_currency": currency_code,
                    "cost_original": cost_original,
                    "shipping_original": shipping_original,
                    "rate": rate,
                    "cost_uah": cost_uah,
                    "customs_uah": customs_uah if customs_uah is not None else 0.0, # Перевірка на None для мита
                    "description": description
                }
                response = apppp.supabase.table('items').insert(insert_data).execute() # Використовуємо apppp.

                if response.data:
                    st.success(f"Товар '{name}' успішно додано!")
                    st.cache_data.clear()
                else:
                     st.error(f"Помилка при додаванні товару: {getattr(response, 'error', 'Невідома помилка')}")

            except Exception as e:
                st.error(f"Помилка бази даних при додаванні товару: {e}")

# --- Головна частина сторінки ---
display_add_item_form()
