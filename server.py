# MIGRIGA British Heritage Living - FastAPI Full-Stack Backend
from fastapi import FastAPI, HTTPException, Header, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import os
import json
import sqlite3
import random
import math

from backend.database import get_db, init_db
from backend.auth import hash_password, verify_password, generate_token
from backend.recommendation_engine import engine
from backend.deps import get_current_user, require_admin
from backend import analytics_api

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="MIGRIGA British Heritage Living API", version="2.0.0")

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".html", ".js", ".json")) or path in ("/", "/welcome", "/store", "/admin", "/login", "/analytics"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Initialize database schema on startup
@app.on_event("startup")
def on_startup():
    init_db()
    analytics_api.warm_cache()

# Migriga Analytics API (/api/analytics/*): warehouse, ETL, OLAP, Apriori, RFM/K-Means
app.include_router(analytics_api.router)
analytics_api.register_error_handlers(app)

# --- Authentication dependencies live in backend/deps.py (shared with the analytics API) ---

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None

class OrderItemSchema(BaseModel):
    id: str
    name: str
    qty: int
    price: float
    shade: Optional[str] = None
    size: Optional[str] = None
    image: Optional[str] = None

class CreateOrderRequest(BaseModel):
    items: List[OrderItemSchema]
    full_name: str
    phone: str
    email: Optional[str] = None
    address: str
    city: str
    pincode: str
    payment_method: str
    subtotal: float
    discount: float = 0
    shipping: float = 0
    total: float

class StatusUpdateRequest(BaseModel):
    status: str

class StockUpdateRequest(BaseModel):
    stock: int
    price: Optional[float] = None

class CouponApplyRequest(BaseModel):
    code: str

class NewsletterRequest(BaseModel):
    email: str

# ==============================================================================
# AUTHENTICATION ENDPOINTS (Customer & Admin)
# ==============================================================================
@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password_hash, full_name, phone, role FROM users WHERE LOWER(email) = ?", (email,))
    user_row = cursor.fetchone()
    
    if not user_row or not verify_password(req.password, user_row["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = generate_token()
    cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_row["id"]))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user_row["id"],
            "email": user_row["email"],
            "full_name": user_row["full_name"],
            "phone": user_row["phone"],
            "role": user_row["role"]
        }
    }

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    pwd_hash, _ = hash_password(req.password)
    cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role)
        VALUES (?, ?, ?, ?, 'customer')
    """, (email, pwd_hash, req.full_name.strip(), req.phone))
    user_id = cursor.lastrowid

    token = generate_token()
    cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "full_name": req.full_name.strip(),
            "phone": req.phone,
            "role": "customer"
        }
    }

@app.get("/api/auth/me")
def get_me(user: Optional[dict] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": user}

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"success": True}

# ==============================================================================
# STOREFRONT ENDPOINTS (Products, Coupons, Newsletter, Orders)
# ==============================================================================
@app.get("/api/products")
def get_products(category: Optional[str] = None, search: Optional[str] = None, sort: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if category and category != 'all':
        query += " AND category = ?"
        params.append(category)

    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(ingredients) LIKE ?)"
        params.extend([s, s, s])

    if sort == 'price-low':
        query += " ORDER BY price ASC"
    elif sort == 'price-high':
        query += " ORDER BY price DESC"
    elif sort == 'rating':
        query += " ORDER BY rating DESC"
    else:
        query += " ORDER BY is_bestseller DESC, id ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    products = []
    for r in rows:
        p = dict(r)
        p["shades"] = json.loads(p["shades_json"]) if p.get("shades_json") else None
        p["sizes"] = json.loads(p["sizes_json"]) if p.get("sizes_json") else None
        p["benefits"] = json.loads(p["benefits_json"]) if p.get("benefits_json") else []
        p["isBestseller"] = bool(p["is_bestseller"])
        p["isNew"] = bool(p["is_new"])
        products.append(p)

    return {"products": products}

@app.get("/api/products/{product_id}")
def get_product_detail(product_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found.")
    
    p = dict(row)
    p["shades"] = json.loads(p["shades_json"]) if p.get("shades_json") else None
    p["sizes"] = json.loads(p["sizes_json"]) if p.get("sizes_json") else None
    p["benefits"] = json.loads(p["benefits_json"]) if p.get("benefits_json") else []
    return {"product": p}
 
# --- Recommendation Engine Endpoints ---
@app.get("/api/recommendations/product/{product_id}")
def get_product_recommendations(product_id: str, limit: int = 4):
    """Returns top hybrid recommendations (Frequently Bought Together + Content Match) for a product."""
    recs = engine.get_recommendations_for_product(product_id, limit=limit)
    return {
        "success": True,
        "product_id": product_id,
        "recommendations": recs,
        "model_status": engine.metadata.get("status", "ready")
    }

@app.get("/api/recommendations/cart")
def get_cart_recommendations(items: Optional[str] = Query(None), limit: int = 4):
    """Smart cross-sell recommendations tailored to current cart items (comma-separated IDs)."""
    cart_ids = [i.strip() for i in items.split(",") if i.strip()] if items else []
    recs = engine.get_cart_recommendations(cart_ids, limit=limit)
    return {
        "success": True,
        "recommendations": recs,
        "model_status": engine.metadata.get("status", "ready")
    }

@app.get("/api/recommendations/trending")
def get_trending_recommendations(limit: int = 8):
    """Returns trending and popular community favorites based on model rankings."""
    trending = engine.get_trending_products(limit=limit)
    return {
        "success": True,
        "trending": trending,
        "model_status": engine.metadata.get("status", "ready")
    }

@app.get("/api/recommendations/status")
def get_recommendation_status():
    """Returns current model status, metadata, dataset coverage, and metrics."""
    return {
        "success": True,
        "metadata": engine.metadata
    }

@app.post("/api/recommendations/train")
def trigger_model_training(admin: Optional[dict] = Depends(require_admin)):
    """Triggers ML recommendation model retraining on available datasets."""
    try:
        from backend.train_recommendation import main as run_trainer
        run_trainer()
        engine.load_cache()
        return {
            "success": True,
            "message": "Model trained and cache reloaded successfully.",
            "metadata": engine.metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")

@app.post("/api/coupons/apply")
def apply_coupon(req: CouponApplyRequest):
    code = req.code.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons WHERE code = ? AND is_active = 1", (code,))
    coupon = cursor.fetchone()
    conn.close()

    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid coupon code. Try RETAIL20, HERITAGE30 or WELCOME15.")

    return {
        "success": True,
        "code": coupon["code"],
        "discount_percent": coupon["discount_percent"],
        "desc": coupon["desc"]
    }

@app.post("/api/newsletter")
def subscribe_newsletter(req: NewsletterRequest):
    email = req.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM newsletter_subscribers WHERE email = ?", (email,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO newsletter_subscribers (email, voucher_code) VALUES (?, 'WELCOME15')", (email,))
        conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Welcome to MIGRIGA! Use code WELCOME15 for 15% off your first order.",
        "voucher": "WELCOME15"
    }

@app.post("/api/orders")
def create_order(req: CreateOrderRequest, user: Optional[dict] = Depends(get_current_user)):
    if not req.items:
        raise HTTPException(status_code=400, detail="Your bag is empty.")

    order_id = f"MIG-{random.randint(10000, 99999)}"
    user_id = user["id"] if user else None
    customer_email = req.email or (user["email"] if user else "guest@migriga.com")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO orders (
            id, user_id, customer_name, customer_email, customer_phone,
            address, city, pincode, payment_method, status,
            subtotal, discount, shipping, total
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', ?, ?, ?, ?)
    """, (
        order_id, user_id, req.full_name, customer_email, req.phone,
        req.address, req.city, req.pincode, req.payment_method,
        req.subtotal, req.discount, req.shipping, req.total
    ))

    for item in req.items:
        cursor.execute("""
            INSERT INTO order_items (
                order_id, product_id, product_name, qty, price, shade, size, image
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, item.id, item.name, item.qty, item.price,
            item.shade, item.size, item.image
        ))

        # Decrement stock
        cursor.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?", (item.qty, item.id))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "order": {
            "id": order_id,
            "status": "Confirmed",
            "total": req.total,
            "payment_method": req.payment_method,
            "customer_name": req.full_name,
            "customer_phone": req.phone,
            "address": f"{req.address}, {req.city} - {req.pincode}"
        }
    }

@app.get("/api/orders/my")
def get_my_orders(user: Optional[dict] = Depends(get_current_user), email: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    if user:
        cursor.execute("""
            SELECT * FROM orders WHERE user_id = ? OR LOWER(customer_email) = LOWER(?)
            ORDER BY created_at DESC
        """, (user["id"], user["email"]))
    elif email:
        cursor.execute("""
            SELECT * FROM orders WHERE LOWER(customer_email) = LOWER(?)
            ORDER BY created_at DESC
        """, (email.strip(),))
    else:
        conn.close()
        return {"orders": []}

    order_rows = cursor.fetchall()
    orders = []
    for o_row in order_rows:
        o = dict(o_row)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
        o["items"] = [dict(it) for it in cursor.fetchall()]
        orders.append(o)

    conn.close()
    return {"orders": orders}

# ==============================================================================
# ADMIN PORTAL ENDPOINTS (Admin Only)
# ==============================================================================
@app.get("/api/admin/stats")
def get_admin_stats(admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(SUM(total), 0) as revenue, COUNT(*) as count FROM orders")
    order_stats = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
    customer_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM products WHERE stock <= 30")
    low_stock_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM products")
    total_products = cursor.fetchone()["count"]

    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 5")
    recent_orders = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) as count FROM product_recommendations")
    recs_count = cursor.fetchone()["count"]

    retail_count = 0
    pjson_path = os.path.join(BASE_DIR, "products.json")
    if os.path.exists(pjson_path):
        try:
            with open(pjson_path, "r", encoding="utf-8") as f:
                retail_count = len(json.load(f))
        except Exception:
            retail_count = 4082
    else:
        retail_count = 4082

    conn.close()

    return {
        "revenue": round(order_stats["revenue"], 2),
        "total_orders": order_stats["count"],
        "total_customers": customer_count,
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "recent_orders": recent_orders,
        "retail_dataset_count": retail_count,
        "beauty_dataset_count": retail_count,
        "recommendations_count": recs_count,
        "dataset_source": "UK Online Retail Dataset (online_retail_09_10.csv / migriga_warehouse.db)",
        "model_metadata": engine.metadata
    }

@app.get("/api/admin/retail-dataset")
@app.get("/api/admin/beauty-dataset")
def get_admin_retail_dataset(admin: dict = Depends(require_admin), page: int = 1, page_size: int = 25, search: Optional[str] = None, category: Optional[str] = None):
    pjson_path = os.path.join(BASE_DIR, "products.json")
    if not os.path.exists(pjson_path):
        return {"products": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
    try:
        with open(pjson_path, "r", encoding="utf-8") as f:
            products = json.load(f)
    except Exception as e:
        return {"products": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0, "error": str(e)}

    if category and category.lower() != "all":
        cat_lower = category.lower()
        products = [p for p in products if p.get("category", "").lower() == cat_lower or p.get("category_name", "").lower() == cat_lower]

    if search:
        s = search.lower().strip()
        products = [
            p for p in products
            if s in p.get("name", "").lower()
            or s in str(p.get("stock_code", "")).lower()
            or s in str(p.get("id", "")).lower()
            or s in p.get("category_name", "").lower()
            or s in p.get("raw_description", "").lower()
        ]

    total = len(products)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = products[start:end]

    return {
        "products": sliced,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 1
    }


@app.get("/api/admin/orders")
def get_admin_orders(admin: dict = Depends(require_admin), status: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM orders"
    params = []
    if status and status != 'all':
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    orders = []
    for r in rows:
        o = dict(r)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],))
        o["items"] = [dict(it) for it in cursor.fetchall()]
        orders.append(o)

    conn.close()
    return {"orders": orders}

@app.patch("/api/admin/orders/{order_id}/status")
def update_order_status(order_id: str, req: StatusUpdateRequest, admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (req.status, order_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found.")
    conn.commit()
    conn.close()
    return {"success": True, "order_id": order_id, "new_status": req.status}

@app.get("/api/admin/products")
def get_admin_products(admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, category_name, price, stock, rating, is_bestseller FROM products ORDER BY category, id")
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"products": products}

@app.patch("/api/admin/products/{product_id}/stock")
def update_product_stock(product_id: str, req: StockUpdateRequest, admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    if req.price is not None:
        cursor.execute("UPDATE products SET stock = ?, price = ? WHERE id = ?", (req.stock, req.price, product_id))
    else:
        cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (req.stock, product_id))
    conn.commit()
    conn.close()
    return {"success": True, "product_id": product_id, "new_stock": req.stock}

@app.get("/api/admin/customers")
def get_admin_customers(admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, full_name, phone, role, created_at FROM users WHERE role = 'customer' ORDER BY created_at DESC")
    customers = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT id, email, voucher_code, created_at FROM newsletter_subscribers ORDER BY created_at DESC")
    subscribers = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {"customers": customers, "subscribers": subscribers}

# ==============================================================================
# STATIC & HTML ROUTES (Get Started -> Login -> Storefront / Admin)
# ==============================================================================
HTML_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/")
@app.get("/welcome")
@app.get("/welcome.html")
def serve_welcome():
    """Serves the primary Get Started page."""
    return FileResponse(os.path.join(BASE_DIR, "welcome.html"), headers=HTML_NO_CACHE_HEADERS)

@app.get("/login")
@app.get("/login.html")
def serve_login():
    """Serves the single unified Login page."""
    return FileResponse(os.path.join(BASE_DIR, "login.html"), headers=HTML_NO_CACHE_HEADERS)

@app.get("/store")
@app.get("/index.html")
def serve_storefront():
    """Serves the MIGRIGA Customer Storefront."""
    return FileResponse(os.path.join(BASE_DIR, "index.html"), headers=HTML_NO_CACHE_HEADERS)

@app.get("/admin")
@app.get("/admin.html")
def serve_admin():
    """Serves the MIGRIGA Store Admin Portal."""
    return FileResponse(os.path.join(BASE_DIR, "admin.html"), headers=HTML_NO_CACHE_HEADERS)

@app.get("/analytics")
@app.get("/analytics.html")
def serve_analytics():
    """Serves Migriga Analytics (data warehouse, OLAP, data mining & DWM Lab)."""
    return FileResponse(os.path.join(BASE_DIR, "analytics.html"), headers=HTML_NO_CACHE_HEADERS)

# Mount static asset folders
app.mount("/css", StaticFiles(directory=os.path.join(BASE_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(BASE_DIR, "js")), name="js")
app.mount("/assets", StaticFiles(directory=os.path.join(BASE_DIR, "assets")), name="assets")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=3000, reload=False)
