# MIGRIGA SQLite Database Setup & Seeding
import sqlite3
import os
import json

try:
    from .auth import hash_password
except ImportError:
    from backend.auth import hash_password

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migriga.db")
CATALOG_SEED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_seed.json")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table (Customer & Admin roles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT,
        role TEXT NOT NULL DEFAULT 'customer',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Active Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 3. Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tagline TEXT,
        category TEXT NOT NULL,
        category_name TEXT NOT NULL,
        price REAL NOT NULL,
        original_price REAL,
        rating REAL DEFAULT 4.8,
        review_count INTEGER DEFAULT 0,
        is_bestseller INTEGER DEFAULT 0,
        is_new INTEGER DEFAULT 0,
        stock INTEGER DEFAULT 50,
        image TEXT NOT NULL,
        secondary_image TEXT,
        description TEXT,
        ingredients TEXT,
        how_to_use TEXT,
        shades_json TEXT,
        sizes_json TEXT,
        benefits_json TEXT,
        badge TEXT
    )
    """)

    # 4. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        user_id INTEGER NULL REFERENCES users(id),
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        pincode TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Confirmed',
        subtotal REAL NOT NULL,
        discount REAL NOT NULL DEFAULT 0,
        shipping REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Order Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL REFERENCES orders(id),
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        shade TEXT,
        size TEXT,
        image TEXT
    )
    """)

    # 6. Coupons Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY,
        discount_percent INTEGER NOT NULL,
        desc TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 7. Newsletter Subscribers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS newsletter_subscribers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        voucher_code TEXT DEFAULT 'WELCOME15',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. High-Performance Query Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

    conn.commit()

    # Seed Data
    seed_users(cursor)
    seed_coupons(cursor)
    seed_products(cursor)
    seed_sample_order(cursor)

    conn.commit()
    conn.close()
    print("MIGRIGA Database successfully initialized and seeded with UK Retail items.")

def seed_users(cursor):
    cursor.execute("SELECT id FROM users WHERE email = 'admin@migriga.com'")
    if not cursor.fetchone():
        pwd_hash, _ = hash_password("admin123")
        cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role)
        VALUES ('admin@migriga.com', ?, 'MIGRIGA Store Administrator', '+44 20 7946 0192', 'admin')
        """, (pwd_hash,))
        print("Seeded Admin: admin@migriga.com / admin123")

    cursor.execute("SELECT id FROM users WHERE email = 'customer@migriga.com'")
    if not cursor.fetchone():
        pwd_hash, _ = hash_password("customer123")
        cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role)
        VALUES ('customer@migriga.com', ?, 'Aanya Sharma', '+44 7700 900077', 'customer')
        """, (pwd_hash,))
        print("Seeded Customer: customer@migriga.com / customer123")

def seed_coupons(cursor):
    coupons = [
        ('RETAIL20', 20, '20% Off Retail Special'),
        ('HERITAGE30', 30, '30% Off Limited Time Heritage Collection'),
        ('WELCOME15', 15, '15% Welcome Subscriber Gift')
    ]
    for code, pct, desc in coupons:
        cursor.execute("""
        INSERT OR IGNORE INTO coupons (code, discount_percent, desc, is_active)
        VALUES (?, ?, ?, 1)
        """, (code, pct, desc))

def seed_products(cursor):
    if not os.path.exists(CATALOG_SEED_PATH):
        print(f"[Warning] {CATALOG_SEED_PATH} not found.")
        return

    # Clear legacy beauty products
    cursor.execute("DELETE FROM products WHERE id LIKE 'mig-%'")

    with open(CATALOG_SEED_PATH, "r", encoding="utf-8") as f:
        products_list = json.load(f)

    for p in products_list:
        cursor.execute("""
        INSERT OR REPLACE INTO products (
            id, name, tagline, category, category_name, price, original_price,
            rating, review_count, is_bestseller, is_new, stock, image, secondary_image,
            description, ingredients, how_to_use, shades_json, sizes_json, benefits_json, badge
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["id"], p["name"], p["tagline"], p["category"], p["categoryName"],
            p["price"], p["originalPrice"], p["rating"], p["reviewCount"],
            1 if p.get("isBestseller") else 0, 1 if p.get("isNew") else 0, p["stock"],
            p["image"], p["secondaryImage"], p["description"],
            p["ingredients"], p["howToUse"],
            json.dumps(p["shades"]) if p.get("shades") else None,
            json.dumps(p["sizes"]) if p.get("sizes") else None,
            json.dumps(p["benefits"]) if p.get("benefits") else None,
            p["badge"]
        ))
    print(f"Seeded {len(products_list)} UK Retail products into SQLite.")

def seed_sample_order(cursor):
    cursor.execute("SELECT id FROM orders WHERE id = 'MIG-89412'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO orders (
            id, user_id, customer_name, customer_email, customer_phone,
            address, city, pincode, payment_method, status,
            subtotal, discount, shipping, total, created_at
        ) VALUES (
            'MIG-89412', 2, 'Aanya Sharma', 'customer@migriga.com', '+44 7700 900077',
            'Flat 4B, Kensington Court Gardens', 'London', 'W8 5HN', 'Card', 'Delivered',
            17.45, 0.00, 0.00, 17.45, '2026-10-20 14:32:00'
        )
        """)

        cursor.execute("""
        INSERT INTO order_items (
            order_id, product_id, product_name, qty, price, shade, size, image
        ) VALUES (
            'MIG-89412', 'ret-22423', 'Regency Cakestand 3 Tier', 1, 14.37, NULL, 'Standard Edition', 'assets/images/prod-cakestand.jpg'
        ), (
            'MIG-89412', 'ret-85123a', 'White Hanging Heart T-LIGHT Holder', 1, 3.08, NULL, 'Single Accent', 'assets/images/cat-homeware.jpg'
        )
        """)

if __name__ == "__main__":
    init_db()
