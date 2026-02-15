from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Dict
from config import sizes

# ============= ГЛАВНОЕ МЕНЮ =============
def main_menu(is_admin: bool = False, is_manager: bool = False):
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛍 КАТАЛОГ"))
    b.row(KeyboardButton(text="🛒 КОРЗИНА"), KeyboardButton(text="📦 ЗАКАЗЫ"))
    b.row(KeyboardButton(text="ℹ️ О НАС"))
    if is_admin:
        b.row(KeyboardButton(text="⚙️ АДМИН"))
    elif is_manager:
        b.row(KeyboardButton(text="📋 МЕНЕДЖЕР"))
    return b.as_markup(resize_keyboard=True)

# ============= АДМИН ПАНЕЛЬ =============
def admin_menu():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="➕ ДОБАВИТЬ ТОВАР"))
    b.row(KeyboardButton(text="🏷 УПРАВЛЕНИЕ БРЕНДАМИ"))
    b.row(KeyboardButton(text="📋 УПРАВЛЕНИЕ ТОВАРАМИ"))
    b.row(KeyboardButton(text="📦 УПРАВЛЕНИЕ ЗАКАЗАМИ"))
    b.row(KeyboardButton(text="🎫 ПРОМОКОДЫ"))
    b.row(KeyboardButton(text="📢 РАССЫЛКА"))
    b.row(KeyboardButton(text="📊 СТАТИСТИКА"))
    b.row(KeyboardButton(text="◀️ НАЗАД"))
    return b.as_markup(resize_keyboard=True)

# ============= МЕНЕДЖЕР ПАНЕЛЬ =============
def manager_menu():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📋 МОИ ЗАКАЗЫ"))
    b.row(KeyboardButton(text="🆕 НОВЫЕ ЗАКАЗЫ"))
    b.row(KeyboardButton(text="📦 ВСЕ ЗАКАЗЫ"))
    b.row(KeyboardButton(text="◀️ НАЗАД"))
    return b.as_markup(resize_keyboard=True)

# ============= ПРОМОКОДЫ =============
def admin_promo_keyboard():
    """Админ-клавиатура для промокодов"""
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo"),
        InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_list_promos")
    )
    b.row(
        InlineKeyboardButton(text="📊 Статистика промокодов", callback_data="admin_promo_stats"),
        InlineKeyboardButton(text="📢 Рассылка промокода", callback_data="admin_promo_mailing")
    )
    b.row(
        InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_admin")
    )
    return b.as_markup()

def promo_list_keyboard(promocodes: list):
    """Клавиатура со списком промокодов"""
    b = InlineKeyboardBuilder()
    for p in promocodes[:10]:
        status = "✅" if p['is_active'] else "❌"
        b.row(InlineKeyboardButton(
            text=f"{status} {p['code']} - {p['discount']}% ({p['used_count']}/{p['max_uses']})",
            callback_data=f"admin_promo_{p['code']}"
        ))
    b.row(
        InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin_promo_stats"),
        InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_admin_promo")
    )
    return b.as_markup()

def promo_actions_keyboard(code: str):
    """Кнопки действий с промокодом"""
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📤 Отправить всем", callback_data=f"promo_send_{code}"),
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"promo_stats_{code}")
    )
    b.row(
        InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"promo_deactivate_{code}"),
        InlineKeyboardButton(text="◀️ НАЗАД", callback_data="admin_list_promos")
    )
    return b.as_markup()

# ============= КАТАЛОГ =============
def brands_kb(brands: list):
    b = InlineKeyboardBuilder()
    for brand in brands:
        b.button(text=brand.upper(), callback_data=f"brand_{brand}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="◀️ ГЛАВНОЕ", callback_data="back_main"))
    return b.as_markup()

def models_kb(products: list):
    b = InlineKeyboardBuilder()
    for product in products:
        price_str = f"{product['final_price']:,}₸"
        b.row(InlineKeyboardButton(
            text=f"{product['model'].upper()}  |  {price_str}",
            callback_data=f"model_{product['id']}"
        ))
    b.row(InlineKeyboardButton(text="◀️ К БРЕНДАМ", callback_data="back_brands"))
    return b.as_markup()

def product_nav(product_id: int, has_multiple: bool = False):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📏 ВЫБРАТЬ РАЗМЕР", callback_data=f"select_size_{product_id}"))
    
    if has_multiple:
        b.row(
            InlineKeyboardButton(text="◀️ ПРЕД.", callback_data=f"prev_model_{product_id}"),
            InlineKeyboardButton(text="СЛЕД. ▶️", callback_data=f"next_model_{product_id}")
        )
    
    b.row(
        InlineKeyboardButton(text="◀️ К МОДЕЛЯМ", callback_data="back_to_models"),
        InlineKeyboardButton(text="🛒 КОРЗИНА", callback_data="view_cart")
    )
    return b.as_markup()

def sizes_kb(product_id: int):
    b = InlineKeyboardBuilder()
    for s in sizes:
        b.button(text=str(s), callback_data=f"size_{product_id}_{s}")
    b.adjust(6)
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data=f"back_product_{product_id}"))
    return b.as_markup()

# ============= КОРЗИНА =============
def cart_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ ОФОРМИТЬ", callback_data="checkout"))
    b.row(InlineKeyboardButton(text="🗑 ОЧИСТИТЬ", callback_data="clear_cart"))
    b.row(InlineKeyboardButton(text="◀️ КАТАЛОГ", callback_data="back_catalog"))
    return b.as_markup()

def checkout_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data="confirm_order"))
    b.row(InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="view_cart"))
    return b.as_markup()

# ============= ЗАКАЗЫ =============
def order_list_kb(orders: List[Dict], callback_prefix: str = "view_order"):
    b = InlineKeyboardBuilder()
    for o in orders[:10]:
        if o['status'] == 'новый':
            icon = "🆕"
        elif o['status'] == 'в работе':
            icon = "🔄"
        elif o['status'] == 'выполнен':
            icon = "✅"
        else:
            icon = "❌"
        
        manager = f" @{o.get('manager_name', '')}" if o.get('manager_name') else ""
        b.row(InlineKeyboardButton(
            text=f"{icon} {o['order_number']}{manager} - {o['total_amount']}₸",
            callback_data=f"{callback_prefix}_{o['order_number']}"
        ))
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_admin_orders"))
    return b.as_markup()

def manager_order_list(orders: List[Dict]):
    b = InlineKeyboardBuilder()
    for o in orders[:5]:
        if o['status'] == 'новый':
            icon = "🆕"
        elif o['status'] == 'в работе':
            icon = "🔄"
        else:
            icon = "✅"
        b.row(InlineKeyboardButton(
            text=f"{icon} {o['order_number']}  {o['total_amount']}₸",
            callback_data=f"view_order_{o['order_number']}"
        ))
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_manager"))
    return b.as_markup()

def order_actions(order_number: str, user_id: int, username: str = None):
    b = InlineKeyboardBuilder()
    if username:
        b.row(InlineKeyboardButton(text="📞 НАПИСАТЬ", url=f"https://t.me/{username}"))
    else:
        b.row(InlineKeyboardButton(text="📞 НАПИСАТЬ", url=f"tg://user?id={user_id}"))
    b.row(
        InlineKeyboardButton(text="✅ ВЗЯТЬ", callback_data=f"take_{order_number}"),
        InlineKeyboardButton(text="📝 ОТВЕТИТЬ", callback_data=f"reply_{order_number}_{user_id}")
    )
    b.row(
        InlineKeyboardButton(text="🏁 ЗАВЕРШИТЬ", callback_data=f"complete_{order_number}"),
        InlineKeyboardButton(text="❌ ОТМЕНИТЬ", callback_data=f"cancel_order_{order_number}")
    )
    b.row(InlineKeyboardButton(text="◀️ К СПИСКУ", callback_data="manager_orders"))
    return b.as_markup()

def manager_order_work_menu(order_number: str):
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=f"📝 СТАТУС ЗАКАЗА {order_number}"))
    b.row(KeyboardButton(text="📞 НАПИСАТЬ КЛИЕНТУ"))
    b.row(KeyboardButton(text="✅ ПОДТВЕРДИТЬ ВЫКУП"))
    b.row(KeyboardButton(text="📦 ОТПРАВЛЕНО В КАЗАХСТАН"))
    b.row(KeyboardButton(text="🏁 ЗАВЕРШИТЬ ЗАКАЗ"))
    b.row(KeyboardButton(text="❌ ОТМЕНИТЬ ЗАКАЗ"))
    b.row(KeyboardButton(text="◀️ К ЗАКАЗАМ"))
    return b.as_markup(resize_keyboard=True)

# ============= АДМИН: УПРАВЛЕНИЕ БРЕНДАМИ =============
def brands_management_kb():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="➕ ДОБАВИТЬ", callback_data="add_brand"),
        InlineKeyboardButton(text="❌ УДАЛИТЬ", callback_data="delete_brand")
    )
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_admin"))
    return b.as_markup()

def brands_list_kb(brands: list, action: str):
    b = InlineKeyboardBuilder()
    for brand in brands[:10]:
        b.row(InlineKeyboardButton(
            text=f"✕ {brand.upper()}",
            callback_data=f"{action}_{brand}"
        ))
    b.row(InlineKeyboardButton(text="◀️ ОТМЕНА", callback_data="back_brands_management"))
    return b.as_markup()

# ============= АДМИН: УПРАВЛЕНИЕ ЗАКАЗАМИ =============
def admin_orders_menu():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📋 ВСЕ ЗАКАЗЫ"))
    b.row(KeyboardButton(text="🆕 НОВЫЕ ЗАКАЗЫ"))
    b.row(KeyboardButton(text="🔄 В РАБОТЕ"))
    b.row(KeyboardButton(text="✅ ВЫПОЛНЕННЫЕ"))
    b.row(KeyboardButton(text="❌ ОТМЕНЕННЫЕ"))
    b.row(KeyboardButton(text="👨‍💼 ПО МЕНЕДЖЕРАМ"))
    b.row(KeyboardButton(text="◀️ НАЗАД"))
    return b.as_markup(resize_keyboard=True)

def admin_orders_by_manager_kb(managers: dict):
    b = InlineKeyboardBuilder()
    for manager_id, manager_name in managers.items():
        b.row(InlineKeyboardButton(
            text=f"👨‍💼 {manager_name}",
            callback_data=f"admin_manager_orders_{manager_id}"
        ))
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_admin_orders"))
    return b.as_markup()

# ============= АДМИН: ТОВАРЫ =============
def admin_products_kb(products: list):
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"{p['brand'].upper()} {p['model'][:15]}...  {p['final_price']}₸",
                callback_data=f"admin_product_{p['id']}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="➕ ДОБАВИТЬ", callback_data="admin_add_product"))
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_admin"))
    return b.as_markup()

def admin_product_kb(product_id: int):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ УДАЛИТЬ", callback_data=f"delete_product_{product_id}"))
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data="admin_products_list"))
    return b.as_markup()

# ============= ПРОМОКОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =============
def promo_keyboard():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🎫 Ввести промокод", callback_data="enter_promo"),
        InlineKeyboardButton(text="🎁 Мои скидки", callback_data="my_discounts")
    )
    return b.as_markup()

# ============= РАССЫЛКА =============
def mailing_confirm_kb():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data="mailing_confirm"),
        InlineKeyboardButton(text="❌ ОТМЕНИТЬ", callback_data="cancel_mailing")
    )
    return b.as_markup()

# ============= ВСПОМОГАТЕЛЬНЫЕ =============
def cancel_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel"))
    return b.as_markup()

def back_kb(cb: str = "back_main"):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ НАЗАД", callback_data=cb))
    return b.as_markup()