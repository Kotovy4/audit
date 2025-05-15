# main_api.py
from dotenv import load_dotenv # <--- ДОДАНО
load_dotenv() # <--- ДОДАНО

from fastapi import FastAPI, HTTPException
from typing import Union, List, Optional
from pydantic import BaseModel
from supabase import create_client, Client
import os
from datetime import datetime

# --- Налаштування підключення до Supabase ---
# Тепер os.environ.get зможе прочитати значення з .env файлу
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL_HERE")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY_HERE")

if SUPABASE_URL == "YOUR_SUPABASE_URL_HERE" or SUPABASE_KEY == "YOUR_SUPABASE_ANON_KEY_HERE":
    print("ПОПЕРЕДЖЕННЯ: Змінні середовища SUPABASE_URL та SUPABASE_KEY не встановлені або не завантажені з .env. Використовуються заглушки.")
    # Для локального запуску це критично, тому можна навіть зупинити, якщо хочете
    # raise ValueError("Необхідно встановити SUPABASE_URL та SUPABASE_KEY у файлі .env або як змінні середовища")


supabase: Client | None = None
# Перевіряємо, чи значення не є заглушками ПІСЛЯ спроби завантажити з .env
if SUPABASE_URL != "YOUR_SUPABASE_URL_HERE" and SUPABASE_KEY != "YOUR_SUPABASE_ANON_KEY_HERE":
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Успішно підключено до Supabase.")
    except Exception as e:
        print(f"Помилка підключення до Supabase: {e}")
else:
    print("Не вдалося ініціалізувати клієнт Supabase через відсутність URL або ключа.")


# --- Моделі Pydantic ---
class ItemBase(BaseModel):
    name: str
    initial_quantity: Optional[int] = None
    cost_uah: Optional[float] = None
    description: Optional[str] = None
    origin_country: Optional[str] = None
    original_currency: Optional[str] = None
    cost_original: Optional[float] = None
    shipping_original: Optional[float] = None
    rate: Optional[float] = None
    customs_uah: Optional[float] = None

class Item(ItemBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# Створюємо екземпляр FastAPI
app = FastAPI()

# --- Ендпоінти API ---

@app.get("/")
async def read_root():
    return {"message": "Вітаю у вашому FastAPI додатку для обліку товарів!"}

@app.get("/items/{item_id}", response_model=Optional[Item])
async def read_item_from_db(item_id: int):
    """
    Отримує конкретний товар з бази даних Supabase за його ID.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервіс бази даних недоступний (клієнт не ініціалізовано)")
    try:
        response = supabase.table("items").select("*").eq("id", item_id).maybe_single().execute()
        if response.data:
            return response.data
        else:
            raise HTTPException(status_code=404, detail="Товар не знайдено")
    except Exception as e:
        print(f"Помилка отримання товару з БД: {e}")
        raise HTTPException(status_code=500, detail=f"Помилка сервера при отриманні товару: {str(e)}")


@app.get("/products/", response_model=List[Item])
async def get_products_from_db(skip: int = 0, limit: int = 20, search: Optional[str] = None):
    """
    Отримує список товарів з бази даних Supabase з пагінацією та пошуком.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Сервіс бази даних недоступний (клієнт не ініціалізовано)")
    try:
        query = supabase.table("items").select("*")

        if search:
            query = query.ilike('name', f'%{search}%')

        query = query.range(skip, skip + limit - 1)
        
        response = query.order('id').execute()
        
        if response.data:
            return response.data
        else:
            return []
            
    except Exception as e:
        print(f"Помилка отримання списку товарів з БД: {e}")
        raise HTTPException(status_code=500, detail=f"Помилка сервера при отриманні списку товарів: {str(e)}")

# Щоб запустити цей додаток:
# 1. Створіть файл .env у корені проекту з вашими SUPABASE_URL та SUPABASE_KEY
# 2. Виконайте в терміналі: uvicorn main_api:app --reload
