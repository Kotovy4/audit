import streamlit as st
import pandas as pd
from datetime import datetime
import io
# Імпортуємо весь модуль apppp
try:
    import apppp
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py'. Переконайтесь, що він існує в кореневій папці.")
    st.stop()


# --- Функція для конвертації DataFrame в Excel ---
def dataframe_to_excel(df):
    """Конвертує Pandas DataFrame у байтовий потік Excel-файлу."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventory')
    processed_data = output.getvalue()
    return processed_data

# --- Функції для відображення форм ---

def display_edit_item_form(item_data):
    """Відображає форму для редагування товару, включаючи вибір країни."""
    st.subheader(f"Редагувати товар: {item_data.get('name', 'Н/Д')}")

    current_country = item_data.get('origin_country')
    if not current_country:
        current_country = "USA"

    country_options = list(apppp.CURRENCY_SETTINGS.keys())
    try:
        current_country_index = country_options.index(current_country)
    except ValueError:
        current_country_index = 0
        current_country = country_options[0]

    selected_country = st.selectbox(
        "Країна походження*",
        options=country_options,
        index=current_country_index,
        key=f"edit_country_select_{item_data['id']}"
    )

    settings = apppp.CURRENCY_SETTINGS[selected_country]
    currency_symbol = settings["symbol"]
    currency_code = settings["code"]
    rate_label = settings["rate_label"]
    current_rate = item_data.get('rate')
    default_rate = current_rate if current_rate and current_rate > 0 else settings["default_rate"]

    with st.form("edit_item_form"):
        name = st.text_input("Назва товару*", value=item_data.get('name', ''), key=f"edit_name_{item_data['id']}")
        initial_quantity = st.number_input("Початкова кількість*", min_value=1, step=1, value=item_data.get('initial_quantity', 1), key=f"edit_qty_{item_data['id']}")

        cost_to_display = item_data.get('cost_original') if item_data.get('origin_country') else item_data.get('cost_usd', 0.0)
        shipping_to_display = item_data.get('shipping_original') if item_data.get('origin_country') else item_data.get('shipping_usd', 0.0)

        cost_original = st.number_input(f"Вартість ({currency_symbol})*", min_value=0.0, step=0.01, format="%.2f", value=float(cost_to_display or 0.0), key=f"edit_cost_original_{item_data['id']}")
        shipping_original = st.number_input(f"Доставка ({currency_symbol})*", min_value=0.0, step=0.01, format="%.2f", value=float(shipping_to_display or 0.0), key=f"edit_shipping_original_{item_data['id']}")
        rate = st.number_input(
            rate_label,
            min_value=0.01,
            step=0.01,
            format="%.4f",
            value=float(default_rate),
            key=f"edit_rate_dynamic_{item_data['id']}"
            )
        customs_uah = st.number_input("Митний платіж (грн)", min_value=0.0, step=0.01, format="%.2f", value=float(item_data.get('customs_uah', 0.0)), key=f"edit_customs_{item_data['id']}")
        description = st.text_area("Опис", value=item_data.get('description', ''), key=f"edit_desc_{item_data['id']}")

        sold_qty, _ = apppp.get_item_sales_info_cached(item_data)
        if sold_qty > 0:
            st.caption(f"(Вже продано: {sold_qty} од.)")

        col1, col2 = st.columns(2)
        with col1:
             submitted = st.form_submit_button("Зберегти зміни")
        with col2:
             cancelled = st.form_submit_button("Скасувати")

        if submitted:
            if not apppp.supabase:
                st.error("Немає підключення до бази даних для збереження змін.")
                return

            # --- Оновлена валідація для редагування ---
            validation_error = False
            error_messages = []
            if not name:
                validation_error = True
                error_messages.append("Назва товару")
            if initial_quantity is None or initial_quantity <= 0:
                 validation_error = True
                 error_messages.append("Початкова кількість (має бути > 0)")
            if rate is None or rate <= 0:
                 validation_error = True
                 error_messages.append(f"{rate_label} (має бути > 0)")
            if cost_original is None: # Дозволяємо 0.0
                 validation_error = True
                 error_messages.append(f"Вартість ({currency_symbol})")
            if shipping_original is None: # Дозволяємо 0.0
                 validation_error = True
                 error_messages.append(f"Доставка ({currency_symbol})")

            if validation_error:
                st.warning(f"Будь ласка, заповніть або перевірте обов'язкові поля: {', '.join(error_messages)}.")
                return # Зупиняємо, якщо є помилка валідації
            # --- Кінець оновленої валідації ---

            # Перевірка кількості (залишається)
            if initial_quantity < sold_qty:
                 st.error(f"Нова початкова кількість ({initial_quantity}) не може бути меншою за вже продану ({sold_qty})!")
                 return

            cost_uah = apppp.calculate_uah_cost(cost_original, shipping_original, rate)
            try:
                update_data = {
                    "name": name,
                    "initial_quantity": initial_quantity,
                    "origin_country": selected_country,
                    "original_currency": currency_code,
                    "cost_original": cost_original,
                    "shipping_original": shipping_original,
                    "rate": rate,
                    "cost_uah": cost_uah,
                    "customs_uah": customs_uah if customs_uah is not None else 0.0, # Перевірка на None
                    "description": description
                }
                response = apppp.supabase.table('items').update(update_data).eq('id', item_data['id']).execute()

                if response.data:
                    st.success(f"Дані товару '{name}' оновлено!")
                    st.cache_data.clear()
                    st.session_state.editing_item_id = None
                    st.rerun()
                else:
                    # Перевіряємо, чи є помилка в відповіді Supabase
                    api_error = getattr(response, 'error', None)
                    if api_error:
                         st.error(f"Помилка при оновленні товару в БД: {api_error}")
                    # Іноді помилка може бути на рівні HTTP або з'єднання
                    elif hasattr(response, 'status_code') and response.status_code >= 400:
                         st.error(f"Помилка при оновленні товару: HTTP {response.status_code}")
                    else:
                         # Якщо даних немає, але й помилки немає (дивно, але можливо)
                         st.warning("Оновлення товару не повернуло даних, але й не повідомило про помилку.")
                         # Все одно скидаємо стан і оновлюємо
                         st.cache_data.clear()
                         st.session_state.editing_item_id = None
                         st.rerun()


            except Exception as e:
                st.error(f"Помилка бази даних при оновленні товару: {e}")
        if cancelled:
             st.session_state.editing_item_id = None
             st.rerun()

def display_sell_item_form(item_data):
    """Відображає форму для продажу одиниць товару."""
    st.subheader(f"Продаж товару: {item_data.get('name', 'Н/Д')}")
    initial_qty = item_data.get('initial_quantity', 0)
    sold_qty, avg_price = apppp.get_item_sales_info_cached(item_data)
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
            cancelled = st.form_submit_button("Скасувати")

        if submitted:
            if not apppp.supabase:
                 st.error("Немає підключення до бази даних для реєстрації продажу.")
                 return

            if not quantity_to_sell or unit_sell_price is None:
                st.warning("Вкажіть кількість та ціну продажу.")
            elif quantity_to_sell > available_qty:
                 st.error(f"Кількість для продажу ({quantity_to_sell}) не може перевищувати доступну ({available_qty}).")
            else:
                try:
                    timestamp = datetime.now().isoformat()
                    response = apppp.supabase.table('sales').insert({
                        "item_id": item_data['id'],
                        "quantity_sold": quantity_to_sell,
                        "price_per_unit_uah": unit_sell_price,
                        "sale_timestamp": timestamp
                    }).execute()

                    if response.data:
                        st.success(f"Продано {quantity_to_sell} од. товару '{item_data.get('name', '')}'.")
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
    st.subheader(f"Історія продажів: {item_data.get('name', 'Н/Д')}")
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
             "Ціна за од. (₴)": apppp.format_currency(sale.get('price_per_unit_uah', 0.0)),
             "Дата/Час": timestamp_display
         })

    df_history = pd.DataFrame(history_display_data)
    st.dataframe(df_history, hide_index=True, use_container_width=True)

    st.write("Дії з вибраним продажем:")
    sale_options = {sale['id']: f"ID: {sale['id']} ({sale.get('quantity_sold', 0)} од. по {apppp.format_currency(sale.get('price_per_unit_uah', 0.0))})" for sale in sales_history}
    selected_sale_id_str = st.selectbox(
         "Виберіть продаж",
         options=list(sale_options.keys()),
         format_func=lambda x: sale_options.get(x, "Невідомий ID"),
         index=0,
         key="sale_selector",
         label_visibility="collapsed"
    )
    selected_sale_id = int(selected_sale_id_str) if selected_sale_id_str else None

    col1, col2, col3 = st.columns([1,1,4])
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
        if st.session_state.confirm_delete_sale_item_id == item_data['id']:
            sale_id_to_delete = st.session_state.confirm_delete_sale_id
            st.warning(f"**Ви впевнені, що хочете видалити запис про продаж ID: {sale_id_to_delete}?**")
            c1, c2, _ = st.columns([1,1,5])
            if c1.button("Так, видалити продаж", key="confirm_delete_sale_yes"):
                item_id_for_update = st.session_state.confirm_delete_sale_item_id
                st.session_state.confirm_delete_sale_id = None
                st.session_state.confirm_delete_sale_item_id = None
                if not apppp.supabase:
                     st.error("Немає підключення до бази даних для видалення продажу.")
                     return
                try:
                    response = apppp.supabase.table('sales').delete().eq('id', sale_id_to_delete).execute()
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
        else:
             st.session_state.confirm_delete_sale_id = None
             st.session_state.confirm_delete_sale_item_id = None

    if st.button("Назад до списку товарів", key="back_from_history"):
        st.session_state.viewing_history_item_id = None
        st.rerun()

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
            cancelled = st.form_submit_button("Скасувати редагування")

        if submitted:
            if not apppp.supabase:
                 st.error("Немає підключення до бази даних для збереження змін продажу.")
                 return
            if not quantity_sold or price_per_unit is None:
                st.warning("Вкажіть кількість та ціну.")
            elif quantity_sold > max_allowed_here:
                 st.error(f"Нова кількість ({quantity_sold}) перевищує максимально допустиму ({max_allowed_here}) для цього продажу.")
            else:
                try:
                    response = apppp.supabase.table('sales').update({
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

# --- Основна функція для відображення списку товарів та кнопок ---
def display_items_view():
    """Відображає список товарів, фільтри, пошук та кнопки дій."""
    col_search, col_filter = st.columns([2, 3])
    with col_search:
        search_term = st.text_input("Пошук за назвою", key="search_input")
    with col_filter:
        filter_status = st.radio(
            "Фільтр:",
            ('all', 'in_stock', 'sold'),
            index=1,
            format_func=lambda x: {'all': 'Усі', 'in_stock': 'В наявності', 'sold': 'Продані'}.get(x, x),
            horizontal=True,
            key="filter_radio"
        )

    all_columns = ["ID", "Назва", "Залишок", "Вартість (₴)", "Мито (₴)", "Сер. ціна продажу (₴/од.)", "Опис"]
    default_columns = ["ID", "Назва", "Залишок", "Вартість (₴)", "Опис"]
    selected_columns = st.multiselect(
        "Виберіть колонки для відображення:",
        options=all_columns,
        default=default_columns,
        key="column_selector"
    )

    items_data = apppp.load_items_from_db()
    filtered_items = []
    search_term_lower = search_term.lower()

    for item in items_data:
        if search_term_lower and search_term_lower not in item.get('name', '').lower():
            continue

        initial_qty = item.get('initial_quantity', 0)
        sold_qty, avg_price = apppp.get_item_sales_info_cached(item)
        remaining_qty = initial_qty - sold_qty
        has_sales = sold_qty > 0

        if filter_status == 'sold' and not has_sales:
            continue
        if filter_status == 'in_stock' and remaining_qty <= 0:
            continue

        item['remaining_qty'] = remaining_qty
        item['has_sales'] = has_sales
        item['can_sell'] = remaining_qty > 0
        item['avg_sell_price'] = avg_price

        filtered_items.append(item)

    if filtered_items:
        display_data = []
        for item in filtered_items:
            item_name = item.get('name')
            display_name = item_name if item_name else 'Без назви'
            row_data = {
                "ID": item['id'],
                "Назва": display_name,
                "Залишок": item['remaining_qty'],
                "Вартість (₴)": apppp.format_currency(item.get('cost_uah', 0.0)),
                "Мито (₴)": apppp.format_currency(item.get('customs_uah', 0.0)),
                "Сер. ціна продажу (₴/од.)": apppp.format_currency(item['avg_sell_price']) if item['has_sales'] else "---",
                "Опис": item.get('description', '')
            }
            display_data.append(row_data)

        df_full = pd.DataFrame(display_data)
        valid_selected_columns = [col for col in selected_columns if col in df_full.columns]
        if not valid_selected_columns:
             valid_selected_columns = ["ID"]
        df_display = df_full[valid_selected_columns]

        st.dataframe(df_display, hide_index=True, use_container_width=True)
        st.markdown("---")

        st.write("Дії з вибраним товаром:")
        item_options = {item['id']: f"{item['id']}: {item.get('name') if item.get('name') else 'Без назви'}" for item in filtered_items}
        current_selection_id = st.session_state.get('selected_item_id', None)
        if current_selection_id not in item_options:
             current_selection_id = None

        default_index = 0
        if current_selection_id and current_selection_id in item_options:
             try:
                 default_index = list(item_options.keys()).index(current_selection_id)
             except ValueError:
                 default_index = 0

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
             selected_item_data = apppp.get_item_by_db_id(selected_id)

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
            can_sell = False
            if selected_item_data:
                 initial_qty = selected_item_data.get('initial_quantity', 0)
                 sold_qty, _ = apppp.get_item_sales_info_cached(selected_item_data)
                 can_sell = (initial_qty - sold_qty) > 0
            if st.button("Продати", key="sell_btn", disabled=not can_sell):
                 st.session_state.selling_item_id = selected_id
                 st.rerun()
        with col4:
            has_sales = False
            if selected_item_data:
                 sold_qty, _ = apppp.get_item_sales_info_cached(selected_item_data)
                 has_sales = sold_qty > 0
            if st.button("Історія продажів", key="history_btn", disabled=not has_sales):
                 st.session_state.viewing_history_item_id = selected_id
                 st.rerun()
        with col5:
             if st.button("Статистика", key="stats_btn"):
                  st.session_state.selected_item_id_for_stats = selected_id
                  st.info("Перейдіть на вкладку 'Статистика' для перегляду.")


        # --- Підтвердження видалення товару ---
        if 'confirm_delete_id' in st.session_state and st.session_state.confirm_delete_id is not None:
             item_to_delete = apppp.get_item_by_db_id(st.session_state.confirm_delete_id)
             item_name = item_to_delete.get('name') if item_to_delete else 'Н/Д'
             display_delete_name = item_name if item_name else 'Без назви'
             st.warning(f"**Ви впевнені, що хочете видалити товар '{display_delete_name}' (ID: {st.session_state.confirm_delete_id}) та всю його історію продажів?**")
             c1, c2, _ = st.columns([1,1,5])
             if c1.button("Так, видалити", key="confirm_delete_yes"):
                  db_id_to_delete = st.session_state.confirm_delete_id
                  st.session_state.confirm_delete_id = None
                  if not apppp.supabase:
                      st.error("Немає підключення до бази даних для видалення.")
                      return
                  try:
                      response = apppp.supabase.table('items').delete().eq('id', db_id_to_delete).execute()
                      st.success(f"Товар '{display_delete_name}' видалено.")
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


# --- Головна логіка сторінки "Перегляд товарів" ---
# st.header("📈 Перегляд товарів") # Заголовок береться з назви файлу

# Перевіряємо, чи потрібно відобразити форму редагування товару
if st.session_state.get('editing_item_id') is not None:
    item_to_edit = apppp.get_item_by_db_id(st.session_state.editing_item_id)
    if item_to_edit:
        display_edit_item_form(item_to_edit)
    else:
        st.error(f"Помилка: не знайдено товар для редагування (ID: {st.session_state.editing_item_id}).")
        st.session_state.editing_item_id = None
        if st.button("Повернутись до списку"):
             st.rerun()

# Перевіряємо, чи потрібно відобразити форму продажу
elif st.session_state.get('selling_item_id') is not None:
    item_to_sell = apppp.get_item_by_db_id(st.session_state.selling_item_id)
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

        item_for_sale_edit = apppp.get_item_by_db_id(st.session_state.editing_sale_item_id)
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
             st.session_state.editing_sale_id = None
             st.session_state.editing_sale_item_id = None
             if st.button("Повернутись до історії"):
                  st.rerun()

    # Якщо не редагуємо продаж, показуємо саму історію
    else:
        item_for_history = apppp.get_item_by_db_id(st.session_state.viewing_history_item_id)
        if item_for_history:
            display_sales_history(item_for_history)
        else:
            st.error(f"Помилка: не знайдено товар для перегляду історії (ID: {st.session_state.viewing_history_item_id}).")
            st.session_state.viewing_history_item_id = None
            if st.button("Повернутись до списку"):
                 st.rerun()

# Якщо жоден з режимів не активний, показуємо таблицю товарів
else:
    display_items_view()

