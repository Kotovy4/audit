import streamlit as st
import locale
# Імпортуємо спільні функції та клієнт supabase з основного файлу
try:
    from apppp import (
        supabase,
        load_items_from_db,
        get_item_by_db_id,
        get_item_sales_info_cached,
        format_currency
    )
except ImportError:
    st.error("Помилка імпорту: Не вдалося знайти основний файл 'apppp.py' або необхідні функції.")
    st.stop()

def display_statistics():
    """Відображає вікно статистики."""
    # st.subheader("Статистика товарів") # Заголовок тепер береться з назви файлу

    items_data = load_items_from_db() # Завантажуємо свіжі дані з кешу/БД
    if not items_data:
         st.info("Немає даних для відображення статистики.")
         return

    total_initial_items_sum = 0
    total_sold_items_sum = 0
    entries_with_sales = 0
    unsold_entries = 0
    total_expenses = 0.0
    total_income_actual = 0.0
    unsold_items_cost = 0.0

    for item in items_data:
        # Історія вже має бути завантажена в item завдяки load_items_from_db
        initial_qty = item.get('initial_quantity', 0)
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
    st.markdown("#### Статистика останнього вибраного товару")
    # Використовуємо ID, збережений у стані сесії з іншої сторінки
    selected_item_id = st.session_state.get('selected_item_id', None)
    selected_item_data = None
    if selected_item_id:
         # Потрібно знайти дані в items_data, які ми завантажили на початку функції
         for item in items_data:
              if item['id'] == selected_item_id:
                   selected_item_data = item
                   break

    if selected_item_data:
        s_initial_qty = selected_item_data.get('initial_quantity', 0)
        s_cost_uah = selected_item_data.get('вартість_uah', 0.0)
        s_customs_uah = selected_item_data.get('мито_uah', 0.0)
        s_sales_history = selected_item_data.get('sales_history', [])

        s_expenses = s_cost_uah + s_customs_uah
        s_unit_cost = s_expenses / s_initial_qty if s_initial_qty > 0 else 0
        s_sold_qty, s_avg_sell_price = get_item_sales_info_cached(selected_item_data)
        s_income = s_sold_qty * s_avg_sell_price if s_sold_qty > 0 else 0.0
        s_remaining_qty = s_initial_qty - s_sold_qty
        s_profit_loss = s_income - (s_sold_qty * s_unit_cost) if s_sold_qty > 0 else None

        st.write(f"**Назва:** {selected_item_data.get('name', 'Н/Д')}")
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
        st.info("Товар не вибрано на сторінці 'Перегляд товарів' для детальної статистики.")

# --- Головна частина сторінки ---
st.header("📊 Статистика")
display_statistics()

