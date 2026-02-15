import asyncio
import json
import os
import re
import logging
import random
import string
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import *
from database import *
from keyboards import *
from states import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= ИНИЦИАЛИЗАЦИЯ БОТА =============
bot = Bot(
    token=token,
    default=DefaultBotProperties(parse_mode="Markdown")
)
dp = Dispatcher(storage=MemoryStorage())

os.makedirs("photos", exist_ok=True)

# ============= ПРОВЕРКА РОЛЕЙ =============
def is_admin(user_id: int) -> bool:
    return user_id == admin_id

def is_manager(user_id: int) -> bool:
    return user_id in manager_ids or user_id == admin_id

# ============= ФУНКЦИИ ФОРМАТИРОВАНИЯ =============
def bold(text: str) -> str:
    return f"*{text.upper()}*"

def format_price(amount: int) -> str:
    return f"{amount:,}₸"

def status_icon(status: str) -> str:
    icons = {
        'новый': '🆕',
        'в работе': '🔄',
        'выполнен': '✅',
        'отменен': '❌'
    }
    return icons.get(status, '📦')

def divider() -> str:
    return "─────────────────────────"

def shop_header() -> str:
    return f"*3500*\n{divider()}"

# ============= ПРОВЕРКА ПОЧТОВОГО ИНДЕКСА =============
def validate_postal_code(code: str) -> bool:
    return bool(re.match(r'^\d{6}$', code.strip()))

# ============= БЕЗОПАСНАЯ ОТПРАВКА ФОТО =============
async def safe_send_photo(message: Message, photo_id: str, caption: str, reply_markup=None):
    try:
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=caption[:1024],
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                text=caption[:4096],
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        await message.answer(
            text=caption[:4096],
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# ============= СТАРТ =============
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await register_user({
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name
    })
    
    await init_brands(initial_brands)
    
    text = f"""
{shop_header()}

*{shop_description.upper()}*

{divider()}
├ 1:1 КАЧЕСТВО
├ ОРИГИНАЛЬНЫЕ МАТЕРИАЛЫ
├ ВСЕ РАЗМЕРЫ 35-46
╰ ДОСТАВКА {delivery_days_min}-{delivery_days_max} ДНЕЙ


{divider()}
*КАК ЗАКАЗАТЬ*
{divider()}
├ 1. ВЫБРАТЬ МОДЕЛЬ
├ 2. ВЫБРАТЬ РАЗМЕР
├ 3. ОФОРМИТЬ ЗАКАЗ
╰ 4. МЕНЕДЖЕР ПОДТВЕРЖДАЕТ
{divider()}"""
    
    await safe_send_photo(
        message,
        menu_image_id,
        text,
        main_menu(
            is_admin(message.from_user.id),
            is_manager(message.from_user.id)
        )
    )

# ============= ПРОМОКОДЫ - КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =============

@dp.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext):
    await state.set_state(PromoStates.waiting_for_promo)
    await message.answer(
        f"{shop_header()}\n*🎫 ВВЕДИТЕ ПРОМОКОД*\n{divider()}\n\n"
        f"Отправьте промокод одним сообщением.\n"
        f"Например: `HAPPY2026`\n\n"
        f"Для отмены отправьте /cancel",
        reply_markup=cancel_kb()
    )

@dp.message(PromoStates.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    promo_code = message.text.strip().upper()
    
    result = await validate_promocode(promo_code, message.from_user.id, 0)
    
    if result['valid']:
        await state.update_data(active_promo=promo_code, promo_discount=result['discount'])
        await message.answer(
            f"{shop_header()}\n*✅ ПРОМОКОД АКТИВИРОВАН!*\n{divider()}\n\n"
            f"Промокод: `{promo_code}`\n"
            f"Скидка: *{result['discount']}%*\n\n"
            f"Скидка будет применена при оформлении заказа."
        )
    else:
        await message.answer(
            f"{shop_header()}\n*❌ ОШИБКА*\n{divider()}\n\n{result['reason']}"
        )
    
    await state.clear()

@dp.message(Command("my_discounts"))
async def cmd_my_discounts(message: Message):
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT discount_level FROM users WHERE user_id = ?", (message.from_user.id,))
        user = await cursor.fetchone()
        base_discount = user['discount_level'] if user else 0
        
        promo_discount = await get_promotion_discount()
        
        cursor = await db.execute("""
            SELECT p.* FROM promocodes p
            WHERE p.is_active = 1 
            AND p.expires_at > CURRENT_TIMESTAMP
            AND p.id NOT IN (
                SELECT promo_code FROM used_promocodes WHERE user_id = ?
            )
            LIMIT 5
        """, (message.from_user.id,))
        available_promos = await cursor.fetchall()
    
    text = f"{shop_header()}\n*🎁 МОИ СКИДКИ*\n{divider()}\n\n"
    text += f"📊 *ПОСТОЯННАЯ СКИДКА:* {base_discount}%\n"
    
    if promo_discount > 0:
        text += f"🔥 *АКЦИОННАЯ СКИДКА:* +{promo_discount}%\n"
    
    text += f"💎 *ИТОГО:* {base_discount + promo_discount}%\n\n"
    
    if available_promos:
        text += f"🎫 *ДОСТУПНЫЕ ПРОМОКОДЫ:*\n"
        for p in available_promos:
            text += f"  • `{p['code']}` - {p['discount']}% (до {p['expires_at'][:10]})\n"
    else:
        text += f"❌ *НЕТ ДОСТУПНЫХ ПРОМОКОДОВ*\n"
    
    text += f"\n{divider()}"
    
    await safe_send_photo(message, menu_image_id, text, promo_keyboard())

# ============= КАТАЛОГ =============
@dp.message(F.text == "🛍 КАТАЛОГ")
async def show_catalog(message: Message):
    products = await get_products()
    brands_list = await get_brands()
    
    if not products:
        text = f"""
{shop_header()}
*ТОВАРОВ НЕТ*
{divider()}
├ ЗАГЛЯНИТЕ ПОЗЖЕ
╰ МЫ ОБНОВЛЯЕМ АССОРТИМЕНТ
{divider()}"""
        
        await safe_send_photo(
            message,
            catalog_image_id,
            text,
            main_menu(
                is_admin(message.from_user.id),
                is_manager(message.from_user.id)
            )
        )
        return
    
    text = f"{shop_header()}\n*ВЫБЕРИТЕ БРЕНД*\n{divider()}"
    
    await safe_send_photo(
        message,
        catalog_image_id,
        text,
        brands_kb(brands_list)
    )

@dp.callback_query(F.data.startswith("brand_"))
async def show_brand_products(callback: CallbackQuery, state: FSMContext):
    brand = callback.data.replace("brand_", "")
    products = await get_products(brand=brand)
    
    if not products:
        await callback.answer(f"❌ НЕТ ТОВАРОВ {brand.upper()}", show_alert=True)
        return
    
    product_ids = [p['id'] for p in products]
    await state.update_data(brand_products=product_ids, current_brand=brand)
    
    await callback.message.delete()
    await show_models_list(callback.message, products, brand)
    await callback.answer()

async def show_models_list(message: Message, products: list, brand: str):
    text = f"""
{shop_header()}
*{brand.upper()}*
{divider()}
╰ ВЫБЕРИТЕ МОДЕЛЬ
{divider()}"""
    
    await safe_send_photo(
        message,
        catalog_image_id,
        text,
        models_kb(products)
    )

@dp.callback_query(F.data.startswith("model_"))
async def show_selected_model(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.replace("model_", ""))
    product = await get_product(product_id)
    
    if not product:
        await callback.answer(f"❌ ТОВАР НЕ НАЙДЕН", show_alert=True)
        return
    
    data = await state.get_data()
    products = await get_products(brand=product['brand'])
    await state.update_data(brand_products=[p['id'] for p in products], current_product=product_id)
    
    await callback.message.delete()
    await show_product(callback.message, product)
    await callback.answer()

@dp.callback_query(F.data.startswith("next_model_"))
@dp.callback_query(F.data.startswith("prev_model_"))
async def navigate_models(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    products = data.get('brand_products', [])
    
    if not products:
        await callback.answer(f"❌ НЕТ ТОВАРОВ", show_alert=True)
        return
    
    current_product_id = data.get('current_product', products[0])
    
    try:
        current_index = products.index(current_product_id)
    except ValueError:
        current_index = 0
    
    if callback.data.startswith("next_model_"):
        next_index = (current_index + 1) % len(products)
    else:
        next_index = (current_index - 1) % len(products)
    
    next_product_id = products[next_index]
    next_product = await get_product(next_product_id)
    
    await state.update_data(current_product=next_product_id)
    await callback.message.delete()
    await show_product(callback.message, next_product)
    await callback.answer()

@dp.callback_query(F.data == "back_to_models")
async def back_to_models(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brand = data.get('current_brand')
    
    if not brand:
        await callback.answer(f"❌ ОШИБКА", show_alert=True)
        return
    
    products = await get_products(brand=brand)
    
    if not products:
        await callback.message.delete()
        await show_catalog(callback.message)
        return
    
    await callback.message.delete()
    await show_models_list(callback.message, products, brand)
    await callback.answer()

async def show_product(message: Message, product: dict):
    photos = json.loads(product['photos'])
    
    text = f"""
{shop_header()}
*{product['brand']}*
*{product['model']}*
{divider()}

*ЦЕНА*
{divider()}
╰ {format_price(product['final_price'])}

*ОПИСАНИЕ*
{divider()}
{product['description'][:150]}

🎨 *РАСЦВЕТКИ*
{divider()}
   ✅ В КАТАЛОГЕ: БАЗОВАЯ РАСЦВЕТКА
   🔄 ДРУГИЕ ЦВЕТА: ПО ЗАПРОСУ
   👨‍💼 УТОЧНЯЙТЕ У МЕНЕДЖЕРА

{divider()}
*РАЗМЕРЫ*
{divider()}
╰ 35-46 EU · ПОД ЗАКАЗ
{divider()}"""
    
    # остальной код...
    
    products = await get_products(brand=product['brand'])
    has_multiple = len(products) > 1
    
    if photos and os.path.exists(photos[0]):
        try:
            photo = FSInputFile(photos[0])
            await message.answer_photo(
                photo,
                caption=text[:1024],
                reply_markup=product_nav(product['id'], has_multiple)
            )
        except:
            await safe_send_photo(
                message,
                catalog_image_id,
                text,
                product_nav(product['id'], has_multiple)
            )
    else:
        await safe_send_photo(
            message,
            catalog_image_id,
            text,
            product_nav(product['id'], has_multiple)
        )

@dp.callback_query(F.data.startswith("select_size_"))
async def select_size(callback: CallbackQuery):
    product_id = int(callback.data.replace("select_size_", ""))
    product = await get_product(product_id)
    
    await callback.message.edit_caption(
        caption=f"{bold(product['brand'])} {bold(product['model'])}\n\n{shop_header()}\n*ВЫБЕРИТЕ РАЗМЕР*\n{divider()}",
        reply_markup=sizes_kb(product_id)
    )

@dp.callback_query(F.data.startswith("size_"))
async def add_to_cart_handler(callback: CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        product_id = int(parts[1])
        size = int(parts[2])
        
        product = await get_product(product_id)
        added = await add_to_cart(callback.from_user.id, product_id, size)
        
        if added:
            await callback.answer(f"✓ {product['model']} {size}", show_alert=False)
            await back_to_product(callback, state)
        else:
            await callback.answer(f"⚠️ УЖЕ В КОРЗИНЕ", show_alert=True)
    except Exception as e:
        logger.error(f"ошибка: {e}")
        await callback.answer(f"❌ ОШИБКА", show_alert=True)

@dp.callback_query(F.data.startswith("back_product_"))
async def back_to_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.replace("back_product_", ""))
    product = await get_product(product_id)
    await callback.message.delete()
    await show_product(callback.message, product)

# ============= КОРЗИНА =============
@dp.message(F.text == "🛒 КОРЗИНА")
@dp.callback_query(F.data == "view_cart")
async def show_cart(event: Message | CallbackQuery):
    user_id = event.from_user.id
    
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        message = event.message
    else:
        message = event
    
    items = await get_cart(user_id)
    
    if not items:
        text = f"""
{shop_header()}
*КОРЗИНА ПУСТА*
{divider()}
├ ДОБАВЬТЕ ТОВАРЫ ИЗ КАТАЛОГА
╰ ИСПОЛЬЗУЙТЕ 🛍 КАТАЛОГ
{divider()}"""
        
        await safe_send_photo(
            message,
            cart_image_id,
            text,
            main_menu(is_admin(user_id), is_manager(user_id))
        )
        return
    
    subtotal = sum(i['price'] for i in items)
    total = subtotal + delivery_price
    
    text = f"{shop_header()}\n*КОРЗИНА*\n{divider()}\n"
    
    for i, item in enumerate(items, 1):
        text += f"\n{i}. {bold(item['brand'])} {bold(item['model'])}"
        text += f"\n   ├ РАЗМЕР: {item['size']}"
        text += f"\n   ╰ ЦЕНА: {format_price(item['price'])}\n"
    
    text += f"""
{divider()}
*ИТОГО: {format_price(total)}*
{divider()}"""
    
    await safe_send_photo(
        message,
        cart_image_id,
        text,
        cart_kb()
    )

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: CallbackQuery):
    await clear_cart(callback.from_user.id)
    await callback.answer(f"🗑 КОРЗИНА ОЧИЩЕНА", show_alert=True)
    await callback.message.delete()
    await show_cart(callback)

# ============= ОФОРМЛЕНИЕ =============
@dp.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext):
    items = await get_cart(callback.from_user.id)
    
    if not items:
        await callback.answer(f"❌ КОРЗИНА ПУСТА", show_alert=True)
        return
    
    await state.update_data(cart_items=items)
    await state.set_state(Checkout.name)
    
    await callback.message.answer(
        text=f"{shop_header()}\n*ВВЕДИТЕ ИМЯ*\n{divider()}",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(Checkout.name)
async def process_name(message: Message, state: FSMContext):
    data = await state.get_data()
    if 'cart_items' not in data:
        await message.answer("❌ ОШИБКА: КОРЗИНА НЕ НАЙДЕНА. НАЧНИТЕ ЗАНОВО.")
        await state.clear()
        return
    
    await state.update_data(name=message.text)
    await state.set_state(Checkout.city)
    
    user = await get_user(message.from_user.id)
    
    if user and user.get('city'):
        await message.answer(
            f"{shop_header()}\n*ИСПОЛЬЗОВАТЬ ГОРОД?*\n{divider()}\n"
            f"├ {bold(user['city'])}\n\n"
            f"├ ВВЕДИТЕ *ДА* / НЕТ ИЛИ НОВЫЙ ГОРОД\n"
            f"╰─────────────────────────",
            reply_markup=cancel_kb()
        )
    else:
        await message.answer(
            f"{shop_header()}\n*ВВЕДИТЕ ГОРОД*\n{divider()}\n"
            f"├ ПРИМЕР: АЛМАТЫ, АСТАНА, МОСКВА\n"
            f"╰─────────────────────────",
            reply_markup=cancel_kb()
        )

@dp.message(Checkout.city)
async def process_city(message: Message, state: FSMContext):
    data = await state.get_data()
    if 'cart_items' not in data:
        await message.answer("❌ ОШИБКА: КОРЗИНА НЕ НАЙДЕНА. НАЧНИТЕ ЗАНОВО.")
        await state.clear()
        return
    
    city = message.text.strip()
    
    if city.lower() == "да":
        user = await get_user(message.from_user.id)
        if user and user.get('city'):
            city = user['city']
    
    await state.update_data(city=city)
    await update_user_profile(message.from_user.id, city=city)
    await state.set_state(Checkout.postal_code)
    
    user = await get_user(message.from_user.id)
    
    if user and user.get('postal_code'):
        await message.answer(
            f"{shop_header()}\n*ИСПОЛЬЗОВАТЬ ИНДЕКС?*\n{divider()}\n"
            f"├ {bold(user['postal_code'])}\n\n"
            f"├ ВВЕДИТЕ *ДА* / НЕТ ИЛИ НОВЫЙ ИНДЕКС\n"
            f"╰─────────────────────────",
            reply_markup=cancel_kb()
        )
    else:
        await message.answer(
            f"{shop_header()}\n*ВВЕДИТЕ ПОЧТОВЫЙ ИНДЕКС*\n{divider()}\n"
            f"├ 6 ЦИФР\n"
            f"├ ПРИМЕР: 050000, 101000\n"
            f"╰─────────────────────────",
            reply_markup=cancel_kb()
        )

@dp.message(Checkout.postal_code)
async def process_postal_code(message: Message, state: FSMContext):
    data = await state.get_data()
    if 'cart_items' not in data:
        await message.answer("❌ ОШИБКА: КОРЗИНА НЕ НАЙДЕНА. НАЧНИТЕ ЗАНОВО.")
        await state.clear()
        return
    
    code = message.text.strip()
    
    if code.lower() == "да":
        user = await get_user(message.from_user.id)
        if user and user.get('postal_code'):
            code = user['postal_code']
    
    if not validate_postal_code(code):
        await message.answer(
            f"{shop_header()}\n*ОШИБКА*\n{divider()}\n"
            f"╰ ИНДЕКС ДОЛЖЕН БЫТЬ 6 ЦИФР\n"
            f"├ ПРИМЕР: 050000, 101000\n"
            f"╰─────────────────────────",
            reply_markup=cancel_kb()
        )
        return
    
    await state.update_data(postal_code=code)
    await update_user_profile(message.from_user.id, postal_code=code)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🎫 Ввести промокод", callback_data="enter_promo_checkout"),
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_promo")
    )
    
    await message.answer(
        f"{shop_header()}\n*🎫 ПРОМОКОД*\n{divider()}\n\n"
        f"У вас есть промокод на скидку?",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "enter_promo_checkout")
async def enter_promo_checkout(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Checkout.promo_code)
    await callback.message.answer(
        f"{shop_header()}\n*🎫 ВВЕДИТЕ ПРОМОКОД*\n{divider()}\n\n"
        f"Отправьте промокод одним сообщением\n"
        f"Или отправьте 0 чтобы пропустить",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(Checkout.promo_code)
async def process_checkout_promo(message: Message, state: FSMContext):
    promo_text = message.text.strip()
    
    if promo_text == "0":
        await show_final_checkout(message, state, None)
        return
    
    data = await state.get_data()
    items = data.get('cart_items', [])
    subtotal = sum(i['price'] for i in items)
    
    result = await validate_promocode(promo_text, message.from_user.id, subtotal)
    
    if result['valid']:
        await state.update_data(promo_code=promo_text, promo_discount=result['discount'])
        await show_final_checkout(message, state, result['discount'])
    else:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="enter_promo_checkout"),
            InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_promo")
        )
        
        await message.answer(
            f"{shop_header()}\n*❌ ОШИБКА*\n{divider()}\n\n"
            f"{result['reason']}\n\n"
            f"Попробуйте другой промокод или пропустите этот шаг.",
            reply_markup=kb.as_markup()
        )

@dp.callback_query(F.data == "skip_promo")
async def skip_promo(callback: CallbackQuery, state: FSMContext):
    await show_final_checkout(callback.message, state, None)
    await callback.answer()

async def show_final_checkout(message: Message, state: FSMContext, discount: int = None):
    data = await state.get_data()
    items = data['cart_items']
    
    subtotal = sum(i['price'] for i in items)
    discount_amount = int(subtotal * discount / 100) if discount else 0
    total = subtotal + delivery_price - discount_amount
    
    await state.update_data(
        discount_amount=discount_amount,
        final_total=total
    )
    
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += f"\n{i}. {bold(item['brand'])} {bold(item['model'])}"
        items_text += f"\n   ├ РАЗМЕР: {item['size']}"
        items_text += f"\n   ╰ ЦЕНА: {format_price(item['price'])}\n"
    
    text = f"""
{shop_header()}
*ПРОВЕРКА ЗАКАЗА*
{divider()}
{items_text}
{divider()}"""
    
    if discount:
        text += f"""
*СКИДКА: {discount}%*
├ БЫЛО: {format_price(subtotal)}
├ СКИДКА: -{format_price(discount_amount)}
╰────────────────────────
"""
    
    text += f"""
*ИТОГО: {format_price(total)}*

{divider()}
*ДАННЫЕ*
{divider()}
├ ПОЛУЧАТЕЛЬ: {data['name']}
├ ГОРОД: {data['city']}
╰ ИНДЕКС: {data['postal_code']}
{divider()}"""
    
    await message.answer(text, reply_markup=checkout_kb())

# ============= ПОДТВЕРЖДЕНИЕ ЗАКАЗА =============
@dp.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    if 'cart_items' not in data:
        await callback.answer("❌ ОШИБКА: КОРЗИНА НЕ НАЙДЕНА", show_alert=True)
        await state.clear()
        return
    
    items = data['cart_items']
    promo_code = data.get('promo_code')
    promo_discount = data.get('promo_discount', 0)
    
    subtotal = sum(i['price'] for i in items)
    discount_amount = int(subtotal * promo_discount / 100) if promo_discount else 0
    total = subtotal + delivery_price - discount_amount
    
    order_number = await create_order(
        callback.from_user.id,
        items,
        data['city'],
        data['postal_code'],
        data['name']
    )
    
    if promo_code:
        await use_promocode(promo_code, callback.from_user.id, order_number, promo_discount)
    
    await clear_cart(callback.from_user.id)
    await state.clear()
    
    await callback.message.edit_text(f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ПОДТВЕРЖДЕН ✓*
{divider()}

*ЧТО ДАЛЬШЕ?*
{divider()}
├ 1. МЕНЕДЖЕР ПОДТВЕРЖДАЕТ ЗАКАЗ
├ 2. ОПЛАТА ЧЕРЕЗ @CRYPTOBOT
├ 4. ОТПРАВКА ИЗ КИТАЯ ({delivery_days_min}-{delivery_days_max} ДНЕЙ)
├ 5. УВЕДОМЛЕНИЕ О ПРИБЫТИИ
╰ 6. ОТЗЫВ
{divider()}""")
    
    order = await get_order(order_number)
    user = callback.from_user
    items_data = json.loads(order['items'])
    
    items_text = ""
    for i, item in enumerate(items_data, 1):
        items_text += f"\n{i}. {bold(item['brand'])} {bold(item['model'])} ({item['size']}) - {item['price']}₸"
    
    discount_text = f"\n💰 СКИДКА: -{discount_amount}₸ ({promo_discount}%)" if discount_amount else ""
    
    manager_text = f"""
{shop_header()}
*НОВЫЙ ЗАКАЗ {order_number}*
{divider()}

├ 👤 @{user.username or '—'} · {user.id}
├ 🏙 {order['delivery_city']}
├ 📮 ИНДЕКС: {order['delivery_postal_code']}
├ 📦 АДРЕС: {order['delivery_address']}

{divider()}
*ТОВАРЫ*
{divider()}
{items_text}

{divider()}
*СУММА: {format_price(order['total_amount'])}*
{discount_text}
{divider()}"""
    
    for manager_id in manager_ids:
        try:
            await bot.send_message(
                manager_id,
                manager_text,
                reply_markup=order_actions(order_number, user.id, user.username)
            )
        except Exception as e:
            logger.error(f"ошибка отправки менеджеру {manager_id}: {e}")
    
    await bot.send_message(
        admin_id,
        f"{shop_header()}\n*ЗАКАЗ {order_number}*\n╰ ОТПРАВЛЕН {len(manager_ids)} МЕНЕДЖЕРАМ\n{divider()}"
    )

# ============= МОИ ЗАКАЗЫ =============
@dp.message(F.text == "📦 ЗАКАЗЫ")
@dp.callback_query(F.data == "my_orders")
async def my_orders(event: Message | CallbackQuery):
    user_id = event.from_user.id
    
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        message = event.message
    else:
        message = event
    
    orders = await get_orders()
    orders = [o for o in orders if o['user_id'] == user_id][:5]
    
    if not orders:
        text = f"{shop_header()}\n*У ВАС НЕТ ЗАКАЗОВ*\n{divider()}"
        await safe_send_photo(
            message,
            orders_image_id,
            text,
            main_menu(is_admin(user_id), is_manager(user_id))
        )
        return
    
    text = f"{shop_header()}\n*МОИ ЗАКАЗЫ*\n{divider()}\n"
    
    for o in orders:
        icon = status_icon(o['status'])
        items = json.loads(o['items'])
        text += f"\n{icon} {bold(o['order_number'])}"
        text += f"\n   ├ {len(items)} ТОВАРОВ"
        text += f"\n   ├ {format_price(o['total_amount'])}"
        text += f"\n   ╰ {o['created_at'][:16]}\n"
    
    text += f"{divider()}"
    
    await safe_send_photo(
        message,
        orders_image_id,
        text,
        main_menu(is_admin(user_id), is_manager(user_id))
    )

# ============= МЕНЕДЖЕР: ЗАКАЗЫ =============
@dp.message(F.text == "📋 МЕНЕДЖЕР")
@dp.message(F.text == "📋 МОИ ЗАКАЗЫ")
async def manager_my_orders(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer(f"{shop_header()}\n*НЕТ ДОСТУПА*\n{divider()}")
        return
    
    my_orders = await get_orders(manager_id=message.from_user.id)
    
    if not my_orders:
        text = f"{shop_header()}\n*У ВАС НЕТ АКТИВНЫХ ЗАКАЗОВ*\n{divider()}"
        await safe_send_photo(
            message,
            orders_image_id,
            text,
            manager_menu()
        )
        return
    
    text = f"{shop_header()}\n*МОИ ЗАКАЗЫ ({len(my_orders)})*\n{divider()}\n"
    
    for o in my_orders[:10]:
        icon = status_icon(o['status'])
        items = json.loads(o['items'])
        text += f"\n{icon} {bold(o['order_number'])}"
        text += f"\n   ├ @{o['username'] or '—'}"
        text += f"\n   ├ {format_price(o['total_amount'])}"
        text += f"\n   ╰ {o['created_at'][:16]}\n"
    
    text += f"{divider()}"
    
    await safe_send_photo(
        message,
        orders_image_id,
        text,
        manager_order_list(my_orders)
    )

@dp.message(F.text == "🆕 НОВЫЕ ЗАКАЗЫ")
async def manager_new_orders(message: Message):
    if not is_manager(message.from_user.id):
        await message.answer(f"{shop_header()}\n*НЕТ ДОСТУПА*\n{divider()}")
        return
    
    new_orders = await get_orders(status='новый')
    
    text = f"""
{shop_header()}
*НОВЫЕ ЗАКАЗЫ*
{divider()}
╰ 🆕 НОВЫХ: {len(new_orders)}
{divider()}"""
    
    await safe_send_photo(
        message,
        orders_image_id,
        text,
        manager_order_list(new_orders)
    )

@dp.message(F.text == "📦 ВСЕ ЗАКАЗЫ")
async def manager_all_orders(message: Message):
    if not is_manager(message.from_user.id):
        return
    
    orders = await get_orders()
    
    text = f"{shop_header()}\n*ВСЕ ЗАКАЗЫ*\n{divider()}\n"
    
    for o in orders[:10]:
        icon = status_icon(o['status'])
        text += f"\n{icon} {bold(o['order_number'])}"
        text += f"\n   ├ @{o['username'] or '—'}"
        text += f"\n   ├ {format_price(o['total_amount'])}"
        text += f"\n   ├ {o['status'].upper()}"
        text += f"\n   ╰ {o['created_at'][:16]}\n"
    
    text += f"{divider()}"
    
    await safe_send_photo(
        message,
        orders_image_id,
        text,
        back_kb("back_manager")
    )

@dp.callback_query(F.data.startswith("view_order_"))
async def view_order(callback: CallbackQuery):
    if not is_manager(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    order_number = callback.data.replace("view_order_", "")
    order = await get_order(order_number)
    
    if not order:
        await callback.answer(f"❌ ЗАКАЗ НЕ НАЙДЕН", show_alert=True)
        return
    
    items = json.loads(order['items'])
    
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += f"\n{i}. {bold(item['brand'])} {bold(item['model'])}"
        items_text += f"\n   ├ РАЗМЕР: {item['size']}"
        items_text += f"\n   ╰ ЦЕНА: {format_price(item['price'])}\n"
    
    text = f"""
{shop_header()}
*ЗАКАЗ {order['order_number']}*
╰ {status_icon(order['status'])} *{order['status'].upper()}*
{divider()}

├ 👤 {bold(order['customer_name'])}
├ 📱 @{order['username'] or '—'}
├ 🏙 {order['delivery_city']}
├ 📮 ИНДЕКС: {order['delivery_postal_code']}
├ 📦 АДРЕС: {order['delivery_address']}

{divider()}
*ТОВАРЫ*
{divider()}
{items_text}
{divider()}
*СУММА: {format_price(order['total_amount'])}*
{divider()}

├ 📅 {order['created_at'][:16]}
{divider()}"""
    
    await callback.message.edit_text(
        text,
        reply_markup=order_actions(order_number, order['user_id'], order['username'])
    )

@dp.callback_query(F.data.startswith("take_"))
async def take_order_handler(callback: CallbackQuery, state: FSMContext):
    if not is_manager(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    order_number = callback.data.replace("take_", "")
    await take_order(order_number, callback.from_user.id)
    
    await state.update_data(current_order=order_number)
    
    await callback.answer(f"✅ ЗАКАЗ ВЗЯТ В РАБОТУ", show_alert=True)
    
    order = await get_order(order_number)
    
    await bot.send_message(
        admin_id,
        f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ВЗЯТ В РАБОТУ* ✓
{divider()}

├ 👨‍💼 МЕНЕДЖЕР: @{callback.from_user.username or '—'}
├ 👤 КЛИЕНТ: @{order['username'] or '—'}
├ 💰 СУММА: {format_price(order['total_amount'])}
{divider()}"""
    )
    
    menu_text = f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ВЗЯТ В РАБОТУ* ✓
{divider()}

├ 👤 КЛИЕНТ: @{order['username'] or '—'}
├ 🏙 ГОРОД: {order['delivery_city']}
├ 📮 ИНДЕКС: {order['delivery_postal_code']}
├ 💰 СУММА: {format_price(order['total_amount'])}
{divider()}

*МЕНЮ РАБОТЫ С ЗАКАЗОМ*
{divider()}"""
    
    await safe_send_photo(
        callback.message,
        orders_image_id,
        menu_text,
        manager_order_work_menu(order_number)
    )
    
    await view_order(callback)

@dp.callback_query(F.data.startswith("complete_"))
async def complete_order_handler(callback: CallbackQuery):
    if not is_manager(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    order_number = callback.data.replace("complete_", "")
    await complete_order(order_number, callback.from_user.id)
    
    await callback.answer(f"✅ ЗАКАЗ ВЫПОЛНЕН", show_alert=True)
    
    order = await get_order(order_number)
    
    await bot.send_message(
        admin_id,
        f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ВЫПОЛНЕН* 🎉
{divider()}

├ 👨‍💼 @{callback.from_user.username or '—'}
├ 👤 @{order['username'] or '—'}
├ 💰 {format_price(order['total_amount'])}
{divider()}"""
    )
    
    await bot.send_message(
        order['user_id'],
        f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ВЫПОЛНЕН* 🎉
{divider()}

├ ✅ ВАШ ЗАКАЗ ДОСТАВЛЕН
├ 🇨🇳 ИЗ КИТАЯ
╰────────────────────────
  ╰ *СПАСИБО ЗА ПОКУПКУ!*
{divider()}"""
    )
    
    await view_order(callback)

@dp.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_handler(callback: CallbackQuery):
    if not is_manager(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    order_number = callback.data.replace("cancel_order_", "")
    await cancel_order(order_number, callback.from_user.id)
    
    await callback.answer(f"❌ ЗАКАЗ ОТМЕНЕН", show_alert=True)
    
    order = await get_order(order_number)
    
    await bot.send_message(
        admin_id,
        f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ОТМЕНЕН* ❌
{divider()}

├ 👨‍💼 @{callback.from_user.username or '—'}
├ 👤 @{order['username'] or '—'}
├ 💰 {format_price(order['total_amount'])}
{divider()}"""
    )
    
    await bot.send_message(
        order['user_id'],
        f"""
{shop_header()}
*ЗАКАЗ {order_number}*
╰ *ОТМЕНЕН* ❌
{divider()}

├ СВЯЖИТЕСЬ С МЕНЕДЖЕРОМ:
├ @{callback.from_user.username or 'МЕНЕДЖЕР'}
{divider()}"""
    )
    
    await view_order(callback)

@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(callback: CallbackQuery, state: FSMContext):
    if not is_manager(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    parts = callback.data.split("_")
    order_number = parts[1]
    user_id = int(parts[2])
    
    await state.update_data(reply_order=order_number, reply_user=user_id)
    await state.set_state(Reply.text)
    
    await callback.message.answer(
        f"{shop_header()}\n*НАПИШИТЕ СООБЩЕНИЕ*\n{divider()}",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(Reply.text)
async def reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    
    try:
        await bot.send_message(
            data['reply_user'],
            f"""
{shop_header()}
*ОТВЕТ ОТ МЕНЕДЖЕРА*
╰ *ЗАКАЗ {data['reply_order']}*
{divider()}

{message.text}
{divider()}

╰ — {message.from_user.full_name}
{divider()}"""
        )
        
        await message.answer(f"{shop_header()}\n*СООБЩЕНИЕ ОТПРАВЛЕНО*\n{divider()}")
        
        await bot.send_message(
            admin_id,
            f"""
{shop_header()}
*ОТВЕТ КЛИЕНТУ*
╰ *ЗАКАЗ {data['reply_order']}*
{divider()}

├ 👨‍💼 @{message.from_user.username or '—'}
├ 💬 {message.text[:50]}...
{divider()}"""
        )
        
    except Exception as e:
        await message.answer(f"{shop_header()}\n*ОШИБКА*\n╰ {str(e)}\n{divider()}")
    
    await state.clear()

@dp.callback_query(F.data == "manager_orders")
async def back_to_manager_orders(callback: CallbackQuery):
    await callback.message.delete()
    await manager_new_orders(callback.message)

# ============= АДМИН: УПРАВЛЕНИЕ БРЕНДАМИ =============
@dp.message(F.text == "⚙️ АДМИН")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{shop_header()}\n*НЕТ ДОСТУПА*\n{divider()}")
        return
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*АДМИН ПАНЕЛЬ*\n{divider()}",
        admin_menu()
    )

@dp.message(F.text == "🏷 УПРАВЛЕНИЕ БРЕНДАМИ")
async def manage_brands(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    brands_list = await get_brands()
    
    text = f"""
{shop_header()}
*УПРАВЛЕНИЕ БРЕНДАМИ*
{divider()}
╰ ТЕКУЩИЕ БРЕНДЫ: {len(brands_list)}

"""
    for i, brand in enumerate(brands_list[:10], 1):
        text += f"{i}. {bold(brand.upper())}\n"
    
    text += f"{divider()}"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        brands_management_kb()
    )

@dp.callback_query(F.data == "add_brand")
async def add_brand_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    await state.set_state(AddBrand.name)
    
    await callback.message.answer(
        text=f"{shop_header()}\n*ВВЕДИТЕ НАЗВАНИЕ БРЕНДА*\n{divider()}",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(AddBrand.name)
async def add_brand_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    brand_name = message.text.strip().lower()
    
    if len(brand_name) < 2:
        await message.answer(
            f"{shop_header()}\n*ОШИБКА*\n{divider()}\n"
            f"╰ НАЗВАНИЕ СЛИШКОМ КОРОТКОЕ\n"
            f"{divider()}",
            reply_markup=cancel_kb()
        )
        return
    
    success = await add_brand(brand_name)
    
    if success:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*БРЕНД ДОБАВЛЕН*\n{divider()}\n╰ {bold(brand_name.upper())}\n{divider()}",
            back_kb("back_brands_management")
        )
    else:
        await message.answer(
            f"{shop_header()}\n*ОШИБКА*\n{divider()}\n"
            f"╰ ТАКОЙ БРЕНД УЖЕ СУЩЕСТВУЕТ\n"
            f"{divider()}",
            reply_markup=cancel_kb()
        )
    
    await state.clear()

@dp.callback_query(F.data == "delete_brand")
async def delete_brand_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    brands_list = await get_brands()
    
    if len(brands_list) <= 1:
        await callback.message.answer(
            text=f"{shop_header()}\n*НЕЛЬЗЯ УДАЛИТЬ*\n{divider()}\n╰ ПОСЛЕДНИЙ БРЕНД\n{divider()}",
            reply_markup=back_kb("back_brands_management")
        )
        await callback.answer()
        return
    
    await callback.message.answer(
        text=f"{shop_header()}\n*ВЫБЕРИТЕ БРЕНД ДЛЯ УДАЛЕНИЯ*\n{divider()}\n\n╰ ⚠️ ТОЛЬКО БРЕНДЫ БЕЗ ТОВАРОВ\n{divider()}",
        reply_markup=brands_list_kb(brands_list, "delete_brand")
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_brand_"))
async def delete_brand_process(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    brand_name = callback.data.replace("delete_brand_", "")
    success = await delete_brand(brand_name)
    
    if success:
        text = f"{shop_header()}\n*БРЕНД УДАЛЕН*\n{divider()}\n╰ {bold(brand_name.upper())}\n{divider()}"
    else:
        text = f"{shop_header()}\n*НЕЛЬЗЯ УДАЛИТЬ*\n{divider()}\n╰ У БРЕНДА ЕСТЬ ТОВАРЫ\n{divider()}"
    
    await callback.message.answer(
        text=text,
        reply_markup=back_kb("back_brands_management")
    )
    await callback.answer()

@dp.callback_query(F.data == "back_brands_management")
async def back_brands_management(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.delete()
    await manage_brands(callback.message)

# ============= АДМИН: ДОБАВЛЕНИЕ ТОВАРА =============
@dp.message(F.text == "➕ ДОБАВИТЬ ТОВАР")
async def add_product_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    brands_list = await get_brands()
    
    if not brands_list:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*СНАЧАЛА ДОБАВЬТЕ БРЕНД*\n{divider()}",
            back_kb("back_admin")
        )
        return
    
    await state.set_state(AddProduct.brand)
    
    b = InlineKeyboardBuilder()
    for brand in brands_list:
        b.button(text=brand.upper(), callback_data=f"add_brand_product_{brand}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel"))
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*ВЫБЕРИТЕ БРЕНД*\n{divider()}",
        b.as_markup()
    )

@dp.callback_query(F.data.startswith("add_brand_product_"), AddProduct.brand)
async def add_product_brand(callback: CallbackQuery, state: FSMContext):
    brand = callback.data.replace("add_brand_product_", "")
    await state.update_data(brand=brand)
    await state.set_state(AddProduct.model)
    
    await callback.message.answer(
        text=f"{shop_header()}\n*ВВЕДИТЕ МОДЕЛЬ*\n{divider()}",
        reply_markup=cancel_kb()
    )

@dp.message(AddProduct.model)
async def add_product_model(message: Message, state: FSMContext):
    await state.update_data(model=message.text)
    await state.set_state(AddProduct.base_price)
    
    await message.answer(
        f"{shop_header()}\n*ВВЕДИТЕ СЕБЕСТОИМОСТЬ (₸)*\n{divider()}",
        reply_markup=cancel_kb()
    )

@dp.message(AddProduct.base_price)
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(base_price=price, markup=markup_percent)
        await state.set_state(AddProduct.description)
        
        await message.answer(
            f"{shop_header()}\n*ВВЕДИТЕ ОПИСАНИЕ*\n{divider()}\n"
            f"├ ЦВЕТ\n"
            f"├ МАТЕРИАЛЫ\n"
            f"╰ ОСОБЕННОСТИ\n"
            f"{divider()}",
            reply_markup=cancel_kb()
        )
    except ValueError:
        await message.answer(
            f"{shop_header()}\n*ОШИБКА*\n{divider()}\n"
            f"╰ ВВЕДИТЕ ЧИСЛО\n"
            f"{divider()}",
            reply_markup=cancel_kb()
        )

@dp.message(AddProduct.description)
async def add_product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.photos)
    
    await message.answer(
        f"{shop_header()}\n*ОТПРАВЬТЕ ФОТОГРАФИЮ*\n{divider()}",
        reply_markup=cancel_kb()
    )

@dp.message(F.photo, AddProduct.photos)
async def add_product_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    
    file = await bot.get_file(message.photo[-1].file_id)
    timestamp = datetime.now().timestamp()
    safe_brand = data['brand'].replace(' ', '_')
    safe_model = data['model'].replace(' ', '_')
    file_path = f"photos/{safe_brand}_{safe_model}_{timestamp}.jpg"
    await bot.download_file(file.file_path, file_path)
    
    product_data = {
        'brand': data['brand'],
        'model': data['model'],
        'base_price': data['base_price'],
        'description': data['description'],
        'markup': data['markup'],
        'photos': [file_path]
    }
    
    product_id = await add_product(product_data)
    await state.clear()
    
    final_price = int(data['base_price'] * (1 + data['markup']/100))
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"""
{shop_header()}
*ТОВАР ДОБАВЛЕН*
{divider()}
╰ {bold(f'{data["brand"].upper()} {data["model"].upper()}')}

├ 💰 {format_price(final_price)}
├ 🆔 #{product_id}
{divider()}""",
        admin_menu()
    )

# ============= АДМИН: УПРАВЛЕНИЕ ТОВАРАМИ =============
@dp.message(F.text == "📋 УПРАВЛЕНИЕ ТОВАРАМИ")
async def admin_manage_products(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    products = await get_products()
    
    if not products:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*НЕТ ТОВАРОВ*\n{divider()}",
            back_kb("back_admin")
        )
        return
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*УПРАВЛЕНИЕ ТОВАРАМИ*\n{divider()}",
        admin_products_kb(products)
    )

@dp.callback_query(F.data.startswith("admin_product_"))
async def admin_view_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    product_id = int(callback.data.replace("admin_product_", ""))
    product = await get_product(product_id)
    
    if not product:
        await callback.answer(f"❌ ТОВАР НЕ НАЙДЕН", show_alert=True)
        return
    
    photos = json.loads(product['photos'])
    
    text = f"""
{shop_header()}
*{product['brand'].upper()} {product['model'].upper()}*
{divider()}

├ 💰 ЦЕНА: {format_price(product['final_price'])}

{divider()}
{product['description']}
{divider()}

├ 📅 {product['added_date'][:16]}
├ 🆔 #{product['id']}
{divider()}"""
    
    if photos and os.path.exists(photos[0]):
        photo = FSInputFile(photos[0])
        await callback.message.delete()
        await callback.message.answer_photo(
            photo,
            caption=text,
            reply_markup=admin_product_kb(product_id)
        )
    else:
        await callback.message.answer(
            text=text,
            reply_markup=admin_product_kb(product_id)
        )

@dp.callback_query(F.data.startswith("delete_product_"))
async def admin_delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    product_id = int(callback.data.replace("delete_product_", ""))
    
    product = await get_product(product_id)
    if product:
        photos = json.loads(product['photos'])
        for photo in photos:
            try:
                if os.path.exists(photo):
                    os.remove(photo)
            except:
                pass
    
    await delete_product(product_id)
    await callback.answer(f"✓ ТОВАР УДАЛЕН", show_alert=True)
    await callback.message.delete()

@dp.callback_query(F.data == "admin_add_product")
async def admin_add_product_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    await callback.message.delete()
    await add_product_start(callback.message, state)

@dp.callback_query(F.data == "admin_products_list")
async def admin_back_to_products_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.delete()
    await admin_manage_products(callback.message)

# ============= АДМИН: УПРАВЛЕНИЕ ЗАКАЗАМИ =============
@dp.message(F.text == "📦 УПРАВЛЕНИЕ ЗАКАЗАМИ")
async def admin_orders_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{shop_header()}\n*НЕТ ДОСТУПА*\n{divider()}")
        return
    
    text = f"{shop_header()}\n*УПРАВЛЕНИЕ ЗАКАЗАМИ*\n{divider()}\n├ ВЫБЕРИТЕ РАЗДЕЛ\n╰─────────────────────────"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        admin_orders_menu()
    )

@dp.message(F.text == "📋 ВСЕ ЗАКАЗЫ")
async def admin_all_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    orders = await get_orders()
    
    if not orders:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*ЗАКАЗОВ НЕТ*\n{divider()}",
            back_kb("back_admin_orders")
        )
        return
    
    for order in orders[:20]:
        if order.get('manager_id'):
            try:
                manager = await bot.get_chat(order['manager_id'])
                order['manager_name'] = manager.username or f"id{order['manager_id']}"
            except:
                order['manager_name'] = f"id{order['manager_id']}"
    
    text = f"{shop_header()}\n*ВСЕ ЗАКАЗЫ ({len(orders[:20])}/{len(orders)})*\n{divider()}\n"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        order_list_kb(orders[:20], "admin_view_order")
    )

@dp.message(F.text == "🆕 НОВЫЕ ЗАКАЗЫ")
async def admin_new_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    orders = await get_orders(status='новый')
    
    if not orders:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*НОВЫХ ЗАКАЗОВ НЕТ*\n{divider()}",
            back_kb("back_admin_orders")
        )
        return
    
    text = f"{shop_header()}\n*НОВЫЕ ЗАКАЗЫ ({len(orders)})*\n{divider()}\n"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        order_list_kb(orders, "admin_view_order")
    )

@dp.message(F.text == "🔄 В РАБОТЕ")
async def admin_processing_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    orders = await get_orders(status='в работе')
    
    if not orders:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*ЗАКАЗОВ В РАБОТЕ НЕТ*\n{divider()}",
            back_kb("back_admin_orders")
        )
        return
    
    for order in orders:
        if order.get('manager_id'):
            try:
                manager = await bot.get_chat(order['manager_id'])
                order['manager_name'] = manager.username or f"id{order['manager_id']}"
            except:
                order['manager_name'] = f"id{order['manager_id']}"
    
    text = f"{shop_header()}\n*ЗАКАЗЫ В РАБОТЕ ({len(orders)})*\n{divider()}\n"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        order_list_kb(orders, "admin_view_order")
    )

@dp.message(F.text == "✅ ВЫПОЛНЕННЫЕ")
async def admin_completed_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    orders = await get_orders(status='выполнен')
    
    if not orders:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*ВЫПОЛНЕННЫХ ЗАКАЗОВ НЕТ*\n{divider()}",
            back_kb("back_admin_orders")
        )
        return
    
    for order in orders:
        if order.get('manager_id'):
            try:
                manager = await bot.get_chat(order['manager_id'])
                order['manager_name'] = manager.username or f"id{order['manager_id']}"
            except:
                order['manager_name'] = f"id{order['manager_id']}"
    
    text = f"{shop_header()}\n*ВЫПОЛНЕННЫЕ ЗАКАЗЫ ({len(orders)})*\n{divider()}\n"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        order_list_kb(orders, "admin_view_order")
    )

@dp.message(F.text == "❌ ОТМЕНЕННЫЕ")
async def admin_cancelled_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    orders = await get_orders(status='отменен')
    
    if not orders:
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*ОТМЕНЕННЫХ ЗАКАЗОВ НЕТ*\n{divider()}",
            back_kb("back_admin_orders")
        )
        return
    
    for order in orders:
        if order.get('manager_id'):
            try:
                manager = await bot.get_chat(order['manager_id'])
                order['manager_name'] = manager.username or f"id{order['manager_id']}"
            except:
                order['manager_name'] = f"id{order['manager_id']}"
    
    text = f"{shop_header()}\n*ОТМЕНЕННЫЕ ЗАКАЗЫ ({len(orders)})*\n{divider()}\n"
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        order_list_kb(orders, "admin_view_order")
    )

@dp.message(F.text == "👨‍💼 ПО МЕНЕДЖЕРАМ")
async def admin_orders_by_managers(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    managers = {}
    for manager_id in manager_ids:
        try:
            manager = await bot.get_chat(manager_id)
            manager_name = manager.username or f"Менеджер {manager_id}"
            managers[manager_id] = manager_name
        except:
            managers[manager_id] = f"Менеджер {manager_id}"
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*ВЫБЕРИТЕ МЕНЕДЖЕРА*\n{divider()}",
        admin_orders_by_manager_kb(managers)
    )

@dp.callback_query(F.data.startswith("admin_manager_orders_"))
async def admin_view_manager_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    manager_id = int(callback.data.replace("admin_manager_orders_", ""))
    
    try:
        manager = await bot.get_chat(manager_id)
        manager_name = manager.username or f"Менеджер {manager_id}"
    except:
        manager_name = f"Менеджер {manager_id}"
    
    orders = await get_orders(manager_id=manager_id)
    
    if not orders:
        text = f"{shop_header()}\n*ЗАКАЗЫ {manager_name}*\n{divider()}\n╰ У МЕНЕДЖЕРА НЕТ ЗАКАЗОВ\n{divider()}"
        await callback.message.edit_caption(caption=text, reply_markup=back_kb("back_admin_orders"))
        await callback.answer()
        return
    
    for order in orders:
        order['manager_name'] = manager_name
    
    text = f"{shop_header()}\n*ЗАКАЗЫ {manager_name} ({len(orders)})*\n{divider()}\n"
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=order_list_kb(orders, "admin_view_order"))
    else:
        await callback.message.edit_text(text=text, reply_markup=order_list_kb(orders, "admin_view_order"))
    await callback.answer()

# ============= АДМИН: ПРОМОКОДЫ =============
@dp.message(F.text == "🎫 ПРОМОКОДЫ")
async def admin_promo_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{shop_header()}\n*❌ НЕТ ДОСТУПА*\n{divider()}")
        return
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*🎫 УПРАВЛЕНИЕ ПРОМОКОДАМИ*\n{divider()}",
        admin_promo_keyboard()
    )

@dp.callback_query(F.data == "back_admin_promo")
async def back_admin_promo(callback: CallbackQuery):
    """Возврат в админ панель промокодов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{shop_header()}\n*🎫 УПРАВЛЕНИЕ ПРОМОКОДАМИ*\n{divider()}",
            reply_markup=admin_promo_keyboard()
        )
    else:
        await callback.message.edit_text(
            text=f"{shop_header()}\n*🎫 УПРАВЛЕНИЕ ПРОМОКОДАМИ*\n{divider()}",
            reply_markup=admin_promo_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data == "admin_promo_stats")
async def admin_promo_stats(callback: CallbackQuery):
    """Общая статистика по промокодам"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    stats = await get_promo_stats()
    
    text = f"""
{shop_header()}
*📊 СТАТИСТИКА ПРОМОКОДОВ*
{divider()}

📦 *ВСЕГО ПРОМОКОДОВ:* {stats['total']}
✅ *АКТИВНЫХ:* {stats['active']}
❌ *НЕАКТИВНЫХ:* {stats['total'] - stats['active']}

{divider()}
*ИСПОЛЬЗОВАНИЕ*
{divider()}
📈 *ВСЕГО ИСПОЛЬЗОВАНИЙ:* {stats['total_uses']}
💰 *ОБЩАЯ СУММА СКИДОК:* {format_price(stats['total_discount'])}
📊 *СРЕДНИЙ РАЗМЕР СКИДКИ:* {stats['avg_discount']}%

{divider()}
*ПОПУЛЯРНОСТЬ*
{divider()}
🏆 *САМЫЙ ПОПУЛЯРНЫЙ:* `{stats['top_promo']}`
🎯 *ИСПОЛЬЗОВАНИЙ:* {stats['top_count']}

{divider()}
⏰ *ИСТЕКАЮТ ЧЕРЕЗ 7 ДНЕЙ:* {stats['expiring_soon']}
{divider()}"""
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=back_kb("back_admin_promo")
        )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=back_kb("back_admin_promo")
        )
    await callback.answer()

@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    await state.set_state(AdminPromoStates.waiting_for_promo_data)
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{shop_header()}\n*➕ СОЗДАНИЕ ПРОМОКОДА*\n{divider()}\n\n"
            f"Введите параметры в формате:\n"
            f"`СКИДКА;КОЛИЧЕСТВО;СРОК(ДНЕЙ);ОПИСАНИЕ`\n\n"
            f"Пример: `15;50;7;Скидка 15% на всё`\n\n"
            f"Или отправьте `random` для случайного промокода\n\n"
            f"Для отмены нажмите кнопку ниже",
            reply_markup=cancel_kb()
        )
    else:
        await callback.message.edit_text(
            text=f"{shop_header()}\n*➕ СОЗДАНИЕ ПРОМОКОДА*\n{divider()}\n\n"
            f"Введите параметры в формате:\n"
            f"`СКИДКА;КОЛИЧЕСТВО;СРОК(ДНЕЙ);ОПИСАНИЕ`\n\n"
            f"Пример: `15;50;7;Скидка 15% на всё`\n\n"
            f"Или отправьте `random` для случайного промокода\n\n"
            f"Для отмены нажмите кнопку ниже",
            reply_markup=cancel_kb()
        )
    await callback.answer()

@dp.callback_query(F.data == "cancel", AdminPromoStates.waiting_for_promo_data)
async def cancel_create_promo(callback: CallbackQuery, state: FSMContext):
    """Отмена создания промокода"""
    await state.clear()
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{shop_header()}\n*❌ СОЗДАНИЕ ОТМЕНЕНО*\n{divider()}",
            reply_markup=back_kb("back_admin_promo")
        )
    else:
        await callback.message.edit_text(
            text=f"{shop_header()}\n*❌ СОЗДАНИЕ ОТМЕНЕНО*\n{divider()}",
            reply_markup=back_kb("back_admin_promo")
        )
    await callback.answer()

@dp.message(AdminPromoStates.waiting_for_promo_data)
async def admin_create_promo_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    text = message.text.strip()
    
    if text.lower() == 'random':
        discount = random.choice([5, 10, 15, 20])
        max_uses = random.choice([10, 25, 50, 100])
        days = random.choice([3, 7, 14, 30])
        
        promo_code = await create_promocode(
            discount=discount,
            max_uses=max_uses,
            description=f"Случайная скидка {discount}%",
            expires_days=days
        )
        
        await safe_send_photo(
            message,
            admin_image_id,
            f"{shop_header()}\n*✅ СЛУЧАЙНЫЙ ПРОМОКОД*\n{divider()}\n\n"
            f"Промокод: `{promo_code}`\n"
            f"Скидка: {discount}%\n"
            f"Использований: {max_uses}\n"
            f"Срок: {days} дней",
            back_kb("back_admin_promo")
        )
    else:
        try:
            parts = text.split(';')
            discount = int(parts[0])
            max_uses = int(parts[1]) if len(parts) > 1 else 100
            days = int(parts[2]) if len(parts) > 2 else 7
            description = parts[3] if len(parts) > 3 else f"Скидка {discount}%"
            
            promo_code = await create_promocode(
                discount=discount,
                max_uses=max_uses,
                description=description,
                expires_days=days
            )
            
            await safe_send_photo(
                message,
                admin_image_id,
                f"{shop_header()}\n*✅ ПРОМОКОД СОЗДАН*\n{divider()}\n\n"
                f"Промокод: `{promo_code}`\n"
                f"Скидка: {discount}%\n"
                f"Использований: {max_uses}\n"
                f"Срок: {days} дней\n"
                f"Описание: {description}",
                back_kb("back_admin_promo")
            )
        except Exception as e:
            await message.answer(
                f"{shop_header()}\n*❌ ОШИБКА*\n{divider()}\n\n"
                f"Неверный формат. Используйте: `СКИДКА;КОЛИЧЕСТВО;СРОК;ОПИСАНИЕ`",
                reply_markup=cancel_kb()
            )
    
    await state.clear()

@dp.callback_query(F.data == "admin_list_promos")
async def admin_list_promos(callback: CallbackQuery):
    """Показать список всех промокодов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    promocodes = await get_all_promocodes()
    
    if not promocodes:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=f"{shop_header()}\n*📋 ПРОМОКОДЫ*\n{divider()}\n\n❌ Нет созданных промокодов",
                reply_markup=back_kb("back_admin_promo")
            )
        else:
            await callback.message.edit_text(
                text=f"{shop_header()}\n*📋 ПРОМОКОДЫ*\n{divider()}\n\n❌ Нет созданных промокодов",
                reply_markup=back_kb("back_admin_promo")
            )
        await callback.answer()
        return
    
    text = f"{shop_header()}\n*📋 ВСЕ ПРОМОКОДЫ*\n{divider()}\n\n"
    
    for p in promocodes[:10]:
        status = "✅" if p['is_active'] else "❌"
        expires = p['expires_at'][:10] if p['expires_at'] else "бессрочно"
        text += f"{status} `{p['code']}` - {p['discount']}%\n"
        text += f"   ├ Использовано: {p['used_count']}/{p['max_uses']}\n"
        text += f"   ╰ Действ. до: {expires}\n\n"
    
    text += f"{divider()}"
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=promo_list_keyboard(promocodes)
        )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=promo_list_keyboard(promocodes)
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_promo_"))
async def admin_view_promo(callback: CallbackQuery):
    """Просмотр конкретного промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    promo_code = callback.data.replace("admin_promo_", "")
    stats = await get_promo_detailed_stats(promo_code)
    
    if not stats:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    promo = stats['promo']
    status = "✅ Активен" if promo['is_active'] else "❌ Неактивен"
    expires = promo['expires_at'][:16] if promo['expires_at'] else "бессрочно"
    
    text = f"""
{shop_header()}
*📊 ПРОМОКОД `{promo['code']}`*
{divider()}

📌 *ОСНОВНАЯ ИНФОРМАЦИЯ:*
├ Скидка: {promo['discount']}%
├ Всего использований: {promo['used_count']}/{promo['max_uses']}
├ Уникальных пользователей: {stats['promo'].get('unique_users', 0)}
├ Статус: {status}
├ Действует до: {expires}
╰ Описание: {promo['description'] or 'нет'}

{divider()}
💰 *ФИНАНСЫ:*
├ Общая сумма скидок: {format_price(stats['promo'].get('total_discount', 0))}
╰ Средняя скидка: {promo['discount']}%

{divider()}
📈 *ИСПОЛЬЗОВАНИЕ ПО ДНЯМ:*
{divider()}
"""
    
    if stats['daily_stats']:
        for day in stats['daily_stats'][:7]:
            text += f"📅 {day['date']}: {day['count']} раз(а) - {format_price(day['discount'])}\n"
    else:
        text += "❌ Нет использований\n"
    
    text += f"\n{divider()}\n"
    
    if stats['recent_uses']:
        text += f"🕒 *ПОСЛЕДНИЕ ИСПОЛЬЗОВАНИЯ:*\n"
        for use in stats['recent_uses'][:5]:
            username = f"@{use['username']}" if use['username'] else f"id{use['user_id']}"
            text += f"• {username}\n"
            text += f"  ╰ {use['used_at'][:16]} - заказ {use['order_number']}\n"
    else:
        text += "❌ Нет использований\n"
    
    text += f"{divider()}"
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=promo_actions_keyboard(promo_code)
        )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=promo_actions_keyboard(promo_code)
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("promo_stats_"))
async def promo_detailed_stats(callback: CallbackQuery):
    """Детальная статистика по конкретному промокоду"""
    await admin_view_promo(callback)

@dp.callback_query(F.data.startswith("promo_deactivate_"))
async def promo_deactivate(callback: CallbackQuery):
    """Деактивация промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    promo_code = callback.data.replace("promo_deactivate_", "")
    await deactivate_promocode(promo_code)
    
    await callback.answer("✅ Промокод деактивирован", show_alert=True)
    await admin_list_promos(callback)

@dp.callback_query(F.data.startswith("promo_send_"))
async def promo_send_all(callback: CallbackQuery, state: FSMContext):
    """Отправка промокода всем пользователям"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    promo_code = callback.data.replace("promo_send_", "")
    promo = await get_promocode(promo_code)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await state.update_data(send_promo=promo_code)
    await state.set_state(AdminPromoStates.waiting_for_send_text)
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{shop_header()}\n*📢 РАССЫЛКА ПРОМОКОДА*\n{divider()}\n\n"
            f"Промокод: `{promo_code}`\n"
            f"Скидка: {promo['discount']}%\n\n"
            f"Введите текст сообщения для рассылки:",
            reply_markup=cancel_kb()
        )
    else:
        await callback.message.edit_text(
            text=f"{shop_header()}\n*📢 РАССЫЛКА ПРОМОКОДА*\n{divider()}\n\n"
            f"Промокод: `{promo_code}`\n"
            f"Скидка: {promo['discount']}%\n\n"
            f"Введите текст сообщения для рассылки:",
            reply_markup=cancel_kb()
        )
    await callback.answer()

@dp.message(AdminPromoStates.waiting_for_send_text)
async def promo_send_text(message: Message, state: FSMContext):
    """Отправка промокода с текстом"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    promo_code = data.get('send_promo')
    promo = await get_promocode(promo_code)
    
    send_text = message.text
    
    users = await get_all_users()
    success = 0
    failed = 0
    
    await message.answer(
        f"{shop_header()}\n*📢 РАССЫЛКА ЗАПУЩЕНА*\n{divider()}\n\n"
        f"👥 Всего пользователей: {len(users)}\n"
        f"⏳ Отправка..."
    )
    
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                f"{send_text}\n\n"
                f"🎫 *ПРОМОКОД:* `{promo_code}`\n"
                f"💰 *СКИДКА:* {promo['discount']}%\n\n"
                f"Введите /promo и активируйте код!",
                parse_mode="Markdown"
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
    
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*📢 РАССЫЛКА ЗАВЕРШЕНА*\n{divider()}\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}\n"
        f"👥 Всего: {len(users)}",
        back_kb("back_admin_promo")
    )
    
    await state.clear()

# ============= АДМИН: СТАТИСТИКА =============
@dp.message(F.text == "📊 СТАТИСТИКА")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    orders = await get_orders()
    
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o['status'] == 'выполнен'])
    total_revenue = sum(o['total_amount'] for o in orders if o['status'] == 'выполнен')
    
    brands_list = await get_brands()
    products = await get_products()
    
    text = f"""
{shop_header()}
*СТАТИСТИКА*
{divider()}
├ 📦 ВСЕГО ЗАКАЗОВ: {total_orders}
├ ✅ ВЫПОЛНЕНО: {completed_orders}
├ 💰 ВЫРУЧКА: {format_price(total_revenue)}
├ 🏷 БРЕНДОВ: {len(brands_list)}
╰ 👕 ТОВАРОВ: {len(products)}

{divider()}"""
    
    await safe_send_photo(
        message,
        admin_image_id,
        text,
        back_kb("back_admin")
    )

# ============= РАССЫЛКА =============
@dp.message(F.text == "📢 РАССЫЛКА")
async def mailing_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(f"{shop_header()}\n*НЕТ ДОСТУПА*\n{divider()}")
        return
    
    await state.set_state(Mailing.text)
    await safe_send_photo(
        message,
        admin_image_id,
        f"{shop_header()}\n*📢 РАССЫЛКА*\n{divider()}\n\n"
        f"ВВЕДИТЕ ТЕКСТ ДЛЯ РАССЫЛКИ ВСЕМ ПОЛЬЗОВАТЕЛЯМ:\n\n"
        f"⚠️ *ВНИМАНИЕ:* Сообщение будет отправлено ВСЕМ, кто запускал бота!",
        cancel_kb()
    )

@dp.message(Mailing.text)
async def mailing_get_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    mailing_text = message.text
    
    await state.update_data(mailing_text=mailing_text)
    await state.set_state(Mailing.confirm)
    
    users = await get_all_users()
    users_count = len(users)
    
    await message.answer(
        f"📢 ПРЕДПРОСМОТР РАССЫЛКИ:\n\n"
        f"{mailing_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 ПОЛУЧАТЕЛЕЙ: {users_count}\n"
        f"━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=mailing_confirm_kb()
    )

@dp.callback_query(F.data == "mailing_confirm")
async def mailing_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(f"❌ НЕТ ДОСТУПА", show_alert=True)
        return
    
    data = await state.get_data()
    mailing_text = data.get('mailing_text')
    
    users = await get_all_users()
    success = 0
    failed = 0
    
    await callback.message.edit_text(
        f"{shop_header()}\n*📢 РАССЫЛКА ЗАПУЩЕНА*\n{divider()}\n\n"
        f"👥 ВСЕГО ПОЛЬЗОВАТЕЛЕЙ: {len(users)}\n"
        f"⏳ ОТПРАВКА..."
    )
    
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                mailing_text,
                parse_mode="Markdown"
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            try:
                await bot.send_message(
                    user_id,
                    mailing_text,
                    parse_mode=None
                )
                success += 1
            except:
                failed += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
    
    await callback.message.edit_text(
        f"{shop_header()}\n*📢 РАССЫЛКА ЗАВЕРШЕНА*\n{divider()}\n\n"
        f"✅ УСПЕШНО: {success}\n"
        f"❌ ОШИБОК: {failed}\n"
        f"👥 ВСЕГО: {len(users)}\n"
        f"{divider()}"
    )
    
    await state.clear()

@dp.callback_query(F.data == "cancel_mailing")
async def mailing_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"{shop_header()}\n*📢 РАССЫЛКА ОТМЕНЕНА*\n{divider()}"
    )
    await callback.answer()

@dp.message(F.text == "ℹ️ О НАС")
async def about(message: Message):
    text = f"""
{shop_header()}

╰ *ПРЕМИУМ РЕПЛИКИ ИЗ КИТАЯ*

{divider()}
❓ *ВОЗМОЖНО ЛИ ЗАКАЗАТЬ ВЕЩЬ НЕ ИЗ КАТАЛОГА?*
   НАПИШИТЕ МЕНЕДЖЕРУ - ВСЁ ВОЗМОЖНО

❓ *КАКИЕ У ВАС РЕПЛИКИ?*
   1:1 КАЧЕСТВО, ПОЛНАЯ КОМПЛЕКТАЦИЯ

❓ *СКОЛЬКО ЖДАТЬ?*
   {delivery_days_min}-{delivery_days_max} ДНЕЙ

❓ *КАК ОПЛАЧИВАТЬ?*
   🇰🇿 CRYPTOBOT

❓ *А ЕСЛИ МОШЕННИКИ?*
    КАНАЛ С ОТЗЫВАМИ @otzivi3500shoes
    ТАКЖЕ МЫ МОЖЕМ ПРЕДОСТАВИТЬ ГАРАНТА

❓ *ЕСТЬ ВОЗВРАТ?*
   ВЫКУП С КИТАЯ - ВОЗВРАТА НЕТ

❓ *ЕСТЬ СКИДКИ?*
   ✅ ПОСТОЯННЫМ КЛИЕНТАМ
   ✅ ПРОМОКОДЫ НА ПРАЗДНИКИ
   ✅ СИСТЕМА ЛОЯЛЬНОСТИ

{divider()}
🎨 *РАСЦВЕТКИ*
{divider()}
   В КАТАЛОГЕ ПОКАЗАНЫ БАЗОВЫЕ/ДЕФОЛТНЫЕ РАСЦВЕТКИ
   
   📌 *ДРУГИЕ РАСЦВЕТКИ ДОСТУПНЫ:*
   • ПО ЗАПРОСУ МЕНЕДЖЕРУ
   • ИНДИВИДУАЛЬНЫЙ ПОДБОР
   • ЛЮБЫЕ ЦВЕТА ПОД ЗАКАЗ

{divider()}
*КОНТАКТЫ:* @TriPatsotManager
{divider()}"""
    
    await safe_send_photo(
        message,
        menu_image_id,
        text,
        main_menu(
            is_admin(message.from_user.id),
            is_manager(message.from_user.id)
        )
    )

# ============= ПОЛУЧЕНИЕ FILE ID =============
@dp.message(F.photo)
async def get_file_id(message: Message):
    file_id = message.photo[-1].file_id
    await message.answer(
        f"✅ FILE_ID:\n{file_id}",
        parse_mode=None
    )

# ============= НАВИГАЦИЯ =============
@dp.message(F.text == "◀️ НАЗАД")
@dp.callback_query(F.data == "back_main")
async def back_to_main(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        message = event.message
    else:
        message = event
    
    text = f"""
{shop_header()}

*{shop_description.upper()}*

{divider()}
├ 1:1 КАЧЕСТВО
├ ОРИГИНАЛЬНЫЕ МАТЕРИАЛЫ
├ ВСЕ РАЗМЕРЫ 35-46
╰ ДОСТАВКА {delivery_days_min}-{delivery_days_max} ДНЕЙ

{divider()}
*КАК ЗАКАЗАТЬ*
{divider()}
├ 1. ВЫБРАТЬ МОДЕЛЬ
├ 2. ВЫБРАТЬ РАЗМЕР
├ 3. ОФОРМИТЬ ЗАКАЗ
╰ 4. МЕНЕДЖЕР ПОДТВЕРЖДАЕТ
{divider()}"""
    
    await safe_send_photo(
        message,
        menu_image_id,
        text,
        main_menu(
            is_admin(message.chat.id),
            is_manager(message.chat.id)
        )
    )

@dp.callback_query(F.data == "back_catalog")
async def back_catalog(callback: CallbackQuery):
    await callback.message.delete()
    await show_catalog(callback.message)

@dp.callback_query(F.data == "back_brands")
async def back_brands(callback: CallbackQuery):
    await callback.message.delete()
    await show_catalog(callback.message)

@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery):
    await callback.message.delete()
    await safe_send_photo(
        callback.message,
        admin_image_id,
        f"{shop_header()}\n*АДМИН ПАНЕЛЬ*\n{divider()}",
        admin_menu()
    )

@dp.callback_query(F.data == "back_manager")
async def back_manager(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        f"{shop_header()}\n*ПАНЕЛЬ МЕНЕДЖЕРА*\n{divider()}",
        reply_markup=manager_menu()
    )

@dp.callback_query(F.data == "back_admin_orders")
async def back_admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.delete()
    await admin_orders_panel(callback.message)

@dp.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    await callback.message.answer(
        text=f"{shop_header()}\n*ДЕЙСТВИЕ ОТМЕНЕНО*\n{divider()}",
        reply_markup=None
    )
    
    await callback.message.answer(
        text=f"{shop_header()}\n*ГЛАВНОЕ МЕНЮ*\n{divider()}",
        reply_markup=main_menu(
            is_admin(callback.from_user.id),
            is_manager(callback.from_user.id)
        )
    )
    await callback.answer()

# ============= ЗАПУСК =============
async def main():
    await init_db()
    await fix_database()
    await fix_orders_table()
    await init_brands(initial_brands)
    print("=" * 50)
    print("🚀 3500SHOES")
    print(f"✅ АДМИН: https://t.me/TriPatsotManager")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())