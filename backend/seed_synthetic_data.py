# Synthetic Data Generator & Seeder for MIGRIGA British Heritage Living & Retail
# Generates realistic UK customer accounts, newsletter subscribers, and order histories.
import os
import sys
import json
import sqlite3
import random
from datetime import datetime, timedelta

# Ensure backend modules can be imported
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.auth import hash_password

DB_PATH = os.path.join(BASE_DIR, "migriga.db")
CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_seed.json")

# UK Customer profiles
CUSTOMERS_DATA = [
    {
        "name": "Eleanor Vance",
        "email": "eleanor.vance@heritagemail.co.uk",
        "phone": "+44 20 7946 0831",
        "address": "18 Cheyne Walk, Chelsea",
        "city": "London",
        "pincode": "SW3 5HN",
        "created_at": "2026-08-12 10:15:00"
    },
    {
        "name": "Oliver Kensington",
        "email": "o.kensington@cotswoldliving.co.uk",
        "phone": "+44 1608 650219",
        "address": "High Street, Chipping Campden",
        "city": "Cotswolds",
        "pincode": "GL55 6AT",
        "created_at": "2026-08-20 14:22:00"
    },
    {
        "name": "Beatrice Holloway",
        "email": "beatrice.holloway@oxfordalumni.org",
        "phone": "+44 1865 270000",
        "address": "24 St Giles'",
        "city": "Oxford",
        "pincode": "OX1 3LW",
        "created_at": "2026-08-29 09:40:00"
    },
    {
        "name": "Charlotte Montgomery",
        "email": "c.montgomery@bathspa.ac.uk",
        "phone": "+44 1225 388388",
        "address": "12 Royal Crescent",
        "city": "Bath",
        "pincode": "BA1 2LR",
        "created_at": "2026-09-04 16:30:00"
    },
    {
        "name": "Henry Cavendish",
        "email": "henry.cavendish@mayfairarts.com",
        "phone": "+44 20 7183 4521",
        "address": "7 Berkeley Square, Mayfair",
        "city": "London",
        "pincode": "W1J 6ER",
        "created_at": "2026-09-10 11:05:00"
    },
    {
        "name": "Fiona MacLeod",
        "email": "fiona.macleod@edinburghvintage.co.uk",
        "phone": "+44 131 496 0321",
        "address": "15 Heriot Row, New Town",
        "city": "Edinburgh",
        "pincode": "EH3 6HU",
        "created_at": "2026-09-15 13:50:00"
    },
    {
        "name": "Arthur Pendelton",
        "email": "arthur.pendelton@yorkshireheritage.co.uk",
        "phone": "+44 1904 621144",
        "address": "9 The Shambles",
        "city": "York",
        "pincode": "YO1 7LZ",
        "created_at": "2026-09-19 17:15:00"
    },
    {
        "name": "Victoria Sterling",
        "email": "victoria.sterling@kensingtongift.co.uk",
        "phone": "+44 20 8960 7712",
        "address": "33 Holland Park Avenue",
        "city": "London",
        "pincode": "W11 3RW",
        "created_at": "2026-09-25 12:45:00"
    },
    {
        "name": "Julian Thorne",
        "email": "julian.thorne@cambridgebooks.co.uk",
        "phone": "+44 1223 337733",
        "address": "14 King's Parade",
        "city": "Cambridge",
        "pincode": "CB2 1SJ",
        "created_at": "2026-10-01 15:20:00"
    },
    {
        "name": "Penelope Wright",
        "email": "penelope.wright@chelseahome.com",
        "phone": "+44 20 7352 8111",
        "address": "52 King's Road, Chelsea",
        "city": "London",
        "pincode": "SW3 4UD",
        "created_at": "2026-10-06 08:30:00"
    },
    {
        "name": "Sebastian Finch",
        "email": "sebastian.finch@manchesterdesign.co.uk",
        "phone": "+44 161 234 5000",
        "address": "45 Deansgate",
        "city": "Manchester",
        "pincode": "M3 2AY",
        "created_at": "2026-10-11 14:10:00"
    },
    {
        "name": "Evelyn Beauchamp",
        "email": "evelyn.beauchamp@bristolceramics.org",
        "phone": "+44 117 922 2000",
        "address": "8 Clifton Down Road",
        "city": "Bristol",
        "pincode": "BS8 4AA",
        "created_at": "2026-10-16 11:35:00"
    },
    {
        "name": "Rupert Langley",
        "email": "rupert.langley@countryliving.co.uk",
        "phone": "+44 1386 840333",
        "address": "Meadow View Cottage, Church Street",
        "city": "Broadway",
        "pincode": "WR12 7AE",
        "created_at": "2026-10-20 16:40:00"
    },
    {
        "name": "Clara Davenport",
        "email": "clara.davenport@richmondgarden.co.uk",
        "phone": "+44 20 8940 1234",
        "address": "29 Richmond Hill",
        "city": "Richmond",
        "pincode": "TW10 6RE",
        "created_at": "2026-10-24 10:00:00"
    },
    {
        "name": "Alistair Graham",
        "email": "alistair.graham@highlandantiques.co.uk",
        "phone": "+44 1463 234123",
        "address": "4 Castle Wynd",
        "city": "Inverness",
        "pincode": "IV2 3EB",
        "created_at": "2026-10-27 13:25:00"
    },
    {
        "name": "Harriet Shaw",
        "email": "harriet.shaw@windsorantiques.com",
        "phone": "+44 1753 860111",
        "address": "16 Thames Street",
        "city": "Windsor",
        "pincode": "SL4 1PL",
        "created_at": "2026-10-30 09:15:00"
    }
]

# Subscribers interested in British Heritage Living
SUBSCRIBERS_DATA = [
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

def load_catalog_products():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        products = json.load(f)
    return {p["id"]: p for p in products}

def run_seeding(db_path=DB_PATH):
    print(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    catalog_map = load_catalog_products()
    catalog_list = list(catalog_map.values())

    # 1. Update/Seed Admin and Seeded Customer (Aanya Sharma)
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

    # 2. Seed Registered Customer Accounts
    customer_user_ids = {}
    for c in CUSTOMERS_DATA:
        cursor.execute("""
            INSERT INTO users (email, password_hash, full_name, phone, role, created_at)
            VALUES (?, ?, ?, ?, 'customer', ?)
            ON CONFLICT(email) DO UPDATE SET
                full_name = excluded.full_name,
                phone = excluded.phone,
                role = 'customer'
        """, (c["email"], cust_pwd_hash, c["name"], c["phone"], c["created_at"]))

    # Fetch user IDs for all customers
    cursor.execute("SELECT id, email FROM users")
    for row in cursor.fetchall():
        customer_user_ids[row["email"]] = row["id"]

    print(f"Registered customers active in DB: {len(customer_user_ids)}")

    # 3. Seed Newsletter Subscribers
    cursor.execute("DELETE FROM newsletter_subscribers")
    for email, voucher, created_at in SUBSCRIBERS_DATA:
        cursor.execute("""
            INSERT INTO newsletter_subscribers (email, voucher_code, created_at)
            VALUES (?, ?, ?)
        """, (email, voucher, created_at))
    print(f"Seeded {len(SUBSCRIBERS_DATA)} newsletter subscribers.")

    # 4. Clean up legacy orders and order items (e.g. mig-001, beauty dataset)
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    print("Cleaned legacy orders and items from SQLite.")

    # 5. Define 26 authentic British Heritage Living orders
    orders_spec = [
        {
            "id": "MIG-89412",
            "email": "customer@migriga.com",
            "name": "Aanya Sharma",
            "phone": "+44 7700 900077",
            "address": "Flat 4B, Kensington Court Gardens",
            "city": "London",
            "pincode": "W8 5HN",
            "payment": "Credit Card",
            "status": "Delivered",
            "created_at": "2026-09-08 14:32:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 1, "Standard Edition"),
                ("ret-85123a", 2, "Single Accent")
            ]
        },
        {
            "id": "MIG-89840",
            "email": "eleanor.vance@heritagemail.co.uk",
            "name": "Eleanor Vance",
            "phone": "+44 20 7946 0831",
            "address": "18 Cheyne Walk, Chelsea",
            "city": "London",
            "pincode": "SW3 5HN",
            "payment": "Apple Pay",
            "status": "Delivered",
            "created_at": "2026-09-12 11:20:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 2, "Hostess Gift Set"),
                ("ret-21843", 1, "Standard Size")
            ]
        },
        {
            "id": "MIG-90145",
            "email": "o.kensington@cotswoldliving.co.uk",
            "name": "Oliver Kensington",
            "phone": "+44 1608 650219",
            "address": "High Street, Chipping Campden",
            "city": "Cotswolds",
            "pincode": "GL55 6AT",
            "payment": "Debit Card",
            "status": "Delivered",
            "created_at": "2026-09-16 16:05:00",
            "discount_pct": 20,
            "shipping": 0.00,
            "items": [
                ("ret-48138", 2, "Standard Size"),
                ("ret-85123a", 4, "Set of 2 (Twin Pack)")
            ]
        },
        {
            "id": "MIG-90712",
            "email": "beatrice.holloway@oxfordalumni.org",
            "name": "Beatrice Holloway",
            "phone": "+44 1865 270000",
            "address": "24 St Giles'",
            "city": "Oxford",
            "pincode": "OX1 3LW",
            "payment": "PayPal",
            "status": "Delivered",
            "created_at": "2026-09-20 09:14:00",
            "discount_pct": 0,
            "shipping": 4.99,
            "items": [
                ("ret-84879", 3, "Handcrafted Piece"),
                ("ret-22086", 2, "Standard Edition")
            ]
        },
        {
            "id": "MIG-91280",
            "email": "customer@migriga.com",
            "name": "Aanya Sharma",
            "phone": "+44 7700 900077",
            "address": "Flat 4B, Kensington Court Gardens",
            "city": "London",
            "pincode": "W8 5HN",
            "payment": "Credit Card",
            "status": "Delivered",
            "created_at": "2026-09-24 15:45:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-21621", 2, "Standard Size"),
                ("ret-47566", 2, "Standard Size"),
                ("ret-85099b", 3, "Standard Edition")
            ]
        },
        {
            "id": "MIG-91544",
            "email": "c.montgomery@bathspa.ac.uk",
            "name": "Charlotte Montgomery",
            "phone": "+44 1225 388388",
            "address": "12 Royal Crescent",
            "city": "Bath",
            "pincode": "BA1 2LR",
            "payment": "Credit Card",
            "status": "Delivered",
            "created_at": "2026-09-28 10:30:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-15056n", 2, "Standard Edition"),
                ("ret-84347", 2, "Single Accent")
            ]
        },
        {
            "id": "MIG-91890",
            "email": "henry.cavendish@mayfairarts.com",
            "name": "Henry Cavendish",
            "phone": "+44 20 7183 4521",
            "address": "7 Berkeley Square, Mayfair",
            "city": "London",
            "pincode": "W1J 6ER",
            "payment": "Apple Pay",
            "status": "Delivered",
            "created_at": "2026-10-02 12:10:00",
            "discount_pct": 20,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 3, "Hostess Gift Set"),
                ("ret-20914", 2, "Standard Size")
            ]
        },
        {
            "id": "MIG-92104",
            "email": "fiona.macleod@edinburghvintage.co.uk",
            "name": "Fiona MacLeod",
            "phone": "+44 131 496 0321",
            "address": "15 Heriot Row, New Town",
            "city": "Edinburgh",
            "pincode": "EH3 6HU",
            "payment": "Debit Card",
            "status": "Delivered",
            "created_at": "2026-10-05 14:40:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-20685", 2, "Standard Size"),
                ("ret-48138", 1, "Standard Size"),
                ("ret-85099f", 4, "Standard Edition")
            ]
        },
        {
            "id": "MIG-92431",
            "email": "arthur.pendelton@yorkshireheritage.co.uk",
            "name": "Arthur Pendelton",
            "phone": "+44 1904 621144",
            "address": "9 The Shambles",
            "city": "York",
            "pincode": "YO1 7LZ",
            "payment": "PayPal",
            "status": "Delivered",
            "created_at": "2026-10-08 17:25:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-21843", 2, "Standard Size"),
                ("ret-21212", 4, "Standard Size")
            ]
        },
        {
            "id": "MIG-92876",
            "email": "victoria.sterling@kensingtongift.co.uk",
            "name": "Victoria Sterling",
            "phone": "+44 20 8960 7712",
            "address": "33 Holland Park Avenue",
            "city": "London",
            "pincode": "W11 3RW",
            "payment": "Credit Card",
            "status": "Delivered",
            "created_at": "2026-10-12 11:55:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 1, "Hostess Gift Set"),
                ("ret-85123a", 3, "Set of 2 (Twin Pack)"),
                ("ret-21232", 4, "Handcrafted Piece")
            ]
        },
        {
            "id": "MIG-93108",
            "email": "julian.thorne@cambridgebooks.co.uk",
            "name": "Julian Thorne",
            "phone": "+44 1223 337733",
            "address": "14 King's Parade",
            "city": "Cambridge",
            "pincode": "CB2 1SJ",
            "payment": "Apple Pay",
            "status": "Delivered",
            "created_at": "2026-10-15 13:18:00",
            "discount_pct": 0,
            "shipping": 4.99,
            "items": [
                ("ret-20725", 3, "Standard Edition"),
                ("ret-85099c", 2, "Standard Edition")
            ]
        },
        {
            "id": "MIG-93450",
            "email": "penelope.wright@chelseahome.com",
            "name": "Penelope Wright",
            "phone": "+44 20 7352 8111",
            "address": "52 King's Road, Chelsea",
            "city": "London",
            "pincode": "SW3 4UD",
            "payment": "Klarna",
            "status": "Delivered",
            "created_at": "2026-10-18 16:50:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-15056bl", 2, "Standard Edition"),
                ("ret-21621", 1, "Standard Size"),
                ("ret-47566", 2, "Standard Size")
            ]
        },
        {
            "id": "MIG-93822",
            "email": "sebastian.finch@manchesterdesign.co.uk",
            "name": "Sebastian Finch",
            "phone": "+44 161 234 5000",
            "address": "45 Deansgate",
            "city": "Manchester",
            "pincode": "M3 2AY",
            "payment": "Debit Card",
            "status": "Delivered",
            "created_at": "2026-10-21 09:40:00",
            "discount_pct": 20,
            "shipping": 0.00,
            "items": [
                ("ret-48138", 1, "Standard Size"),
                ("ret-20685", 1, "Standard Size"),
                ("ret-22386", 4, "Standard Edition")
            ]
        },
        {
            "id": "MIG-94115",
            "email": "evelyn.beauchamp@bristolceramics.org",
            "name": "Evelyn Beauchamp",
            "phone": "+44 117 922 2000",
            "address": "8 Clifton Down Road",
            "city": "Bristol",
            "pincode": "BS8 4AA",
            "payment": "Credit Card",
            "status": "Delivered",
            "created_at": "2026-10-23 15:10:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 2, "Standard Edition"),
                ("ret-84347", 3, "Single Accent")
            ]
        },
        {
            "id": "MIG-94520",
            "email": "rupert.langley@countryliving.co.uk",
            "name": "Rupert Langley",
            "phone": "+44 1386 840333",
            "address": "Meadow View Cottage, Church Street",
            "city": "Broadway",
            "pincode": "WR12 7AE",
            "payment": "PayPal",
            "status": "Shipped",
            "created_at": "2026-10-26 11:25:00",
            "discount_pct": 20,
            "shipping": 0.00,
            "items": [
                ("ret-21843", 2, "Standard Size"),
                ("ret-85123a", 3, "Set of 2 (Twin Pack)")
            ]
        },
        {
            "id": "MIG-94892",
            "email": "clara.davenport@richmondgarden.co.uk",
            "name": "Clara Davenport",
            "phone": "+44 20 8940 1234",
            "address": "29 Richmond Hill",
            "city": "Richmond",
            "pincode": "TW10 6RE",
            "payment": "Apple Pay",
            "status": "Shipped",
            "created_at": "2026-10-28 14:05:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-15056n", 1, "Standard Edition"),
                ("ret-21621", 2, "Standard Size")
            ]
        },
        {
            "id": "MIG-95201",
            "email": "customer@migriga.com",
            "name": "Aanya Sharma",
            "phone": "+44 7700 900077",
            "address": "Flat 4B, Kensington Court Gardens",
            "city": "London",
            "pincode": "W8 5HN",
            "payment": "Credit Card",
            "status": "Shipped",
            "created_at": "2026-10-29 16:30:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 1, "Hostess Gift Set"),
                ("ret-84879", 2, "Handcrafted Piece"),
                ("ret-85099b", 2, "Standard Edition")
            ]
        },
        {
            "id": "MIG-95633",
            "email": "alistair.graham@highlandantiques.co.uk",
            "name": "Alistair Graham",
            "phone": "+44 1463 234123",
            "address": "4 Castle Wynd",
            "city": "Inverness",
            "pincode": "IV2 3EB",
            "payment": "Debit Card",
            "status": "Shipped",
            "created_at": "2026-10-30 10:45:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-48138", 2, "Standard Size"),
                ("ret-22086", 3, "Standard Edition")
            ]
        },
        {
            "id": "MIG-96045",
            "email": "harriet.shaw@windsorantiques.com",
            "name": "Harriet Shaw",
            "phone": "+44 1753 860111",
            "address": "16 Thames Street",
            "city": "Windsor",
            "pincode": "SL4 1PL",
            "payment": "Credit Card",
            "status": "Processing",
            "created_at": "2026-10-31 12:15:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 1, "Standard Edition"),
                ("ret-21843", 1, "Standard Size"),
                ("ret-84347", 2, "Single Accent")
            ]
        },
        {
            "id": "MIG-96420",
            "email": "guest.sophie@outlook.co.uk",
            "name": "Sophie Turner",
            "phone": "+44 20 7946 0991",
            "address": "42 St John's Wood High St",
            "city": "London",
            "pincode": "NW8 7NL",
            "payment": "Apple Pay",
            "status": "Processing",
            "created_at": "2026-11-01 09:30:00",
            "discount_pct": 0,
            "shipping": 4.99,
            "items": [
                ("ret-85123a", 2, "Single Accent"),
                ("ret-21232", 3, "Handcrafted Piece")
            ]
        },
        {
            "id": "MIG-96850",
            "email": "eleanor.vance@heritagemail.co.uk",
            "name": "Eleanor Vance",
            "phone": "+44 20 7946 0831",
            "address": "18 Cheyne Walk, Chelsea",
            "city": "London",
            "pincode": "SW3 5HN",
            "payment": "Credit Card",
            "status": "Processing",
            "created_at": "2026-11-01 15:40:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-20914", 3, "Standard Size"),
                ("ret-47566", 2, "Standard Size")
            ]
        },
        {
            "id": "MIG-97124",
            "email": "henry.cavendish@mayfairarts.com",
            "name": "Henry Cavendish",
            "phone": "+44 20 7183 4521",
            "address": "7 Berkeley Square, Mayfair",
            "city": "London",
            "pincode": "W1J 6ER",
            "payment": "Apple Pay",
            "status": "Confirmed",
            "created_at": "2026-11-02 08:20:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 2, "Hostess Gift Set"),
                ("ret-85123a", 4, "Set of 2 (Twin Pack)")
            ]
        },
        {
            "id": "MIG-97550",
            "email": "beatrice.holloway@oxfordalumni.org",
            "name": "Beatrice Holloway",
            "phone": "+44 1865 270000",
            "address": "24 St Giles'",
            "city": "Oxford",
            "pincode": "OX1 3LW",
            "payment": "PayPal",
            "status": "Confirmed",
            "created_at": "2026-11-02 11:10:00",
            "discount_pct": 15,
            "shipping": 0.00,
            "items": [
                ("ret-21621", 2, "Standard Size"),
                ("ret-15056bl", 1, "Standard Edition")
            ]
        },
        {
            "id": "MIG-97910",
            "email": "guest.william@btinternet.com",
            "name": "William Blackwood",
            "phone": "+44 131 225 8000",
            "address": "28 George Street",
            "city": "Edinburgh",
            "pincode": "EH2 2LR",
            "payment": "Credit Card",
            "status": "Confirmed",
            "created_at": "2026-11-02 14:00:00",
            "discount_pct": 0,
            "shipping": 4.99,
            "items": [
                ("ret-20685", 1, "Standard Size"),
                ("ret-85099b", 2, "Standard Edition")
            ]
        },
        {
            "id": "MIG-98305",
            "email": "o.kensington@cotswoldliving.co.uk",
            "name": "Oliver Kensington",
            "phone": "+44 1608 650219",
            "address": "High Street, Chipping Campden",
            "city": "Cotswolds",
            "pincode": "GL55 6AT",
            "payment": "Debit Card",
            "status": "Cancelled",
            "created_at": "2026-10-14 11:00:00",
            "discount_pct": 0,
            "shipping": 0.00,
            "items": [
                ("ret-22423", 1, "Standard Edition"),
                ("ret-48138", 1, "Standard Size")
            ]
        }
    ]

    total_revenue = 0.0
    for ord_spec in orders_spec:
        user_id = customer_user_ids.get(ord_spec["email"])

        # Calculate items subtotal
        subtotal = 0.0
        resolved_items = []
        for pid, qty, size in ord_spec["items"]:
            prod = catalog_map.get(pid)
            if not prod:
                # Fallback to first available
                prod = catalog_list[0]
            price = float(prod["price"])
            line_tot = price * qty
            subtotal += line_tot
            resolved_items.append({
                "product_id": prod["id"],
                "product_name": prod["name"],
                "qty": qty,
                "price": price,
                "size": size,
                "image": prod.get("image", "assets/images/prod-cakestand.jpg")
            })

        subtotal = round(subtotal, 2)
        discount = round(subtotal * (ord_spec["discount_pct"] / 100.0), 2)
        shipping = ord_spec["shipping"]
        total = round(subtotal - discount + shipping, 2)
        total_revenue += total

        # Insert Order
        cursor.execute("""
            INSERT INTO orders (
                id, user_id, customer_name, customer_email, customer_phone,
                address, city, pincode, payment_method, status,
                subtotal, discount, shipping, total, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ord_spec["id"],
            user_id,
            ord_spec["name"],
            ord_spec["email"],
            ord_spec["phone"],
            ord_spec["address"],
            ord_spec["city"],
            ord_spec["pincode"],
            ord_spec["payment"],
            ord_spec["status"],
            subtotal,
            discount,
            shipping,
            total,
            ord_spec["created_at"]
        ))

        # Insert Order Items
        for it in resolved_items:
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, product_id, product_name, qty, price, shade, size, image
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
            """, (
                ord_spec["id"],
                it["product_id"],
                it["product_name"],
                it["qty"],
                it["price"],
                it["size"],
                it["image"]
            ))

    conn.commit()

    # Query summary
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'customer'")
    cust_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM newsletter_subscribers")
    sub_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    ord_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM order_items")
    item_count = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(total) FROM orders")
    rev = cursor.fetchone()[0]

    conn.close()
    print("=== SYNTHETIC DATA SEEDING COMPLETE ===")
    print(f"Registered Customers : {cust_count}")
    print(f"Newsletter Subs      : {sub_count}")
    print(f"Store Orders         : {ord_count}")
    print(f"Order Items Breakdown: {item_count}")
    print(f"Total Store Revenue  : £{rev:,.2f}")

if __name__ == "__main__":
    run_seeding()
