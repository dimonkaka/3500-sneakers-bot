import os
from dotenv import load_dotenv

load_dotenv()

# ============= 3500 sneakers =============
token = os.getenv("BOT_TOKEN")

# админ и менеджеры
admin_id = int(os.getenv("ADMIN_ID", "7329250669"))
manager_ids = [int(id) for id in os.getenv("MANAGER_IDS", "7329250669").split(",")]

# настройки магазина
shop_name = "3500"
shop_description = "🇨🇳 3500 - премиум реплики из Китая"

# начальные бренды
initial_brands = [
    "rick owens",
    "maison margiela",
    "balenciaga",
    "nike",
    "adidas"
]

# размеры
sizes = [35,36,37,38,39,40,41,42,43,44,45,46]

# ДОСТАВКА
delivery_price = 5000
delivery_days_min = 14
delivery_days_max = 21

# наценка
markup_percent = 20

# ============= ID ФОТОГРАФИЙ ИЗ .ENV =============
menu_image_id = os.getenv("menu_image_id")
catalog_image_id = os.getenv("catalog_image_id")
cart_image_id = os.getenv("cart_image_id")
orders_image_id = os.getenv("orders_image_id")
admin_image_id = os.getenv("admin_image_id")