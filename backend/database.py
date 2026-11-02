# MIGRIGA SQLite Database Setup & Seeding
import sqlite3
import os
import json

try:
    from .auth import hash_password
except ImportError:
    try:
        from backend.auth import hash_password
    except ModuleNotFoundError:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    seed_subscribers(cursor)
    seed_synthetic_retail_orders(cursor)

    conn.commit()
    conn.close()
    print("MIGRIGA Database successfully initialized and seeded with UK Retail items, customers, subscribers, and orders.")

def seed_users(cursor):
    pwd_hash, _ = hash_password("admin123")
    cursor.execute("""
    INSERT INTO users (email, password_hash, full_name, phone, role)
    VALUES ('admin@migriga.com', ?, 'MIGRIGA Store Administrator', '+44 20 7946 0192', 'admin')
    ON CONFLICT(email) DO UPDATE SET
        full_name = 'MIGRIGA Store Administrator',
        phone = '+44 20 7946 0192',
        role = 'admin'
    """, (pwd_hash,))

    cust_pwd_hash, _ = hash_password("customer123")
    cursor.execute("""
    INSERT INTO users (email, password_hash, full_name, phone, role)
    VALUES ('customer@migriga.com', ?, 'Aanya Sharma', '+44 7700 900077', 'customer')
    ON CONFLICT(email) DO UPDATE SET
        full_name = 'Aanya Sharma',
        phone = '+44 7700 900077',
        role = 'customer'
    """, (cust_pwd_hash,))

    # Synthetic British Retail Customers
    customers = [
        ("Eleanor Vance", "eleanor.vance@heritagemail.co.uk", "+44 20 7946 0831", "2026-08-12 10:15:00"),
        ("Oliver Kensington", "o.kensington@cotswoldliving.co.uk", "+44 1608 650219", "2026-08-20 14:22:00"),
        ("Beatrice Holloway", "beatrice.holloway@oxfordalumni.org", "+44 1865 270000", "2026-08-29 09:40:00"),
        ("Charlotte Montgomery", "c.montgomery@bathspa.ac.uk", "+44 1225 388388", "2026-09-04 16:30:00"),
        ("Henry Cavendish", "henry.cavendish@mayfairarts.com", "+44 20 7183 4521", "2026-09-10 11:05:00"),
        ("Fiona MacLeod", "fiona.macleod@edinburghvintage.co.uk", "+44 131 496 0321", "2026-09-15 13:50:00"),
        ("Arthur Pendelton", "arthur.pendelton@yorkshireheritage.co.uk", "+44 1904 621144", "2026-09-19 17:15:00"),
        ("Victoria Sterling", "victoria.sterling@kensingtongift.co.uk", "+44 20 8960 7712", "2026-09-25 12:45:00"),
        ("Julian Thorne", "julian.thorne@cambridgebooks.co.uk", "+44 1223 337733", "2026-10-01 15:20:00"),
        ("Penelope Wright", "penelope.wright@chelseahome.com", "+44 20 7352 8111", "2026-10-06 08:30:00"),
        ("Sebastian Finch", "sebastian.finch@manchesterdesign.co.uk", "+44 161 234 5000", "2026-10-11 14:10:00"),
        ("Evelyn Beauchamp", "evelyn.beauchamp@bristolceramics.org", "+44 117 922 2000", "2026-10-16 11:35:00"),
        ("Rupert Langley", "rupert.langley@countryliving.co.uk", "+44 1386 840333", "2026-10-20 16:40:00"),
        ("Clara Davenport", "clara.davenport@richmondgarden.co.uk", "+44 20 8940 1234", "2026-10-24 10:00:00"),
        ("Alistair Graham", "alistair.graham@highlandantiques.co.uk", "+44 1463 234123", "2026-10-27 13:25:00"),
        ("Harriet Shaw", "harriet.shaw@windsorantiques.com", "+44 1753 860111", "2026-10-30 09:15:00")
    ]
    for name, email, phone, created_at in customers:
        cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role, created_at)
        VALUES (?, ?, ?, ?, 'customer', ?)
        ON CONFLICT(email) DO UPDATE SET
            full_name = excluded.full_name,
            phone = excluded.phone,
            role = 'customer'
        """, (email, cust_pwd_hash, name, phone, created_at))

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

def seed_subscribers(cursor):
    cursor.execute("SELECT COUNT(*) FROM newsletter_subscribers")
    if cursor.fetchone()[0] > 0:
        return
    subs = [
        ("eleanor.vance@heritagemail.co.uk", "WELCOME15", "2026-08-12 10:18:00"),
        ("o.kensington@cotswoldliving.co.uk", "HERITAGE20", "2026-08-20 14:25:00"),
        ("beatrice.holloway@oxfordalumni.org", "WELCOME15", "2026-08-29 09:42:00"),
        ("sophie.turner.tea@gmail.com", "WELCOME15", "2026-09-01 11:30:00"),
        ("c.montgomery@bathspa.ac.uk", "WELCOME15", "2026-09-04 16:35:00"),
        ("william.b.crafts@outlook.com", "WELCOME15", "2026-09-06 14:12:00"),
        ("gemma.cottagecrafts@btinternet.com", "HERITAGE30", "2026-09-08 19:40:00"),
        ("henry.cavendish@mayfairarts.com", "RETAIL20", "2026-09-10 11:10:00"),
        ("james.millar92@gmail.com", "WELCOME15", "2026-09-12 08:22:00"),
        ("fiona.macleod@edinburghvintage.co.uk", "WELCOME15", "2026-09-15 13:55:00"),
        ("elizabeth.bennet.heritage@yahoo.co.uk", "RETAIL20", "2026-09-17 15:45:00"),
        ("arthur.pendelton@yorkshireheritage.co.uk", "WELCOME15", "2026-09-19 17:20:00"),
        ("hannah.vintagehome@icloud.com", "WELCOME15", "2026-09-22 10:05:00"),
        ("victoria.sterling@kensingtongift.co.uk", "HERITAGE30", "2026-09-25 12:50:00"),
        ("thomas.edinburghdecor@btconnect.com", "WELCOME15", "2026-09-28 16:18:00"),
        ("lucy.afternoontea@gmail.com", "HERITAGE30", "2026-09-30 18:30:00"),
        ("julian.thorne@cambridgebooks.co.uk", "WELCOME15", "2026-10-01 15:25:00"),
        ("richard.pendleton@heritageuk.net", "WELCOME15", "2026-10-04 12:14:00"),
        ("penelope.wright@chelseahome.com", "WELCOME15", "2026-10-06 08:35:00"),
        ("grace.darling.decor@gmail.com", "WELCOME15", "2026-10-08 14:50:00"),
        ("sebastian.finch@manchesterdesign.co.uk", "RETAIL20", "2026-10-11 14:15:00"),
        ("edward.fairfax@oxfordheritage.co.uk", "RETAIL20", "2026-10-13 17:02:00"),
        ("rosalind.f@kensingtonantiques.org", "WELCOME15", "2026-10-15 09:28:00"),
        ("evelyn.beauchamp@bristolceramics.org", "WELCOME15", "2026-10-16 11:40:00"),
        ("george.hartley@cotswoldsfolk.co.uk", "WELCOME15", "2026-10-18 13:45:00"),
        ("rupert.langley@countryliving.co.uk", "HERITAGE20", "2026-10-20 16:45:00"),
        ("isla.cameron@highlandhome.scot", "WELCOME15", "2026-10-22 11:12:00"),
        ("clara.davenport@richmondgarden.co.uk", "WELCOME15", "2026-10-24 10:05:00"),
        ("charles.beverley@bathsociety.co.uk", "WELCOME15", "2026-10-26 15:30:00"),
        ("alistair.graham@highlandantiques.co.uk", "HERITAGE15", "2026-10-27 13:30:00"),
        ("miranda.priestly@mayfairliving.com", "RETAIL20", "2026-10-28 16:55:00"),
        ("harriet.shaw@windsorantiques.com", "WELCOME15", "2026-10-30 09:20:00"),
        ("amelia.rose.teaware@outlook.com", "WELCOME15", "2026-11-01 10:40:00"),
        ("kate.winslet.cottage@gmail.com", "WELCOME15", "2026-11-02 12:15:00")
    ]
    for email, voucher, created_at in subs:
        cursor.execute("INSERT OR IGNORE INTO newsletter_subscribers (email, voucher_code, created_at) VALUES (?, ?, ?)", (email, voucher, created_at))

def seed_synthetic_retail_orders(cursor):
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] >= 20:
        return

    # Delete any legacy beauty orders
    cursor.execute("DELETE FROM order_items WHERE product_id LIKE 'mig-%'")
    cursor.execute("DELETE FROM orders WHERE id NOT IN (SELECT DISTINCT order_id FROM order_items)")

    # Call external seeder if available
    try:
        from .seed_synthetic_data import run_seeding
        run_seeding(DB_PATH)
    except Exception:
        pass

if __name__ == "__main__":
    init_db()
