import streamlit as st
import locale
# Імпортуємо весь модуль apppp
try:
    import apppp
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py'. Переконайтесь, що він існує в кореневій папці.")
    st.stop()

def display_statistics():
    """Відображає вікно статистики з додатковою діагностикою."""
    # st.subheader("Статистика товарів") # Заголовок тепер береться з назви файлу

    # Виправляємо розпакування результату
    items_data, _ = apppp.load_items_from_db(limit=None, offset=None, search_term=None) 
    
    if not items_data:
         st.info("Немає даних для відображення статистики.")
         return

    # Ініціалізуємо суми
    total_initial_items_sum = 0
    total_sold_items_sum = 0
    entries_with_sales = 0
    unsold_entries = 0
    total_expenses = 0.0
    total_income_actual = 0.0
    unsold_items_cost = 0.0

    print("--- Початок розрахунку статистики ---") # Діагностика

    for index, item in enumerate(items_data): # Тепер item - це словник
        print(f"\nОбробка товару ID: {item.get('id')}, Назва: {item.get('name', 'Н/Д')}")

        # --- Розрахунок витрат для поточного товару ---
        item_expense = 0.0
        try:
            initial_qty = item.get('initial_quantity', 0)
            cost_uah = item.get('cost_uah', 0.0)
            customs_uah = item.get('customs_uah', 0.0)

            initial_qty_val = int(initial_qty) if initial_qty is not None else 0
            cost_uah_val = float(cost_uah) if cost_uah is not None else 0.0
            customs_uah_val = float(customs_uah) if customs_uah is not None else 0.0

            print(f"  -> Витрати: cost_uah={cost_uah_val}, customs_uah={customs_uah_val}")

            item_expense = cost_uah_val + customs_uah_val
            total_expenses += item_expense

            unit_cost = item_expense / initial_qty_val if initial_qty_val > 0 else 0
            total_initial_items_sum += initial_qty_val

        except (ValueError, TypeError) as e:
            print(f"  -> ПОМИЛКА розрахунку витрат для товару ID {item.get('id')}: {e}")
            unit_cost = 0

        # --- Розрахунок доходу для поточного товару ---
        item_sold_qty, avg_price = apppp.get_item_sales_info_cached(item)
        item_income = 0.0
        sales_history = item.get('sales_history', [])

        if sales_history:
            entries_with_sales += 1
            print(f"  -> Знайдено {len(sales_history)} записів продажів.")
            for sale_index, sale in enumerate(sales_history):
                try:
                    qty = sale.get('quantity_sold', 0)
                    price = sale.get('price_per_unit_uah', 0.0)

                    qty_val = int(qty) if qty is not None else 0
                    price_val = float(price) if price is not None else 0.0

                    print(f"    -> Продаж {sale_index+1}: qty={qty_val}, price={price_val}")

                    if qty_val > 0 and price_val >= 0:
                         item_income += qty_val * price_val
                    else:
                         print(f"    -> Попередження: Пропуск продажу з некоректними даними (qty={qty_val}, price={price_val})")

                except (ValueError, TypeError) as e:
                    print(f"    -> ПОМИЛКА обробки продажу {sale_index+1} для товару ID {item.get('id')}: {e}")
        else:
            unsold_entries += 1

        total_sold_items_sum += item_sold_qty
        total_income_actual += item_income

        # --- Розрахунок вартості залишку ---
        remaining_qty = initial_qty_val - item_sold_qty
        if remaining_qty > 0:
            unsold_items_cost += remaining_qty * unit_cost

    print(f"--- Кінець розрахунку: Заг.витрати={total_expenses}, Заг.дохід={total_income_actual} ---")

    overall_profit_loss = total_income_actual - total_expenses

    # --- Відображення статистики (використовуємо apppp.format_currency) ---
    st.markdown("#### Загальна статистика")
    col1, col2 = st.columns(2)
    col1.metric("Кількість записів", len(items_data))
    col1.metric("Загальна початкова к-сть од.", total_initial_items_sum)
    col1.metric("Загально продано од.", total_sold_items_sum)
    col2.metric("Записи з продажами", entries_with_sales)
    col2.metric("Записи без продаж", unsold_entries)

    st.markdown("---")
    col1, col2 = st.columns(2)
    col1.metric("Загальні витрати (на всі од.)", apppp.format_currency(total_expenses))
    col1.metric("Загальний дохід (з проданих од.)", apppp.format_currency(total_income_actual))
    col2.metric("Прибуток / Збиток (Дохід - Всі витрати)", apppp.format_currency(overall_profit_loss))
    col2.metric("Вартість одиниць в наявності", apppp.format_currency(unsold_items_cost))

    st.markdown("---")
    st.markdown("#### Статистика останнього вибраного товару")
    selected_item_id = st.session_state.get('selected_item_id_for_stats', None)
    selected_item_data = None
    if selected_item_id:
         selected_item_data = apppp.get_item_by_db_id(selected_item_id)

    if selected_item_data:
        s_initial_qty = selected_item_data.get('initial_quantity', 0)
        s_cost_uah = selected_item_data.get('cost_uah', 0.0)
        s_customs_uah = selected_item_data.get('customs_uah', 0.0)
        s_sales_history = selected_item_data.get('sales_history', [])

        s_cost_uah_val = float(s_cost_uah) if s_cost_uah is not None else 0.0
        s_customs_uah_val = float(s_customs_uah) if s_customs_uah is not None else 0.0
        s_initial_qty_val = int(s_initial_qty) if s_initial_qty is not None else 0

        s_expenses = s_cost_uah_val + s_customs_uah_val
        s_unit_cost = s_expenses / s_initial_qty_val if s_initial_qty_val > 0 else 0
        s_sold_qty, s_avg_sell_price = apppp.get_item_sales_info_cached(selected_item_data)
        s_income = s_sold_qty * s_avg_sell_price if s_sold_qty > 0 else 0.0
        s_remaining_qty = s_initial_qty_val - s_sold_qty
        s_profit_loss = s_income - (s_sold_qty * s_unit_cost) if s_sold_qty > 0 else None

        st.write(f"**Назва:** {selected_item_data.get('name', 'Н/Д')}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Початкова к-сть", s_initial_qty_val)
        col2.metric("Продано к-сть", s_sold_qty)
        col3.metric("Залишок к-сть", s_remaining_qty)

        col1, col2 = st.columns(2)
        col1.metric("Витрати (на весь запис)", apppp.format_currency(s_expenses))
        col2.metric("Витрати на 1 од.", apppp.format_currency(s_unit_cost))
        col1.metric("Середня ціна продажу (за 1 од.)", apppp.format_currency(s_avg_sell_price) if s_sold_qty > 0 else "---")
        col2.metric("Дохід (з проданих од.)", apppp.format_currency(s_income))
        st.metric("Прибуток / Збиток (з проданих)", apppp.format_currency(s_profit_loss) if s_profit_loss is not None else "---")

    else:
        st.info("Товар не вибрано на сторінці 'Перегляд товарів' для детальної статистики.")

# --- Головна частина сторінки ---
display_statistics()

