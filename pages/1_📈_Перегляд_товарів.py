import streamlit as st
import pandas as pd
from datetime import datetime
# Імпортуємо спільні функції та клієнт supabase з основного файлу
# Припускаємо, що основний файл називається apppp.py
# Якщо він називається інакше, змініть імпорт
try:
    from apppp import (
        supabase,
        load_items_from_db,
        load_sales_history_for_item, # Можливо, не потрібен тут напряму
        get_item_by_db_id,
        get_item_sales_info_cached,
        format_currency,
        calculate_uah_cost
    )
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py' або необхідні функції.")
    # Можна додати альтернативні шляхи імпорту, якщо структура інша
    # from ..apppp import ... # Якщо pages на одному рівні з apppp.py
    st.stop()


# --- Функції для відображення форм (перенесені сюди) ---

def display_edit_item_form(item_data):
    """Відображає форму для редагування товару."""
    st.subheader(f"Редагувати товар: {item_data.get('name', 'Н/Д')}")
    with st.form("edit_item_form"):
        name = st.text_input("Назва товару*", value=item_data.get('name', ''), key=f"edit_name_{item_data['id']}")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, value=item_data.get('initial_quantity', 1), key=f"edit_qty_{item_data['id']}")
        cost_usd = st.number_input("Вартість ($)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('cost_usd', 0.0)), key=f"edit_cost_{item_data['id']}")
        shipping_usd = st.number_input("Доставка ($)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('shipping_usd', 0.0)), key=f"edit_ship_{item_data['id']}")
        rate = st.number_input("Курс $/грн*", min_value=0.01, step=0.01, format="%.4f", value=float(item_data.get('rate', 0.0)), key=f"edit_rate_{item_data['id']}")
        customs_uah = st.number_input("Митний платіж (грн)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('customs_uah', 0.0)), key=f"edit_customs_{item_data['id']}")
        description = st.text_area("Опис", value=item_data.get('description', ''), key=f"edit_desc_{item_data['id']}")

        sold_qty, _ = get_item_sales_info_cached(item_data) # Використовуємо кешовану історію
        if sold_qty > 0:
            st.caption(f"(Вже продано: {sold_qty} од.)")

        col1, col2 = st.columns(2)
        with col1:
             submitted = st.form_submit_button("Зберегти зміни")
        with col2:
             # Кнопка скасування просто скидає стан редагування
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
                        st.session_state.editing_item_id = None # Скидаємо стан редагування
                        st.rerun() # Перезапускаємо, щоб повернутися до таблиці
                    else:
                        st.error(f"Помилка при оновленні товару: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при оновленні товару: {e}")
        if cancelled:
             st.session_state.editing_item_id = None # Скидаємо стан редагування
             st.rerun() # Перезапускаємо, щоб повернутися до таблиці

def display_sell_item_form(item_data):
    """Відображає форму для продажу одиниць товару."""
    st.subheader(f"Продаж товару: {item_data.get('name', 'Н/Д')}")
    initial_qty = item_data.get('initial_quantity', 0)
    sold_qty, avg_price = get_item_sales_info_cached(item_data)
    available_qty = initial_qty - sold_qty

    st.write(f"Доступно для продажу: **{available_qty}** од.")

    with st.form("sell_item_form"):
        quantity_to_sell = st.number_input("Кількість для продажу*", min_value=1, max_value=available_qty, step=1, value=1, key="sell_qty")
        last_sale_price = None
        if item_data.get('sales_history'):
            last_sale_price = item_data['sales_history'][-1].get('price_per_unit_uah')
        suggested_price = last_sale_price if last_sale_price is not None else avg_price
        unit_sell_price = st.number_input("Ціна за одиницю (грн)*", min_value=0.0, step=0.01, format="%.2f", value=float(suggested_price) if suggested_price > 0 else 0.01, key="sell_price")

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Зареєструвати продаж")
        with col2:
            # Кнопка скасування просто скидає стан продажу
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
                        st.success(f"Продано {quantity_to_sell} од. товару '{item_data.get('name', '')}'.")
                        st.cache_data.clear()
                        st.session_state.selling_item_id = None # Скидаємо стан продажу
                        st.rerun() # Перезапускаємо, щоб повернутися до таблиці
                    else:
                         st.error(f"Помилка при реєстрації продажу: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при реєстрації продажу: {e}")
        if cancelled:
            st.session_state.selling_item_id = None # Скидаємо стан продажу
            st.rerun() # Перезапускаємо, щоб повернутися до таблиці

def display_sales_history(item_data):
    """Відображає історію продажів для товару та кнопки управління."""
    st.subheader(f"Історія продажів: {item_data.get('name', 'Н/Д')}")
    sales_history = item_data.get('sales_history', [])

    if not sales_history:
        st.info("Історія продажів для цього товару порожня.")
        # Кнопка Назад просто скидає стан перегляду історії
        if st.button("Назад до списку товарів", key="back_from_empty_history"):
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

    col1, col2, col3 = st.columns([1,1,4]) # Змінено пропорції
    with col1:
         # Кнопка редагування встановлює відповідний стан
         if st.button("Редагувати", key="edit_sale_btn", disabled=selected_sale_id is None):
             st.session_state.editing_sale_id = selected_sale_id
             st.session_state.editing_sale_item_id = item_data['id'] # Зберігаємо ID товару
             st.rerun() # Перезапуск покаже форму редагування продажу (на цій же сторінці)
    with col2:
        if st.button("Видалити", key="delete_sale_btn", disabled=selected_sale_id is None):
             # Встановлюємо стан для підтвердження видалення
             st.session_state.confirm_delete_sale_id = selected_sale_id
             st.session_state.confirm_delete_sale_item_id = item_data['id']
             st.rerun() # Перезапуск покаже запит на підтвердження

    # --- Підтвердження видалення продажу ---
    if 'confirm_delete_sale_id' in st.session_state and st.session_state.confirm_delete_sale_id is not None:
        # Перевіряємо, чи ID товару все ще той самий (про всяк випадок)
        if st.session_state.confirm_delete_sale_item_id == item_data['id']:
            sale_id_to_delete = st.session_state.confirm_delete_sale_id
            st.warning(f"**Ви впевнені, що хочете видалити запис про продаж ID: {sale_id_to_delete}?**")
            c1, c2, _ = st.columns([1,1,5])
            if c1.button("Так, видалити продаж", key="confirm_delete_sale_yes"):
                item_id_for_update = st.session_state.confirm_delete_sale_item_id
                # Скидаємо стан підтвердження ДО операції з БД
                st.session_state.confirm_delete_sale_id = None
                st.session_state.confirm_delete_sale_item_id = None
                if not supabase:
                     st.error("Немає підключення до бази даних для видалення продажу.")
                     return
                try:
                    response = supabase.table('sales').delete().eq('id', sale_id_to_delete).execute()
                    st.success(f"Запис про продаж ID: {sale_id_to_delete} видалено.")
                    st.cache_data.clear()
                    # Залишаємось на сторінці історії, просто оновлюємо її
                    st.session_state.viewing_history_item_id = item_id_for_update
                    st.rerun()
                except Exception as e:
                    st.error(f"Помилка видалення продажу з БД: {e}")

            if c2.button("Ні, скасувати", key="confirm_delete_sale_no"):
                st.session_state.confirm_delete_sale_id = None
                st.session_state.confirm_delete_sale_item_id = None
                st.rerun()
        else:
             # Якщо ID товару змінився, поки було відкрито підтвердження, скидаємо стан
             st.session_state.confirm_delete_sale_id = None
             st.session_state.confirm_delete_sale_item_id = None


    # Кнопка Назад до списку товарів
    if st.button("Назад до списку товарів", key="back_from_history"):
        st.session_state.viewing_history_item_id = None # Скидаємо стан
        st.rerun() # Перезапуск поверне до таблиці

def display_edit_sale_form(item_data, sale_data):
    """Відображає форму для редагування конкретного продажу."""
    st.subheader(f"Редагувати продаж ID: {sale_data['id']} для товару: {item_data.get('name', 'Н/Д')}")
    initial_item_qty = item_data.get('initial_quantity', 0)

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
            value=float(sale_data.get('price_per_unit_uah', 0.0)),
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
            # Кнопка скасування скидає стан редагування продажу
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
                        # Скидаємо стан редагування продажу і повертаємось до історії
                        st.session_state.editing_sale_id = None
                        st.session_state.editing_sale_item_id = None
                        st.session_state.viewing_history_item_id = item_data['id'] # Залишаємо ID товару
                        st.rerun()
                    else:
                         st.error(f"Помилка при оновленні продажу: {getattr(response, 'error', 'Невідома помилка')}")

                except Exception as e:
                    st.error(f"Помилка бази даних при оновленні продажу: {e}")

        if cancelled:
            # Скидаємо стан редагування продажу і повертаємось до історії
            st.session_state.editing_sale_id = None
            st.session_state.editing_sale_item_id = None
            st.session_state.viewing_history_item_id = item_data['id'] # Залишаємо ID товару
            st.rerun()

# --- Головна логіка сторінки "Перегляд товарів" ---

st.header("Список товарів")

# Перевіряємо, чи потрібно відобразити форму редагування товару
if st.session_state.get('editing_item_id') is not None:
    item_to_edit = get_item_by_db_id(st.session_state.editing_item_id)
    if item_to_edit:
        display_edit_item_form(item_to_edit)
    else:
        st.error(f"Помилка: не знайдено товар для редагування (ID: {st.session_state.editing_item_id}).")
        st.session_state.editing_item_id = None # Скидаємо стан, якщо товар не знайдено
        if st.button("Повернутись до списку"): # Кнопка для повернення
             st.rerun()

# Перевіряємо, чи потрібно відобразити форму продажу
elif st.session_state.get('selling_item_id') is not None:
    item_to_sell = get_item_by_db_id(st.session_state.selling_item_id)
    if item_to_sell:
        display_sell_item_form(item_to_sell)
    else:
        st.error(f"Помилка: не знайдено товар для продажу (ID: {st.session_state.selling_item_id}).")
        st.session_state.selling_item_id = None
        if st.button("Повернутись до списку"):
             st.rerun()

# Перевіряємо, чи потрібно відобразити історію продажів
elif st.session_state.get('viewing_history_item_id') is not None:
    # Перевіряємо, чи потрібно відобразити форму редагування продажу всередині історії
    if st.session_state.get('editing_sale_id') is not None and \
       st.session_state.get('editing_sale_item_id') == st.session_state.viewing_history_item_id:

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
             st.error(f"Помилка: не знайдено продаж для редагування (Sale ID: {st.session_state.editing_sale_id}).")
             # Скидаємо стан редагування продажу, але залишаємось на історії
             st.session_state.editing_sale_id = None
             st.session_state.editing_sale_item_id = None
             if st.button("Повернутись до історії"):
                  st.rerun()

    # Якщо не редагуємо продаж, показуємо саму історію
    else:
        item_for_history = get_item_by_db_id(st.session_state.viewing_history_item_id)
        if item_for_history:
            display_sales_history(item_for_history)
        else:
            st.error(f"Помилка: не знайдено товар для перегляду історії (ID: {st.session_state.viewing_history_item_id}).")
            st.session_state.viewing_history_item_id = None
            if st.button("Повернутись до списку"):
                 st.rerun()

# Якщо жоден з режимів (редагування, продаж, історія) не активний, показуємо таблицю
else:
    display_items_view()

