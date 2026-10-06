# MIGRIGA SQLite Database Setup & Seeding
import sqlite3
import os
import json
from .auth import hash_password

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migriga.db")

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
        role TEXT NOT NULL DEFAULT 'customer', -- 'admin' or 'customer'
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
        status TEXT NOT NULL DEFAULT 'Confirmed', -- 'Confirmed', 'Processing', 'Shipped', 'Delivered', 'Cancelled'
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

    conn.commit()

    # --- Seed Default Admin & Customer Accounts ---
    seed_users(cursor)

    # --- Seed Coupons ---
    seed_coupons(cursor)

    # --- Seed 20 Products ---
    seed_products(cursor)

    # --- Seed Sample Order ---
    seed_sample_order(cursor)

    conn.commit()
    conn.close()
    print("MIGRIGA Database successfully initialized and seeded.")

def seed_users(cursor):
    # 1. Admin Account
    cursor.execute("SELECT id FROM users WHERE email = 'admin@migriga.com'")
    if not cursor.fetchone():
        pwd_hash, _ = hash_password("admin123")
        cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role)
        VALUES ('admin@migriga.com', ?, 'MIGRIGA Store Administrator', '+91 12345 67890', 'admin')
        """, (pwd_hash,))
        print("Seeded Admin: admin@migriga.com / admin123")

    # 2. Customer Account
    cursor.execute("SELECT id FROM users WHERE email = 'customer@migriga.com'")
    if not cursor.fetchone():
        pwd_hash, _ = hash_password("customer123")
        cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role)
        VALUES ('customer@migriga.com', ?, 'Aanya Sharma', '+91 98765 43210', 'customer')
        """, (pwd_hash,))
        print("Seeded Customer: customer@migriga.com / customer123")

def seed_coupons(cursor):
    coupons = [
        ('GLOW20', 20, '20% Off Glow Special'),
        ('GLOW30', 30, '30% Off Limited Time Offer'),
        ('WELCOME15', 15, '15% Welcome Subscriber Gift')
    ]
    for code, pct, desc in coupons:
        cursor.execute("""
        INSERT OR IGNORE INTO coupons (code, discount_percent, desc, is_active)
        VALUES (?, ?, ?, 1)
        """, (code, pct, desc))

def seed_products(cursor):
    cursor.execute("SELECT COUNT(*) as count FROM products")
    if cursor.fetchone()['count'] == 0:
        # Load from products list
        products_list = [
            {
                "id": "mig-001",
                "name": "Migriga Glow Radiance Serum",
                "tagline": "Hydrating Botanical Radiance Concentrate",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 899,
                "original_price": 1199,
                "rating": 4.9,
                "review_count": 1420,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 45,
                "image": "assets/images/prod-serum.jpg",
                "secondary_image": "assets/images/cat-skincare.jpg",
                "description": "A transformative lightweight elixir enriched with Hyaluronic Acid, Niacinamide, and Rosehip extracts. Penetrates deep into the dermal layers to restore glass-skin luminosity.",
                "ingredients": "Damask Rose Hydrosol, Botanical Squalane, 5% Niacinamide, Multi-Molecular Hyaluronic Acid, Vitamin E, Centella Asiatica.",
                "how_to_use": "Dispense 3-4 drops onto clean fingertips. Gently press and smooth across face and décolletage every morning and evening before moisturizer.",
                "shades": None,
                "sizes": ["30ml", "50ml (Popular)"],
                "benefits": ["Intense 72-hour hydration", "Visible glass-skin glow within 7 days", "Refines pores & smooths texture", "Non-comedogenic & dermatologist approved"],
                "badge": "★ Award Winner"
            },
            {
                "id": "mig-002",
                "name": "Migriga Luxury Glow Cream",
                "tagline": "Deep Restorative Peptide Soufflé",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 999,
                "original_price": 1299,
                "rating": 4.8,
                "review_count": 980,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 38,
                "image": "assets/images/prod-cream.jpg",
                "secondary_image": "assets/images/prod-nightcream.jpg",
                "description": "An ultra-plush velvet moisture cream that melts upon contact. Fortifies skin barrier lipid defenses while infusing long-lasting dewiness and firmness.",
                "ingredients": "Shea Butter, Triple Ceramide Complex, Copper Tripeptide-1, Japanese Camellia Seed Oil, Adenosine, Marine Collagen.",
                "how_to_use": "Warm a pea-sized amount between clean palms. Sweep gently in upward motions across cleansed face and neck.",
                "shades": None,
                "sizes": ["50ml", "100ml Luxury Jar"],
                "benefits": ["Locks in deep moisture for 48h", "Strengthens moisture barrier", "Silky, non-greasy cashmere feel", "Ideal day & night"],
                "badge": "Bestseller"
            },
            {
                "id": "mig-003",
                "name": "Migriga Rose Bloom Eau de Parfum",
                "tagline": "Romantic Floral & Warm Amber Sillage",
                "category": "fragrance",
                "category_name": "Fragrance",
                "price": 1499,
                "original_price": 1999,
                "rating": 5.0,
                "review_count": 760,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 25,
                "image": "assets/images/prod-perfume.jpg",
                "secondary_image": "assets/images/cat-fragrance.jpg",
                "description": "An enchanting artisanal fragrance capturing blooming Grasse roses, sparkling pink pepper, velvety peony, and a sensuous base of white musk and amber.",
                "ingredients": "Alcohol Denat., Parfum (Fragrance), Aqua, Grasse Rose Absolute, Bergamot Oil, Pink Pepper Essence, White Musk Accord.",
                "how_to_use": "Mist directly onto pulse points: wrists, collarbone, behind ears, and hair mist for an intoxicating scent cloud.",
                "shades": None,
                "sizes": ["50ml Bottle", "100ml Flacon"],
                "benefits": ["Lasts 12+ hours with rich sillage", "Crafted by master French perfumers", "Comes in crystal-cut flacon with gold stopper"],
                "badge": "Signature Scent"
            },
            {
                "id": "mig-004",
                "name": "Migriga Velvet Matte Lipstick",
                "tagline": "Featherlight Cashmere Longwear Pigment",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 699,
                "original_price": 899,
                "rating": 4.9,
                "review_count": 2150,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 60,
                "image": "assets/images/prod-lipstick.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "A revolutionary weightless matte lipstick loaded with hyaluronic filling spheres and jojoba butter. Delivers intensely saturated color that won’t feather or dry out lips.",
                "ingredients": "Dimethicone, Jojoba Esters, Micro-fine Pigments, Sodium Hyaluronate, Vitamin C Palmitate, Candelilla Wax.",
                "how_to_use": "Glide directly across lips from the center outwards. Blot with a tissue for a soft-focus blurred stain effect.",
                "shades": [
                    {"name": "Rose Petal 01", "hex": "#B85D6C"},
                    {"name": "Nude Allure 02", "hex": "#BA7A69"},
                    {"name": "Velvet Crimson 03", "hex": "#9E2A34"},
                    {"name": "Warm Terracotta 04", "hex": "#A3523B"},
                    {"name": "Blush Suede 05", "hex": "#C2847A"}
                ],
                "sizes": ["3.8g Full Size"],
                "benefits": ["10-hour comfortable wear", "Zero dry flaking or creasing", "One-swipe ultra pigment", "Enriched with conditioning oils"],
                "badge": "Trending #1"
            },
            {
                "id": "mig-005",
                "name": "Migriga Silk Touch Foundation",
                "tagline": "Second-Skin Breathable Radiant Base",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 899,
                "original_price": 1199,
                "rating": 4.8,
                "review_count": 1640,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 42,
                "image": "assets/images/prod-foundation.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "An ethereal fluid foundation infused with light-diffusing pearls. Blurs imperfections, evens tone, and imparts a natural soft-lit radiance with breathable medium buildable coverage.",
                "ingredients": "SPF 25 Mineral Screen, Niacinamide, Hyaluronic Acid, Marine Botanicals, Mica, Squalane.",
                "how_to_use": "Shake well. Dispense 1-2 pumps onto the back of your hand. Blend seamlessly using damp sponge or foundation brush.",
                "shades": [
                    {"name": "01 Porcelain Glow", "hex": "#F6E4D6"},
                    {"name": "02 Ivory Beige", "hex": "#EED3BE"},
                    {"name": "03 Warm Sand", "hex": "#DFC0A4"},
                    {"name": "04 Honey Almond", "hex": "#C79D7C"},
                    {"name": "05 Deep Amber", "hex": "#A2704E"}
                ],
                "sizes": ["30ml Glass Pump"],
                "benefits": ["All-day fresh radiant finish", "SPF 25 UV protection", "Transfer-resistant & sweat-proof", "Hydrates while evening skin tone"],
                "badge": "Editor’s Choice"
            },
            {
                "id": "mig-006",
                "name": "Migriga Gold Elixir Facial Oil",
                "tagline": "24K Gold Flake & Marula Botanical Elixir",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 1199,
                "original_price": 1599,
                "rating": 4.9,
                "review_count": 520,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 30,
                "image": "assets/images/prod-oil.jpg",
                "secondary_image": "assets/images/cat-skincare.jpg",
                "description": "Infused with real 24k gold leaf and cold-pressed Marula & Rosehip seed oils. Nourishes tired skin, imparting immediate luminescence and supple bounce.",
                "ingredients": "24K Pure Gold Leaf, Cold-Pressed Marula Oil, Rosehip Seed Oil, Evening Primrose, Neroli Oil.",
                "how_to_use": "Warm 2-3 drops between fingertips and press over moisturizer or mix 1 drop with foundation for an ethereal luminous glow.",
                "shades": None,
                "sizes": ["30ml Dropper"],
                "benefits": ["Immediate radiant sheen", "Deep antioxidant nourishment", "Restores dry, depleted skin"],
                "badge": "Luxury New"
            },
            {
                "id": "mig-007",
                "name": "Migriga Luminous Tinted Lip Balm",
                "tagline": "Hydrating Peptide Sheer Gloss Stick",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 499,
                "original_price": 699,
                "rating": 4.7,
                "review_count": 890,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 55,
                "image": "assets/images/prod-lipbalm.jpg",
                "secondary_image": "assets/images/prod-lipstick.jpg",
                "description": "A cushiony, nourishing lip butter stick tinted with a sheer flush of blooming rose. Packed with peptides and mango seed butter to plump and drench lips in hydration.",
                "ingredients": "Mango Seed Butter, Shea Butter, Palmitoyl Tripeptide-38, Vitamin E, Sweet Almond Oil.",
                "how_to_use": "Swipe generously onto bare lips whenever needed throughout the day for continuous hydration and a glossy, healthy flush.",
                "shades": [
                    {"name": "Blush Glow", "hex": "#E8909A"},
                    {"name": "Peach Nectar", "hex": "#E58E72"},
                    {"name": "Berry Crush", "hex": "#AD4660"}
                ],
                "sizes": ["4g Bullet"],
                "benefits": ["Instantly plumps & conditions", "Non-sticky mirror gloss finish", "Cures chapped dry lips"],
                "badge": "Must Have"
            },
            {
                "id": "mig-008",
                "name": "Migriga Peptide Eye Lifting Cream",
                "tagline": "Awakening Caffeine & Tri-Peptide Treatment",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 849,
                "original_price": 1099,
                "rating": 4.8,
                "review_count": 430,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 35,
                "image": "assets/images/prod-eyecream.jpg",
                "secondary_image": "assets/images/prod-cream.jpg",
                "description": "Targeted cooling eye treatment formulated to dramatically diminish morning puffiness, dark under-eye circles, and fine expression lines with soothing botanical botanicals.",
                "ingredients": "Green Tea Caffeine, Acetyl Tetrapeptide-5, Cucumber Hydrosol, Niacinamide, Chamomile Extract.",
                "how_to_use": "Dispense a rice grain amount onto ring finger. Tap gently around orbital eye contour area morning and night.",
                "shades": None,
                "sizes": ["15ml Precision Tip"],
                "benefits": ["Noticeably depuffs within 10 minutes", "Brightens stubborn dark shadows", "Smooths crow’s feet"],
                "badge": "Clean Beauty"
            },
            {
                "id": "mig-009",
                "name": "Migriga Satin Finish Setting Powder",
                "tagline": "Micro-Milled Translucent Blur Powder",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 749,
                "original_price": 999,
                "rating": 4.8,
                "review_count": 670,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 40,
                "image": "assets/images/prod-powder.jpg",
                "secondary_image": "assets/images/prod-foundation.jpg",
                "description": "Ultra-refined micro-spun mineral translucent setting powder that locks makeup in place for 16 hours without flash-back, dryness, or cakey buildup.",
                "ingredients": "Corn Starch, Mica, Silica, Aloe Leaf Powder, Tocopherol, Lauroyl Lysine.",
                "how_to_use": "Dip the custom velour puff into powder, tap off excess, and press into T-zone and under-eyes to lock in flawless coverage.",
                "shades": [
                    {"name": "Translucent Clear", "hex": "#FAF5EE"},
                    {"name": "Soft Medium Banana", "hex": "#EAD7B5"}
                ],
                "sizes": ["18g Jar with Velour Puff"],
                "benefits": ["Soft-focus camera-ready blur", "Zero flashback under photography", "Absorbs excess oil for 16 hours"],
                "badge": "Pro Artist"
            },
            {
                "id": "mig-010",
                "name": "Migriga Moroccan Argan Hair Serum",
                "tagline": "Liquid Silk Anti-Frizz Gloss Oil",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 799,
                "original_price": 1050,
                "rating": 4.9,
                "review_count": 1120,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 48,
                "image": "assets/images/cat-haircare.jpg",
                "secondary_image": "assets/images/prod-hairserum.jpg",
                "description": "Infused with cold-pressed organic Moroccan Argan Oil and Keratin proteins. Tames flyaways, prevents heat damage up to 230°C, and bestows brilliant mirror shine.",
                "ingredients": "Pure Argania Spinosa Kernel Oil, Camellia Seed Oil, Hydrolyzed Keratin, Cyclomethicone, Fragrance.",
                "how_to_use": "Dispense 1-2 pumps through damp hair before heat styling or smooth onto dry ends for instant glossy polish.",
                "shades": None,
                "sizes": ["100ml Glass Flacon"],
                "benefits": ["Shields against 230°C heat styling", "Banishes humidity frizz instantly", "Never leaves greasy residue"],
                "badge": "Salon Grade"
            },
            {
                "id": "mig-011",
                "name": "Migriga Botanical Overnight Hair Mask",
                "tagline": "Intensive Reconstructing Hair Butter",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 899,
                "original_price": 1199,
                "rating": 4.8,
                "review_count": 490,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 32,
                "image": "assets/images/prod-hairmask.jpg",
                "secondary_image": "assets/images/cat-haircare.jpg",
                "description": "A decadent restorative hair mask infused with Murumuru butter, Biotin, and Castor oil. Deeply rescues dry, damaged, colored, or heat-processed hair.",
                "ingredients": "Astrocaryum Murumuru Butter, Hydrolyzed Wheat Protein, Biotin, Organic Castor Seed Oil, Panthenol.",
                "how_to_use": "Apply generously to damp hair from mid-lengths to ends after shampooing. Leave on for 10-15 minutes (or overnight) before rinsing.",
                "shades": None,
                "sizes": ["200g Tub"],
                "benefits": ["Cuts split-ends by 85%", "Infuses luxurious bounce and silkiness", "Restores moisture barrier of hair cuticles"],
                "badge": "New Release"
            },
            {
                "id": "mig-012",
                "name": "Migriga Amber Vanilla Eau de Parfum",
                "tagline": "Decadent Bourbon Vanilla & Golden Woods",
                "category": "fragrance",
                "category_name": "Fragrance",
                "price": 1599,
                "original_price": 2099,
                "rating": 4.9,
                "review_count": 680,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 20,
                "image": "assets/images/prod-amberperfume.jpg",
                "secondary_image": "assets/images/cat-fragrance.jpg",
                "description": "Warm, cozy, and irresistibly intoxicating. Features notes of golden amber crystal, Madagascan bourbon vanilla beans, creamy sandalwood, and soft tonka bean.",
                "ingredients": "Alcohol Denat., Fragrance (Parfum), Vanilla Tahitensis Extract, Sandalwood Oil, Benzoin Resin, Amber Accord.",
                "how_to_use": "Mist on wrists and neck. Layer over Migriga Rose Bloom for a bespoke sweet floral-oriental scent profile.",
                "shades": None,
                "sizes": ["50ml Bottle", "100ml Flacon"],
                "benefits": ["Addictive warm gourmand trail", "High 22% perfume oil concentration", "Lasts effortlessly all night"],
                "badge": "Customer Obsession"
            },
            {
                "id": "mig-013",
                "name": "Migriga Jasmine Petal Body Mist",
                "tagline": "Refreshing All-Over Scented Glow Mist",
                "category": "fragrance",
                "category_name": "Fragrance",
                "price": 649,
                "original_price": 850,
                "rating": 4.7,
                "review_count": 380,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 50,
                "image": "assets/images/prod-bodymist.jpg",
                "secondary_image": "assets/images/prod-perfume.jpg",
                "description": "An airy, mood-lifting body mist bursting with crisp Indian Sambac jasmine, sparkling mandarin, and white lotus petals. Light enough for anytime wear.",
                "ingredients": "Aloe Barbadensis Leaf Juice, Sambac Jasmine Distillate, Mandarin Peel Extract, Glycerin, Witch Hazel.",
                "how_to_use": "Spritz generously all over body and hair post-shower or whenever you need an uplifting fragrance pick-me-up.",
                "shades": None,
                "sizes": ["150ml Fine Spray Mist"],
                "benefits": ["Infused with soothing organic aloe", "Featherlight non-sticky mist", "Subtle, uplifting floral radiance"],
                "badge": "Everyday Fresh"
            },
            {
                "id": "mig-014",
                "name": "Migriga Gentle Cloud Foam Cleanser",
                "tagline": "pH-Balanced Amino Acid Daily Wash",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 599,
                "original_price": 799,
                "rating": 4.8,
                "review_count": 910,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 44,
                "image": "assets/images/prod-cleanser.jpg",
                "secondary_image": "assets/images/cat-skincare.jpg",
                "description": "A whipped, cloud-like foam cleanser that sweeps away longwear makeup, sunscreen, and daily pollutants without stripping the skin’s essential acid mantle.",
                "ingredients": "Sodium Cocoyl Apple Amino Acids, Chamomile Flower Water, Panthenol, Glycerin, Green Tea Leaf Extract.",
                "how_to_use": "Pump 1-2 clouds of foam into hands. Massage onto damp skin in circular motions for 60 seconds, then rinse with lukewarm water.",
                "shades": None,
                "sizes": ["150ml Self-Foaming Pump"],
                "benefits": ["Sulfate-free pH 5.5 balance", "Leaves skin squeaky soft, not tight", "Dissolves waterproof makeup effortlessly"],
                "badge": "Sensitive Safe"
            },
            {
                "id": "mig-015",
                "name": "Migriga Rosewater Balancing Toner",
                "tagline": "Calming French Rose Petal Infusion",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 649,
                "original_price": 849,
                "rating": 4.7,
                "review_count": 540,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 36,
                "image": "assets/images/prod-toner.jpg",
                "secondary_image": "assets/images/prod-serum.jpg",
                "description": "An alcohol-free calming tonic crafted from 100% steam-distilled French roses and witch hazel. Balances pH, cools redness, and preps pores for serums.",
                "ingredients": "Rosa Damascena Flower Water, Witch Hazel Extract, Sodium Hyaluronate, Willow Bark Extract, Allantoin.",
                "how_to_use": "Sweep onto clean skin using cotton pad or press directly into palms and pat until absorbed.",
                "shades": None,
                "sizes": ["200ml Glass Bottle"],
                "benefits": ["Instantly calms irritation", "Tightens and clarifies pores", "Restores natural skin equilibrium"],
                "badge": "100% Pure"
            },
            {
                "id": "mig-016",
                "name": "Migriga Creamy Sculpt Bronzer",
                "tagline": "Sun-Kissed Dewy Cream Contour Stick",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 749,
                "original_price": 950,
                "rating": 4.9,
                "review_count": 820,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 28,
                "image": "assets/images/prod-bronzer.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "Effortless blendable contour stick that melts seamlessly for natural sun-kissed warmth and chiseled definition with zero muddy undertones.",
                "ingredients": "Castor Seed Oil, Caprylic Triglyceride, Carnauba Wax, Tocopheryl Acetate, Iron Oxides, Mica.",
                "how_to_use": "Swipe along hollows of cheeks, temples, jawline, and collarbones. Blend out using brush, sponge, or warm fingers.",
                "shades": [
                    {"name": "Beach Glow 01 (Light)", "hex": "#C49472"},
                    {"name": "Golden Bronze 02 (Medium)", "hex": "#A76D49"},
                    {"name": "Warm Terracotta 03 (Deep)", "hex": "#7E472A"}
                ],
                "sizes": ["8g Twist-up Stick"],
                "benefits": ["Seamless second-skin melt", "Natural warm glow without glitter", "Foolproof buildable formula"],
                "badge": "Viral Favorite"
            },
            {
                "id": "mig-017",
                "name": "Migriga Vitamin C Brightening Drops",
                "tagline": "15% Ethyl Ascorbic Acid Glow Booster",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 949,
                "original_price": 1249,
                "rating": 4.9,
                "review_count": 1310,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 35,
                "image": "assets/images/prod-vitaminc.jpg",
                "secondary_image": "assets/images/prod-serum.jpg",
                "description": "Stabilized pure vitamin C concentrate designed to fade dark acne spots, hyperpigmentation, and sun damage while boosting collagen synthesis.",
                "ingredients": "15% 3-O-Ethyl Ascorbic Acid, Ferulic Acid, Hyaluronic Acid, Kakadu Plum Extract, Vitamin E.",
                "how_to_use": "Apply 3-4 drops in the morning to clean skin before sunscreen for enhanced environmental defense and radiant skin tone.",
                "shades": None,
                "sizes": ["30ml UV-Protected Bottle"],
                "benefits": ["Fades dark spots in 2 weeks", "Protects against UV photo-aging", "Ultra-stable formula that won’t oxidize"],
                "badge": "Clinical Grade"
            },
            {
                "id": "mig-018",
                "name": "Migriga Precision Micro Brow Definer",
                "tagline": "Ultra-Fine Hair-Like Stroke Eyebrow Pencil",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 499,
                "original_price": 650,
                "rating": 4.7,
                "review_count": 610,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 50,
                "image": "assets/images/prod-brow.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "Featuring an ultra-skinny 1.4mm mechanical tip that draws real micro hair-like strokes for naturally feathered, impeccably defined arches.",
                "ingredients": "Hydrogenated Soybean Oil, Carnauba Wax, Synthetic Japan Wax, Zinc Stearate, Iron Oxides.",
                "how_to_use": "Use delicate upward flicks to fill sparse areas. Flip to spoolie brush end to blend and groom hairs into place.",
                "shades": [
                    {"name": "Soft Charcoal 01", "hex": "#3B3A38"},
                    {"name": "Espresso Brown 02", "hex": "#483529"},
                    {"name": "Warm Taupe 03", "hex": "#6D5B4F"}
                ],
                "sizes": ["0.08g Mechanical Pencil + Spoolie"],
                "benefits": ["Waterproof & smudge-proof", "1.4mm micro tip precision", "Natural matte hair finish"],
                "badge": "Best Brow"
            },
            {
                "id": "mig-019",
                "name": "Migriga Midnight Repair Night Cream",
                "tagline": "Cellular Renewal Night Sleeping Elixir",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 1049,
                "original_price": 1399,
                "rating": 4.8,
                "review_count": 750,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 25,
                "image": "assets/images/prod-nightcream.jpg",
                "secondary_image": "assets/images/prod-cream.jpg",
                "description": "A transformative overnight sleep mask cream loaded with encapsulated retinol and bakuchiol. Repairs cellular micro-damage while you sleep.",
                "ingredients": "0.3% Encapsulated Retinol, 1% Bakuchiol, Evening Primrose, Squalane, Peptides, Allantoin.",
                "how_to_use": "Apply at night to face and neck as the final step in your routine. Wear sunscreen the next morning.",
                "shades": None,
                "sizes": ["50ml Airless Jar"],
                "benefits": ["Accelerates nightly cell turnover", "Smooths fine lines and rough patches", "Wake up to baby-soft radiant skin"],
                "badge": "Night Care"
            },
            {
                "id": "mig-020",
                "name": "Migriga Restorative Scalp & Root Tonic",
                "tagline": "Density Boosting Rosemary & Caffeine Serum",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 749,
                "original_price": 999,
                "rating": 4.8,
                "review_count": 510,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 35,
                "image": "assets/images/cat-haircare.jpg",
                "secondary_image": "assets/images/prod-hairserum.jpg",
                "description": "A non-greasy scalp serum powered by Spanish Rosemary, caffeine, and Red Clover extract. Stimulates microcirculation to promote thicker, denser hair growth.",
                "ingredients": "Rosmarinus Officinalis (Rosemary) Leaf Extract, Caffeine, Red Clover Extract, Biotinoyl Tripeptide-1, Peppermint Oil.",
                "how_to_use": "Part hair into sections and apply 1 full dropper directly to scalp daily. Gently massage with fingertips for 2 minutes. Do not rinse.",
                "shades": None,
                "sizes": ["60ml Precision Dropper"],
                "benefits": ["Reduces seasonal hair thinning", "Stimulates dormant follicles", "Non-oily water-light texture"],
                "badge": "Growth Booster"
            },
            {
                "id": "mig-021",
                "name": "Migriga Aura Shield Invisible Sunscreen SPF 50+",
                "tagline": "Broad Spectrum PA++++ Hydrating Fluid",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 849,
                "original_price": 1099,
                "rating": 4.9,
                "review_count": 840,
                "is_bestseller": 1,
                "is_new": 1,
                "stock": 60,
                "image": "assets/images/prod-sunscreen.jpg",
                "secondary_image": "assets/images/cat-skincare.jpg",
                "description": "An ultra-lightweight, invisible broad-spectrum fluid sunscreen that glides on like silk with zero white cast or greasy sheen. Packed with Hyaluronic Acid and Centella Asiatica for all-day luminous defense.",
                "ingredients": "Zinc Oxide, Titanium Dioxide, Hyaluronic Acid, Centella Asiatica Extract, Niacinamide, Green Tea Extract.",
                "how_to_use": "Apply generously as the final step of your morning skincare ritual, 15 minutes before sun exposure. Reapply every 2-3 hours.",
                "shades": None,
                "sizes": ["50ml Airless Pump", "100ml Value Size"],
                "benefits": ["SPF 50+ PA++++ broad spectrum", "Completely zero white cast", "Water & sweat resistant for 80 mins", "Non-comedogenic & reef safe"],
                "badge": "SPF Hero"
            },
            {
                "id": "mig-022",
                "name": "Migriga Lumière Radiant Liquid Blush",
                "tagline": "Weightless Dewy Pinch of Color",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 649,
                "original_price": 849,
                "rating": 4.9,
                "review_count": 1180,
                "is_bestseller": 1,
                "is_new": 1,
                "stock": 50,
                "image": "assets/images/prod-blush.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "A weightless liquid blush infused with French rose petals and light-reflecting micropigments. Delivers an effortless, healthy-from-within flush that melts seamlessly into bare skin or over foundation.",
                "ingredients": "French Rose Hydrosol, Jojoba Seed Oil, Vitamin E, Micro-fine Mineral Pigments, Squalane, Aloe Vera.",
                "how_to_use": "Dab 1-2 micro dots onto the high apples of your cheeks. Diffuse softly upward toward temples using fingertips, sponge, or brush.",
                "shades": [
                    {"name": "Pétale Doré (Soft Rose)", "hex": "#D67D89"},
                    {"name": "Pêche Lumineuse (Warm Peach)", "hex": "#E58A72"},
                    {"name": "Baie Sucre (Rich Berry)", "hex": "#9C3A53"},
                    {"name": "Terracotta Soleil (Warm Bronze)", "hex": "#B8583B"}
                ],
                "sizes": ["15ml Glass Flacon"],
                "benefits": ["12-hour dewy hydration flush", "Featherlight seamless blend", "Buildable from sheer to bold pop"],
                "badge": "Bestseller New"
            },
            {
                "id": "mig-023",
                "name": "Migriga Haute Volume Panoramic Mascara",
                "tagline": "Dramatic Sculpt & Flake-Free Carbon Black",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 699,
                "original_price": 899,
                "rating": 4.8,
                "review_count": 920,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 45,
                "image": "assets/images/prod-mascara.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "A high-impact volumizing mascara crafted in a heavy fluted gold case. Custom hourglass brush captures every single lash for panoramic lift, incredible separation, and smudge-proof all-day drama.",
                "ingredients": "Carnauba Wax, Rice Bran Wax, Argan Oil, Provitamin B5, Triple Black Carbon Pigment, Acacia Senegal Gum.",
                "how_to_use": "Wiggle the brush from lash base to tip in gentle zig-zag motions. Layer for extreme volume without clumping.",
                "shades": [
                    {"name": "Carbon Black Onyx", "hex": "#1C1B1A"},
                    {"name": "Rich Espresso Brown", "hex": "#3B2F2F"}
                ],
                "sizes": ["10ml Full Size"],
                "benefits": ["36-hour lift and volume hold", "Zero flaking, zero raccoon smudges", "Infused with lash-fortifying peptides"],
                "badge": "Dramatic Lash"
            },
            {
                "id": "mig-024",
                "name": "Migriga Aurora Liquid Starlight Illuminator",
                "tagline": "Micro-Pearl Glass-Skin Highlighter Drops",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 799,
                "original_price": 1049,
                "rating": 4.9,
                "review_count": 1350,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 40,
                "image": "assets/images/prod-highlighter.jpg",
                "secondary_image": "assets/images/prod-foundation.jpg",
                "description": "Custom liquid highlighter drops infused with ultra-refined prismatic champagne and rose gold pearls. Imparts an ethereal, lit-from-within sheen without glitter or chunkiness.",
                "ingredients": "Prismatic Mica, Camellia Japonica Seed Oil, Sodium Hyaluronate, Vitamin E Palmitate, Ethylhexyl Olivate.",
                "how_to_use": "Dispense a drop directly onto cheekbones, brow bone, and cupid’s bow. Alternatively, mix 1 drop into foundation or moisturizer.",
                "shades": [
                    {"name": "Champagne Éclat", "hex": "#F0DAB5"},
                    {"name": "Rose Gold Nectar", "hex": "#E8B4A2"},
                    {"name": "Celestial Bronze", "hex": "#C28E6B"}
                ],
                "sizes": ["30ml Dropper Bottle"],
                "benefits": ["Glass-skin dewy finish", "Never emphasizes texture or pores", "Weightless serum-like blend"],
                "badge": "Viral Glow"
            },
            {
                "id": "mig-025",
                "name": "Migriga Botanical Eucalyptus Nourishing Shampoo",
                "tagline": "Scalp Revitalizing & Sulfate-Free Lather",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 699,
                "original_price": 899,
                "rating": 4.8,
                "review_count": 780,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 55,
                "image": "assets/images/prod-shampoo.jpg",
                "secondary_image": "assets/images/prod-conditioner.jpg",
                "description": "A restorative, sulfate-free salon shampoo formulated with French eucalyptus, tea tree, and plant keratins. Purifies product buildup and pollution while maintaining optimal scalp lipid balance.",
                "ingredients": "French Eucalyptus Essential Oil, Tea Tree Leaf Oil, Hydrolyzed Wheat Keratin, Aloe Leaf Juice, Coconut-Derived Surfactants.",
                "how_to_use": "Massage into wet hair and scalp until a dense, velvety lather forms. Inhale the aromatic botanicals and rinse thoroughly.",
                "shades": None,
                "sizes": ["300ml Pump", "500ml Salon Size"],
                "benefits": ["Balances excess oil & dandruff", "Sulfate, paraben & silicone free", "Leaves hair weightlessly voluminous"],
                "badge": "Pure Scalp"
            },
            {
                "id": "mig-026",
                "name": "Migriga Aura Luxe Botanical Nourishing Conditioner",
                "tagline": "Deep Moisture Detangling & Silk Protein Crème",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 749,
                "original_price": 949,
                "rating": 4.9,
                "review_count": 860,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 50,
                "image": "assets/images/prod-conditioner.jpg",
                "secondary_image": "assets/images/prod-shampoo.jpg",
                "description": "A decadent hair balm conditioner enriched with Moroccan Argan oil, silk amino acids, and white orchid extract. Instantly dissolves knots, smooths coarse hair cuticles, and locks in moisture.",
                "ingredients": "Silk Amino Acids, Cold-Pressed Argania Spinosa Kernel Oil, White Orchid Extract, Shea Butter, Provitamin B5.",
                "how_to_use": "Apply to damp hair from mid-lengths to ends after shampooing. Leave for 3 minutes before rinsing cleanly.",
                "shades": None,
                "sizes": ["300ml Pump", "500ml Salon Size"],
                "benefits": ["Instant effortless comb-through slip", "Repairs heat and chemical dryness", "Adds touchable cashmere softness"],
                "badge": "Silk Soft"
            },
            {
                "id": "mig-027",
                "name": "Migriga Santal & Royal Oud Extrait de Parfum",
                "tagline": "Mystic Smoked Wood & Golden Saffron Sillage",
                "category": "fragrance",
                "category_name": "Fragrance",
                "price": 1799,
                "original_price": 2399,
                "rating": 5.0,
                "review_count": 640,
                "is_bestseller": 1,
                "is_new": 1,
                "stock": 30,
                "image": "assets/images/prod-amberperfume.jpg",
                "secondary_image": "assets/images/cat-fragrance.jpg",
                "description": "An opulent, smoky extrait de parfum blending precious Cambodian oud, Mysore sandalwood, spicy Kashmiri saffron, and rich bourbon vanilla. A commanding fragrance of royalty and warmth.",
                "ingredients": "Alcohol Denat., Fragrance (Parfum), Cambodian Agarwood (Oud) Oil, Sandalwood Essential Oil, Saffron Extract, Ambergris Accord.",
                "how_to_use": "Spray 1-2 spritzes onto collarbones and wrists. Extreme longevity ensures all-day projection.",
                "shades": None,
                "sizes": ["50ml Crystal Flacon", "100ml Collector Bottle"],
                "benefits": ["Extrait concentration (28% perfume oil)", "Projects 14+ hours with magnetic sillage", "Handcrafted artisanal flacon with gold emblem"],
                "badge": "Haute Prestige"
            },
            {
                "id": "mig-028",
                "name": "Migriga Fleur Blanche Citrus & Neroli Cologne",
                "tagline": "Crisp Bergamot & Orange Blossom Refreshment",
                "category": "fragrance",
                "category_name": "Fragrance",
                "price": 1299,
                "original_price": 1699,
                "rating": 4.8,
                "review_count": 410,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 35,
                "image": "assets/images/prod-perfume.jpg",
                "secondary_image": "assets/images/prod-bodymist.jpg",
                "description": "An invigorating, radiant olfactory journey through sun-drenched Mediterranean citrus groves. Crisp Italian bergamot merges with Tunisian neroli, white cedar, and clean solar musk.",
                "ingredients": "Italian Bergamot Oil, Tunisian Neroli Essence, Mandarin Peel Extract, Orange Blossom Absolute, White Cedarwood.",
                "how_to_use": "Mist across neck, wrists, and hair after morning shower for an exhilarating burst of solar energy.",
                "shades": None,
                "sizes": ["50ml Bottle", "100ml Flacon"],
                "benefits": ["Crisp, vibrant, mood-elevating sillage", "Unisex timeless luxury profile", "Steam-distilled natural botanicals"],
                "badge": "Summer Classic"
            },
            {
                "id": "mig-029",
                "name": "Migriga Velvet Lip Glaze & Peptide Oil",
                "tagline": "High-Shine Mirror Finish & Nourishing Cushion",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 599,
                "original_price": 799,
                "rating": 4.9,
                "review_count": 1450,
                "is_bestseller": 1,
                "is_new": 1,
                "stock": 65,
                "image": "assets/images/prod-lipbalm.jpg",
                "secondary_image": "assets/images/prod-lipstick.jpg",
                "description": "A plush, non-sticky lip oil-gloss hybrid packed with Maxi-Lip peptides, raspberry seed oil, and vitamin E. Delivers juicy high-shine glass reflection and deep conditioning.",
                "ingredients": "Raspberry Seed Oil, Maxi-Lip Tripeptide, Jojoba Oil, Tocopherol, Micro-Reflective Silica, Stevia Leaf Extract.",
                "how_to_use": "Swipe using the plush oversized doe-foot applicator across bare lips or layer over Migriga Velvet Matte Lipstick.",
                "shades": [
                    {"name": "Crystal Honey 01", "hex": "#F9D39C"},
                    {"name": "Rose Quartz 02", "hex": "#EAA4B8"},
                    {"name": "Caramel Glaze 03", "hex": "#B87258"},
                    {"name": "Blackberry Shine 04", "hex": "#773549"}
                ],
                "sizes": ["6ml Deluxe Wand"],
                "benefits": ["Zero stickiness with mirror gloss finish", "Cushions and repairs chapped lips", "Visibly plumps lip contours within 10 mins"],
                "badge": "Viral Gloss"
            },
            {
                "id": "mig-030",
                "name": "Migriga Dual-Ended Pro Precision Eyeliner",
                "tagline": "Waterproof Liquid Calligraphy & Gel Crayon",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 549,
                "original_price": 749,
                "rating": 4.8,
                "review_count": 670,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 45,
                "image": "assets/images/prod-brow.jpg",
                "secondary_image": "assets/images/cat-makeup.jpg",
                "description": "A versatile 2-in-1 eyeliner tool featuring an ultra-fine 0.05mm flexible brush tip liquid liner on one end, and a creamy waterproof gel twist crayon on the other.",
                "ingredients": "Acrylates Copolymer, Iron Oxides, Carbon Black, Trimethylsiloxysilicate, Candelilla Wax.",
                "how_to_use": "Use the calligraphy felt tip for sharp feline wings. Use the gel crayon along waterline or tightline for smoky definition.",
                "shades": [
                    {"name": "Midnight Ink Black", "hex": "#111111"},
                    {"name": "Smoked Chocolate Brown", "hex": "#3E2723"}
                ],
                "sizes": ["Dual Pen 0.5ml + 0.2g"],
                "benefits": ["24-hour waterproof and smudge-proof", "Ergonomic calligraphy grip", "Quick dry time with intense jet-black pigment"],
                "badge": "Pro Precision"
            },
            {
                "id": "mig-031",
                "name": "Migriga Hydra-Plump Hyaluronic Acid B5 Serum",
                "tagline": "Multi-Depth 5D Dermal Moisture Booster",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 849,
                "original_price": 1099,
                "rating": 4.9,
                "review_count": 1020,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 40,
                "image": "assets/images/prod-serum.jpg",
                "secondary_image": "assets/images/prod-cream.jpg",
                "description": "An intensive quenching serum featuring 5 molecular weights of pure Hyaluronic Acid combined with Provitamin B5 (Panthenol). Saturates thirsty skin cells from surface to deep dermis.",
                "ingredients": "5D Hyaluronic Acid Complex (Sodium Hyaluronate, Hydrolyzed HA, Sodium Acetylated HA), Panthenol 3%, Betaine, Snow Mushroom Extract.",
                "how_to_use": "Apply 3-4 drops to slightly damp skin morning and night. Follow immediately with your Migriga moisturiser to lock in hydration.",
                "shades": None,
                "sizes": ["30ml Pipette Flacon", "50ml Deluxe Size"],
                "benefits": ["Instantly plumps dehydration fine lines", "Deep moisture saturation for 48 hours", "Ultra-clean, hypoallergenic formula"],
                "badge": "Deep Plump"
            },
            {
                "id": "mig-032",
                "name": "Migriga Clarifying AHA + BHA Glow Peeling Tonic",
                "tagline": "7% Glycolic & Salicylic Pore Refining Solution",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 749,
                "original_price": 999,
                "rating": 4.8,
                "review_count": 880,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 50,
                "image": "assets/images/prod-toner.jpg",
                "secondary_image": "assets/images/cat-skincare.jpg",
                "description": "A multi-acid clarifying exfoliating elixir that gently dissolves dead epidermal cells, unclogs congested pores, and fades post-blemish discoloration for renewed glass clarity.",
                "ingredients": "7% Glycolic Acid, 2% Salicylic Acid, Tasmanian Pepperberry Extract, Aloe Vera Gel, Niacinamide.",
                "how_to_use": "Saturate a cotton pad and sweep across cleansed face 2-3 nights per week. Avoid direct eye area. Always wear SPF the following day.",
                "shades": None,
                "sizes": ["150ml Glass Bottle"],
                "benefits": ["Unclogs stubborn blackheads and sebum", "Smooths uneven bumpy skin texture", "Gentle soothing Tasmanian Pepperberry prevents redness"],
                "badge": "Pore Clarify"
            },
            {
                "id": "mig-033",
                "name": "Migriga Barrier Calm Centella Cica Balm",
                "tagline": "Intensive Skin Barrier Repair & Recovery Cream",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 799,
                "original_price": 1049,
                "rating": 4.9,
                "review_count": 710,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 42,
                "image": "assets/images/prod-cream.jpg",
                "secondary_image": "assets/images/prod-nightcream.jpg",
                "description": "A rich yet non-greasy rescue balm loaded with Centella Asiatica (Madecassoside), Ceramide NP, and colloidal oat. Quickly cools irritation, redness, and compromised skin barriers.",
                "ingredients": "Madecassoside, Asiatic Acid, Ceramide NP, Colloidal Oatmeal, Squalane, Shea Butter, Bisabolol.",
                "how_to_use": "Warm a dime-sized amount between fingers and press onto compromised, sensitized, or peeling areas as needed.",
                "shades": None,
                "sizes": ["50ml Aluminium Squeeze Tube"],
                "benefits": ["Relieves itching and burning in seconds", "Rebuilds compromised skin lipid barrier", "Fragrance-free, steroid-free, dermatologist-tested"],
                "badge": "SOS Barrier"
            },
            {
                "id": "mig-034",
                "name": "Migriga Golden Saffron Radiance Face Mask",
                "tagline": "Ayurvedic Botanical Brightening Clay Soufflé",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 899,
                "original_price": 1199,
                "rating": 4.8,
                "review_count": 630,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 38,
                "image": "assets/images/prod-nightcream.jpg",
                "secondary_image": "assets/images/prod-cream.jpg",
                "description": "A creamy clay mask infused with pure Kashmiri Mogra saffron, wild turmeric, kaolin clay, and sweet almond oil. Purifies impurities without drying, leaving an unmistakable bridal radiance.",
                "ingredients": "Kashmiri Crocus Sativus (Saffron) Stigma, Curcuma Longa, Kaolin Clay, Sweet Almond Oil, Sandalwood Hydrosol.",
                "how_to_use": "Apply an even opaque layer to clean face. Relax for 10-15 minutes until semi-dry. Rinse with warm water in circular buffing motions.",
                "shades": None,
                "sizes": ["100g Porcelain Jar"],
                "benefits": ["Instant luminous bridal glow", "Detoxifies congested pores gently", "Softens and refines dull skin texture"],
                "badge": "Bridal Glow"
            },
            {
                "id": "mig-035",
                "name": "Migriga Heat Shield & Keratin Styling Mist",
                "tagline": "230°C Thermal Protection & Anti-Humidity Spray",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 649,
                "original_price": 849,
                "rating": 4.7,
                "review_count": 520,
                "is_bestseller": 0,
                "is_new": 0,
                "stock": 48,
                "image": "assets/images/cat-haircare.jpg",
                "secondary_image": "assets/images/prod-hairserum.jpg",
                "description": "An invisible micro-mist that coats every strand with a protective thermal keratin shield, shielding hair up to 230°C/450°F against blow dryers, flat irons, and curling wands.",
                "ingredients": "Hydrolyzed Keratin, Bamboo Extract, Argan Oil, Panthenol, Thermal Protection Silicones.",
                "how_to_use": "Shake well. Mist evenly over damp or dry hair in sections prior to using hot styling tools.",
                "shades": None,
                "sizes": ["200ml Fine Mist Spray"],
                "benefits": ["Blocks heat damage up to 230°C", "Blocks humidity for 48-hour sleekness", "Weightless feel with zero sticky crunch"],
                "badge": "Heat Shield"
            },
            {
                "id": "mig-036",
                "name": "Migriga Silk Protein Leave-In Conditioning Milk",
                "tagline": "Weightless Moisture & Split-End Sealant",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 699,
                "original_price": 899,
                "rating": 4.8,
                "review_count": 460,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 44,
                "image": "assets/images/prod-conditioner.jpg",
                "secondary_image": "assets/images/cat-haircare.jpg",
                "description": "A lightweight daily leave-in treatment milk enriched with hydrolyzed silk proteins, marula oil, and green tea antioxidants. Eliminates tangles, seals split ends, and adds high-gloss radiance.",
                "ingredients": "Hydrolyzed Silk Protein, Cold-Pressed Sclerocarya Birrea (Marula) Seed Oil, Camellia Sinensis Leaf, Glycerin.",
                "how_to_use": "Work 1-2 pumps through towel-dried mid-lengths and ends before air-drying or styling. Do not rinse out.",
                "shades": None,
                "sizes": ["150ml Pump Flacon"],
                "benefits": ["Detangles wet hair in one pass", "Seals frizzy and split ends", "Lightweight for fine, medium and coarse hair"],
                "badge": "Daily Silk"
            },
            {
                "id": "mig-037",
                "name": "Migriga Rosemary & Castor Scalp Stimulation Oil",
                "tagline": "Concentrated Follicle Nourishing Elixir",
                "category": "haircare",
                "category_name": "Haircare",
                "price": 799,
                "original_price": 1049,
                "rating": 4.9,
                "review_count": 970,
                "is_bestseller": 1,
                "is_new": 0,
                "stock": 52,
                "image": "assets/images/prod-hairserum.jpg",
                "secondary_image": "assets/images/cat-haircare.jpg",
                "description": "An ultra-potent root therapy oil crafted with organic Spanish Rosemary, Jamaican Black Castor oil, and Fenugreek seed extract. Stimulates blood circulation to nourish roots and strengthen baby hairs.",
                "ingredients": "Rosmarinus Officinalis Oil, Ricinus Communis Seed Oil, Trigonella Foenum-Graecum (Fenugreek) Extract, Amla Oil, Vitamin E.",
                "how_to_use": "Part hair into sections and massage 1-2 pipettes into scalp. Leave on for at least 1 hour or overnight before shampooing.",
                "shades": None,
                "sizes": ["100ml Dropper Bottle"],
                "benefits": ["Nourishes thinning edges and hairline", "Promotes thicker-looking strands", "Natural cold-pressed organic botanicals"],
                "badge": "Root Growth"
            },
            {
                "id": "mig-038",
                "name": "Migriga Velvet Silk Eyeshadow Palette — Sunset Rose",
                "tagline": "9 Buttery Mattes, Molten Metallics & Duochromes",
                "category": "makeup",
                "category_name": "Makeup",
                "price": 1199,
                "original_price": 1599,
                "rating": 4.9,
                "review_count": 780,
                "is_bestseller": 1,
                "is_new": 1,
                "stock": 35,
                "image": "assets/images/cat-makeup.jpg",
                "secondary_image": "assets/images/prod-powder.jpg",
                "description": "A curated 9-pan luxury eyeshadow palette featuring warm sunset terracottas, velvety rose mauves, shimmering molten gold, and duochrome rose quartz. Infused with squalane for buttery adherence.",
                "ingredients": "Mica, Talc, Squalane, Zinc Stearate, Dimethicone, Tocopheryl Acetate, Iron Oxides, Titanium Dioxide.",
                "how_to_use": "Apply mattes across crease for soft sculpting. Press metallic and duochrome foils onto center lid using fingertips for wet-look sparkle.",
                "shades": [
                    {"name": "Sunset Terracotta 01", "hex": "#BA5D4A"},
                    {"name": "Rose Petal Silk 02", "hex": "#D28593"},
                    {"name": "Molten Gold 03", "hex": "#E2AC4C"},
                    {"name": "Smoked Plum 04", "hex": "#5E2B38"}
                ],
                "sizes": ["9 x 1.5g Magnetic Palette"],
                "benefits": ["One-swipe buttery pigmentation", "Zero fallout or creasing for 14 hours", "Includes built-in vanity mirror"],
                "badge": "Artisan Palette"
            },
            {
                "id": "mig-039",
                "name": "Migriga Nectar de Poire & Freesia Eau de Parfum",
                "tagline": "Sparkling English Pear & White Freesia Sillage",
                "category": "fragrance",
                "category_name": "Fragrance",
                "price": 1499,
                "original_price": 1999,
                "rating": 4.9,
                "review_count": 560,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 32,
                "image": "assets/images/prod-perfume.jpg",
                "secondary_image": "assets/images/cat-fragrance.jpg",
                "description": "A joyful, sophisticated perfume capturing juicy autumn King William pears, delicate white blooming freesias, and a sensual base of golden patchouli and sheer amber.",
                "ingredients": "Alcohol Denat., Parfum, Aqua, Pear Accord, White Freesia Extract, Indonesian Patchouli, White Amber Accord.",
                "how_to_use": "Mist lightly on pulse points. Perfect daytime signature scent for elegant everyday wear.",
                "shades": None,
                "sizes": ["50ml Bottle", "100ml Flacon"],
                "benefits": ["Fresh, juicy, and sparkling trail", "10+ hours lasting performance", "French haute parfumerie formulation"],
                "badge": "Juicy Floral"
            },
            {
                "id": "mig-040",
                "name": "Migriga Cashmere Body Soufflé & Glow Crème",
                "tagline": "Ultra-Rich Shea Butter & Gilded Shimmer Crème",
                "category": "skincare",
                "category_name": "Skincare",
                "price": 799,
                "original_price": 1050,
                "rating": 4.8,
                "review_count": 690,
                "is_bestseller": 0,
                "is_new": 1,
                "stock": 48,
                "image": "assets/images/prod-cream.jpg",
                "secondary_image": "assets/images/prod-oil.jpg",
                "description": "A decadent, whipped body butter infused with African Shea butter, sweet almond oil, and micro-fine golden pearl dust. Deeply quenches dry skin and leaves a captivating luminous radiance.",
                "ingredients": "Unrefined Butyrospermum Parkii (Shea) Butter, Sweet Almond Oil, Cocoa Seed Butter, Squalane, Gold Mica, Parfum.",
                "how_to_use": "Smooth generously all over arms, legs, and décolletage after shower or bath. Absorbs quickly without greasy transfer.",
                "shades": None,
                "sizes": ["250g Luxury Tub"],
                "benefits": ["72-hour moisture cushion for dry skin", "Subtle candlelit skin glow", "Infused with delicate vanilla rose scent"],
                "badge": "Body Luxe"
            }
        ]

        for p in products_list:
            cursor.execute("""
            INSERT OR REPLACE INTO products (
                id, name, tagline, category, category_name, price, original_price,
                rating, review_count, is_bestseller, is_new, stock, image, secondary_image,
                description, ingredients, how_to_use, shades_json, sizes_json, benefits_json, badge
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["id"], p["name"], p["tagline"], p["category"], p["category_name"],
                p["price"], p["original_price"], p["rating"], p["review_count"],
                p["is_bestseller"], p["is_new"], p["stock"], p["image"], p["secondary_image"],
                p["description"], p["ingredients"], p["how_to_use"],
                json.dumps(p["shades"]) if p["shades"] else None,
                json.dumps(p["sizes"]) if p["sizes"] else None,
                json.dumps(p["benefits"]) if p["benefits"] else None,
                p["badge"]
            ))
        print("Seeded 40 Products into SQLite database.")

def seed_sample_order(cursor):
    cursor.execute("SELECT id FROM orders WHERE id = 'MIG-89412'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO orders (
            id, user_id, customer_name, customer_email, customer_phone,
            address, city, pincode, payment_method, status,
            subtotal, discount, shipping, total, created_at
        ) VALUES (
            'MIG-89412', 2, 'Aanya Sharma', 'customer@migriga.com', '+91 98765 43210',
            'Penthouse 4B, Emerald Heights, Linking Road', 'Mumbai', '400050',
            'UPI', 'Delivered', 899, 0, 0, 899, '2026-09-28 14:20:00'
        )
        """)
        cursor.execute("""
        INSERT INTO order_items (
            order_id, product_id, product_name, qty, price, shade, size, image
        ) VALUES (
            'MIG-89412', 'mig-001', 'Migriga Glow Radiance Serum', 1, 899, NULL, '30ml', 'assets/images/prod-serum.jpg'
        )
        """)
        print("Seeded sample delivered order #MIG-89412.")

if __name__ == "__main__":
    init_db()
