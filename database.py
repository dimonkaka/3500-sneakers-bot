import aiosqlite
import json
import random
import string
from datetime import datetime, timedelta

db_name = "3500.db"

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(db_name) as db:
        # бренды
        await db.execute("""
            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # товары
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                base_price INTEGER NOT NULL,
                final_price INTEGER NOT NULL,
                description TEXT,
                photos TEXT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                postal_code TEXT,
                city TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_orders INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                discount_level INTEGER DEFAULT 0
            )
        """)
        
        # корзина
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                size INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, product_id, size)
            )
        """)
        
        # заказы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                items TEXT NOT NULL,
                subtotal INTEGER NOT NULL,
                delivery_price INTEGER NOT NULL,
                discount_amount INTEGER DEFAULT 0,
                promo_code TEXT,
                total_amount INTEGER NOT NULL,
                delivery_city TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                delivery_postal_code TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                contact_username TEXT,
                status TEXT DEFAULT 'новый',
                manager_id INTEGER,
                processed_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ПРОМОКОДЫ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount INTEGER NOT NULL,
                description TEXT,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                per_user_limit INTEGER DEFAULT 1,
                min_order_amount INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                expires_at TIMESTAMP,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # АКТИВНЫЕ АКЦИИ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                discount INTEGER NOT NULL,
                promo_required BOOLEAN DEFAULT 0,
                promo_code TEXT,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (promo_code) REFERENCES promocodes(code)
            )
        """)
        
        # ИСПОЛЬЗОВАННЫЕ ПРОМОКОДЫ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                promo_code TEXT NOT NULL,
                order_number TEXT,
                discount_used INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (promo_code) REFERENCES promocodes(code)
            )
        """)
        
        await db.commit()
        print("✅ База данных инициализирована")

# ============= ФУНКЦИИ ДЛЯ ИСПРАВЛЕНИЯ БАЗЫ =============

async def fix_database():
    """Добавляет недостающие колонки в существующую базу данных"""
    async with aiosqlite.connect(db_name) as db:
        # Проверяем таблицу users
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'postal_code' not in column_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN postal_code TEXT")
                print("✅ Добавлена колонка postal_code в таблицу users")
            except:
                pass
        
        if 'city' not in column_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN city TEXT")
                print("✅ Добавлена колонка city в таблицу users")
            except:
                pass
        
        if 'discount_level' not in column_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN discount_level INTEGER DEFAULT 0")
                print("✅ Добавлена колонка discount_level в таблицу users")
            except:
                pass
        
        if 'total_spent' not in column_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN total_spent INTEGER DEFAULT 0")
                print("✅ Добавлена колонка total_spent в таблицу users")
            except:
                pass
        
        # Проверяем таблицу orders
        cursor = await db.execute("PRAGMA table_info(orders)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'discount_amount' not in column_names:
            try:
                await db.execute("ALTER TABLE orders ADD COLUMN discount_amount INTEGER DEFAULT 0")
                print("✅ Добавлена колонка discount_amount в таблицу orders")
            except:
                pass
        
        if 'promo_code' not in column_names:
            try:
                await db.execute("ALTER TABLE orders ADD COLUMN promo_code TEXT")
                print("✅ Добавлена колонка promo_code в таблицу orders")
            except:
                pass
        
        await db.commit()

async def fix_orders_table():
    """Пересоздает таблицу orders с новыми полями"""
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        exists = await cursor.fetchone()
        
        if exists:
            await db.execute("CREATE TABLE orders_backup AS SELECT * FROM orders")
            await db.execute("DROP TABLE orders")
        
        await db.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                items TEXT NOT NULL,
                subtotal INTEGER NOT NULL,
                delivery_price INTEGER NOT NULL,
                discount_amount INTEGER DEFAULT 0,
                promo_code TEXT,
                total_amount INTEGER NOT NULL,
                delivery_city TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                delivery_postal_code TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                contact_username TEXT,
                status TEXT DEFAULT 'новый',
                manager_id INTEGER,
                processed_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if exists:
            try:
                await db.execute("""
                    INSERT INTO orders (
                        id, order_number, user_id, items, subtotal, delivery_price, 
                        total_amount, delivery_city, delivery_address, delivery_postal_code,
                        customer_name, contact_username, status, manager_id, 
                        processed_at, completed_at, created_at
                    )
                    SELECT 
                        id, order_number, user_id, items, subtotal, delivery_price,
                        total_amount, delivery_city, delivery_address, delivery_postal_code,
                        customer_name, contact_username, status, manager_id,
                        processed_at, completed_at, created_at
                    FROM orders_backup
                """)
                print("✅ Данные заказов восстановлены")
            except:
                pass
            await db.execute("DROP TABLE orders_backup")
        
        await db.commit()
        print("✅ Таблица orders обновлена")

# ============= БРЕНДЫ =============

async def add_brand(name: str) -> bool:
    async with aiosqlite.connect(db_name) as db:
        try:
            await db.execute("INSERT INTO brands (name) VALUES (?)", (name.lower(),))
            await db.commit()
            return True
        except:
            return False

async def delete_brand(name: str) -> bool:
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM products WHERE brand = ?", (name,))
        count = (await cursor.fetchone())[0]
        if count > 0:
            return False
        await db.execute("DELETE FROM brands WHERE name = ?", (name,))
        await db.commit()
        return True

async def get_brands() -> list:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM brands ORDER BY name ASC")
        rows = await cursor.fetchall()
        return [dict(row)['name'] for row in rows]

async def init_brands(initial_brands: list):
    async with aiosqlite.connect(db_name) as db:
        for brand in initial_brands:
            try:
                await db.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand.lower(),))
            except:
                pass
        await db.commit()

# ============= ТОВАРЫ =============

async def add_product(data: dict) -> int:
    async with aiosqlite.connect(db_name) as db:
        final = int(data['base_price'] * (1 + data['markup']/100))
        cursor = await db.execute(
            "INSERT INTO products (brand, model, base_price, final_price, description, photos) VALUES (?,?,?,?,?,?)",
            (data['brand'], data['model'], data['base_price'], final, data['description'], json.dumps(data['photos']))
        )
        await db.commit()
        return cursor.lastrowid

async def get_products(brand: str = None) -> list:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM products"
        params = []
        if brand:
            query += " WHERE brand = ?"
            params.append(brand)
        query += " ORDER BY added_date DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_product(product_id: int) -> dict:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def delete_product(product_id: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()

# ============= ПОЛЬЗОВАТЕЛИ =============

async def register_user(data: dict):
    async with aiosqlite.connect(db_name) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?,?,?,?)",
            (data['user_id'], data.get('username',''), data.get('first_name',''), data.get('last_name',''))
        )
        await db.commit()

async def get_user(user_id: int) -> dict:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_all_users() -> list:
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def update_user_profile(user_id: int, postal_code: str = None, city: str = None):
    async with aiosqlite.connect(db_name) as db:
        updates = []
        params = []
        if postal_code:
            updates.append("postal_code = ?")
            params.append(postal_code)
        if city:
            updates.append("city = ?")
            params.append(city)
        if updates:
            params.append(user_id)
            await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)
            await db.commit()

# ============= КОРЗИНА =============

async def add_to_cart(user_id: int, product_id: int, size: int) -> bool:
    async with aiosqlite.connect(db_name) as db:
        try:
            await db.execute("INSERT INTO cart (user_id, product_id, size) VALUES (?,?,?)",
                           (user_id, product_id, size))
            await db.commit()
            return True
        except:
            return False

async def remove_from_cart(user_id: int, product_id: int, size: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=? AND size=?",
                       (user_id, product_id, size))
        await db.commit()

async def get_cart(user_id: int) -> list:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT c.*, p.brand, p.model, p.final_price as price
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
            ORDER BY c.added_at DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def clear_cart(user_id: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()

# ============= ЗАКАЗЫ =============

async def create_order(user_id: int, items: list, city: str, postal_code: str, name: str) -> str:
    async with aiosqlite.connect(db_name) as db:
        date = datetime.now().strftime("%d%m%y")
        async with db.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')") as cursor:
            count = (await cursor.fetchone())[0] + 1
        order_number = f"3500-{date}-{count:03d}"
        
        subtotal = sum(i['price'] for i in items)
        
        from config import delivery_price
        total = subtotal + delivery_price
        
        items_data = [{
            'product_id': i['product_id'],
            'brand': i['brand'],
            'model': i['model'],
            'price': i['price'],
            'size': i['size']
        } for i in items]
        
        user = await get_user(user_id)
        contact = f"@{user.get('username')}" if user and user.get('username') else f"id{user_id}"
        
        await db.execute(
            """INSERT INTO orders (
                order_number, user_id, items, subtotal, delivery_price, total_amount,
                delivery_city, delivery_address, delivery_postal_code, 
                customer_name, contact_username
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order_number, user_id, json.dumps(items_data), subtotal, 
                delivery_price, total, city, postal_code, postal_code, 
                name, contact
            )
        )
        await db.commit()
        return order_number

async def get_order(order_number: str) -> dict:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT o.*, u.username
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.user_id
            WHERE o.order_number = ?
        """, (order_number,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_orders(status: str = None, manager_id: int = None) -> list:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT o.*, u.username FROM orders o LEFT JOIN users u ON o.user_id = u.user_id"
        params = []
        conditions = []
        
        if status:
            conditions.append("o.status = ?")
            params.append(status)
        if manager_id:
            conditions.append("o.manager_id = ?")
            params.append(manager_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY o.created_at DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def take_order(order_number: str, manager_id: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute(
            "UPDATE orders SET status = 'в работе', manager_id = ?, processed_at = CURRENT_TIMESTAMP WHERE order_number = ?",
            (manager_id, order_number)
        )
        await db.commit()

async def complete_order(order_number: str, manager_id: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute(
            "UPDATE orders SET status = 'выполнен', completed_at = CURRENT_TIMESTAMP WHERE order_number = ?",
            (order_number,)
        )
        await db.commit()
        cursor = await db.execute("SELECT user_id FROM orders WHERE order_number = ?", (order_number,))
        user_id = (await cursor.fetchone())[0]
        await db.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def cancel_order(order_number: str, manager_id: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute(
            "UPDATE orders SET status = 'отменен', manager_id = ? WHERE order_number = ?",
            (manager_id, order_number)
        )
        await db.commit()

# ============= ПРОМОКОДЫ =============

async def generate_promo_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

async def create_promocode(discount: int, max_uses: int = 1, per_user_limit: int = 1,
                          min_order_amount: int = 0, description: str = None,
                          expires_days: int = 30, custom_code: str = None) -> str:
    async with aiosqlite.connect(db_name) as db:
        if custom_code:
            code = custom_code.upper()
        else:
            code = await generate_promo_code()
        
        expires_at = datetime.now() + timedelta(days=expires_days)
        
        try:
            await db.execute("""
                INSERT INTO promocodes 
                (code, discount, description, max_uses, per_user_limit, min_order_amount, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (code, discount, description, max_uses, per_user_limit, min_order_amount, expires_at))
            await db.commit()
            return code
        except:
            return await create_promocode(discount, max_uses, per_user_limit, 
                                         min_order_amount, description, expires_days)

async def get_promocode(code: str) -> dict:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM promocodes 
            WHERE code = ? AND is_active = 1 
            AND (expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL)
        """, (code.upper(),))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def validate_promocode(code: str, user_id: int, order_amount: int) -> dict:
    promo = await get_promocode(code)
    
    if not promo:
        return {'valid': False, 'reason': '❌ Промокод не найден или истек'}
    
    if promo['used_count'] >= promo['max_uses']:
        return {'valid': False, 'reason': '❌ Промокод больше недействителен'}
    
    if order_amount < promo['min_order_amount']:
        return {'valid': False, 'reason': f'❌ Минимальная сумма заказа: {promo["min_order_amount"]}₸'}
    
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM used_promocodes 
            WHERE user_id = ? AND promo_code = ?
        """, (user_id, code))
        used_count = (await cursor.fetchone())[0]
        
        if used_count >= promo['per_user_limit']:
            return {'valid': False, 'reason': '❌ Вы уже использовали этот промокод'}
    
    return {
        'valid': True,
        'discount': promo['discount'],
        'promo': promo
    }

async def use_promocode(code: str, user_id: int, order_number: str, discount: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
        await db.execute("""
            INSERT INTO used_promocodes (user_id, promo_code, order_number, discount_used)
            VALUES (?, ?, ?, ?)
        """, (user_id, code, order_number, discount))
        await db.commit()

async def get_all_promocodes() -> list:
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def deactivate_promocode(code: str):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE promocodes SET is_active = 0 WHERE code = ?", (code,))
        await db.commit()

# ============= СТАТИСТИКА ПРОМОКОДОВ =============

async def get_promo_stats() -> dict:
    """Получить общую статистику по промокодам"""
    async with aiosqlite.connect(db_name) as db:
        # Общее количество промокодов
        cursor = await db.execute("SELECT COUNT(*) FROM promocodes")
        total = (await cursor.fetchone())[0]
        
        # Активные промокоды
        cursor = await db.execute("SELECT COUNT(*) FROM promocodes WHERE is_active = 1")
        active = (await cursor.fetchone())[0]
        
        # Всего использований
        cursor = await db.execute("SELECT COUNT(*) FROM used_promocodes")
        total_uses = (await cursor.fetchone())[0]
        
        # Общая сумма скидок
        cursor = await db.execute("SELECT SUM(discount_used) FROM used_promocodes")
        total_discount = (await cursor.fetchone())[0] or 0
        
        # Самый популярный промокод
        cursor = await db.execute("""
            SELECT promo_code, COUNT(*) as count 
            FROM used_promocodes 
            GROUP BY promo_code 
            ORDER BY count DESC 
            LIMIT 1
        """)
        top = await cursor.fetchone()
        top_promo = top[0] if top else "нет"
        top_count = top[1] if top else 0
        
        # Средний размер скидки
        cursor = await db.execute("SELECT AVG(discount) FROM promocodes")
        avg_discount = (await cursor.fetchone())[0] or 0
        
        # Истекающие промокоды (ближайшие 7 дней)
        cursor = await db.execute("""
            SELECT COUNT(*) FROM promocodes 
            WHERE expires_at BETWEEN CURRENT_TIMESTAMP AND DATE(CURRENT_TIMESTAMP, '+7 days')
            AND is_active = 1
        """)
        expiring_soon = (await cursor.fetchone())[0]
        
        return {
            'total': total,
            'active': active,
            'total_uses': total_uses,
            'total_discount': total_discount,
            'top_promo': top_promo,
            'top_count': top_count,
            'avg_discount': round(avg_discount, 1),
            'expiring_soon': expiring_soon
        }

async def get_promo_detailed_stats(code: str = None) -> dict:
    """Детальная статистика по конкретному промокоду или всем"""
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        
        if code:
            cursor = await db.execute("""
                SELECT p.*, 
                       (SELECT COUNT(*) FROM used_promocodes WHERE promo_code = p.code) as used,
                       (SELECT SUM(discount_used) FROM used_promocodes WHERE promo_code = p.code) as total_discount,
                       (SELECT COUNT(DISTINCT user_id) FROM used_promocodes WHERE promo_code = p.code) as unique_users
                FROM promocodes p
                WHERE p.code = ?
            """, (code,))
            promo_data = await cursor.fetchone()
            
            if not promo_data:
                return None
            
            cursor = await db.execute("""
                SELECT DATE(used_at) as date, COUNT(*) as count, SUM(discount_used) as discount
                FROM used_promocodes
                WHERE promo_code = ?
                GROUP BY DATE(used_at)
                ORDER BY date DESC
                LIMIT 30
            """, (code,))
            daily_stats = await cursor.fetchall()
            
            cursor = await db.execute("""
                SELECT u.username, u.first_name, up.used_at, up.order_number, up.discount_used
                FROM used_promocodes up
                LEFT JOIN users u ON up.user_id = u.user_id
                WHERE up.promo_code = ?
                ORDER BY up.used_at DESC
                LIMIT 10
            """, (code,))
            recent_uses = await cursor.fetchall()
            
            return {
                'promo': dict(promo_data),
                'daily_stats': [dict(d) for d in daily_stats],
                'recent_uses': [dict(r) for r in recent_uses]
            }
        else:
            cursor = await db.execute("""
                SELECT 
                    p.code,
                    p.discount,
                    p.max_uses,
                    p.used_count,
                    p.is_active,
                    p.expires_at,
                    (SELECT COUNT(*) FROM used_promocodes WHERE promo_code = p.code) as total_uses,
                    (SELECT SUM(discount_used) FROM used_promocodes WHERE promo_code = p.code) as total_discount,
                    (SELECT COUNT(DISTINCT user_id) FROM used_promocodes WHERE promo_code = p.code) as unique_users
                FROM promocodes p
                ORDER BY p.created_at DESC
            """)
            all_stats = await cursor.fetchall()
            
            return [dict(s) for s in all_stats]

# ============= АКЦИИ =============

async def get_promotion_discount() -> int:
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.execute("""
            SELECT SUM(discount) as total FROM promotions 
            WHERE is_active = 1 
            AND promo_required = 0
            AND start_date <= CURRENT_TIMESTAMP 
            AND end_date >= CURRENT_TIMESTAMP
        """)
        result = await cursor.fetchone()
        return result[0] if result[0] else 0