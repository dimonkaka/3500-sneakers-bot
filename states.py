from aiogram.fsm.state import State, StatesGroup

class AddProduct(StatesGroup):
    brand = State()
    model = State()
    base_price = State()
    description = State()
    photos = State()

class AddBrand(StatesGroup):
    name = State()

class Checkout(StatesGroup):
    name = State()
    city = State()
    postal_code = State()
    promo_code = State()

class Reply(StatesGroup):
    text = State()

class Mailing(StatesGroup):
    text = State()
    confirm = State()

class AdminPromoStates(StatesGroup):
    waiting_for_promo_data = State()
    waiting_for_send_text = State()
    waiting_for_promotion_name = State()
    waiting_for_promotion_discount = State()
    waiting_for_promotion_duration = State()
    waiting_for_promotion_promo = State()

class PromoStates(StatesGroup):
    waiting_for_promo = State()