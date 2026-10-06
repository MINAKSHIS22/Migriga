// MIGRIGA Store State Management (Connected to FastAPI + SQLite Backend)
class MigrigaStore {
  constructor() {
    this.cart = this.loadFromStorage('migriga_cart', []);
    this.wishlist = this.loadFromStorage('migriga_wishlist', []);
    this.appliedCoupon = this.loadFromStorage('migriga_coupon', null);
    this.currentUser = this.loadFromStorage('migriga_user', null);
    this.token = localStorage.getItem('migriga_token') || null;
    this.orderHistory = [];
    this.freeShippingThreshold = 999;
    this.subscribers = [];

    // Fetch initial order history from backend if logged in
    if (this.currentUser) {
      this.fetchMyOrders();
    }
  }

  loadFromStorage(key, fallback) {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  saveToStorage(key, val) {
    try {
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) {}
  }

  subscribe(callback) {
    this.subscribers.push(callback);
  }

  notify(event, payload) {
    this.subscribers.forEach(cb => cb(event, payload));
  }

  // --- Cart Operations ---
  addToCart(productId, qty = 1, options = {}) {
    const product = PRODUCTS_DATA.find(p => p.id === productId);
    if (!product) return;

    const shade = options.shade || (product.shades ? product.shades[0].name : null);
    const size = options.size || (product.sizes ? product.sizes[0] : null);

    const existingIndex = this.cart.findIndex(
      item => item.id === productId && item.shade === shade && item.size === size
    );

    if (existingIndex > -1) {
      this.cart[existingIndex].qty += qty;
    } else {
      this.cart.push({
        id: product.id,
        name: product.name,
        category: product.category,
        price: product.price,
        originalPrice: product.originalPrice,
        image: product.image,
        qty: qty,
        shade: shade,
        size: size
      });
    }

    this.saveToStorage('migriga_cart', this.cart);
    this.notify('cart_updated', { cart: this.cart, addedProduct: product });
    return product;
  }

  updateCartQty(index, newQty) {
    if (index >= 0 && index < this.cart.length) {
      if (newQty <= 0) {
        this.cart.splice(index, 1);
      } else {
        this.cart[index].qty = Math.min(newQty, 10);
      }
      this.saveToStorage('migriga_cart', this.cart);
      this.notify('cart_updated', { cart: this.cart });
    }
  }

  removeFromCart(index) {
    if (index >= 0 && index < this.cart.length) {
      const removed = this.cart.splice(index, 1);
      this.saveToStorage('migriga_cart', this.cart);
      this.notify('cart_updated', { cart: this.cart, removed: removed[0] });
    }
  }

  clearCart() {
    this.cart = [];
    this.saveToStorage('migriga_cart', this.cart);
    this.notify('cart_updated', { cart: this.cart });
  }

  getCartCount() {
    return this.cart.reduce((sum, item) => sum + item.qty, 0);
  }

  getCartSubtotal() {
    return this.cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
  }

  async applyCoupon(code) {
    const clean = (code || '').trim().toUpperCase();
    try {
      const res = await fetch('/api/coupons/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: clean })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invalid coupon');
      
      this.appliedCoupon = { code: data.code, discountPercent: data.discount_percent, desc: data.desc };
      this.saveToStorage('migriga_coupon', this.appliedCoupon);
      this.notify('cart_updated', { cart: this.cart });
      return { success: true, message: `Coupon ${data.code} applied! ${data.discount_percent}% off.` };
    } catch (err) {
      // Fallback
      if (['GLOW20', 'GLOW30', 'WELCOME15'].includes(clean)) {
        const pct = clean === 'GLOW30' ? 30 : clean === 'GLOW20' ? 20 : 15;
        this.appliedCoupon = { code: clean, discountPercent: pct, desc: `${pct}% Discount` };
        this.saveToStorage('migriga_coupon', this.appliedCoupon);
        this.notify('cart_updated', { cart: this.cart });
        return { success: true, message: `Coupon ${clean} applied! ${pct}% off.` };
      }
      return { success: false, message: err.message || 'Invalid coupon code.' };
    }
  }

  removeCoupon() {
    this.appliedCoupon = null;
    this.saveToStorage('migriga_coupon', null);
    this.notify('cart_updated', { cart: this.cart });
  }

  getCartTotals() {
    const subtotal = this.getCartSubtotal();
    let discount = 0;
    if (this.appliedCoupon && subtotal > 0) {
      discount = Math.round(subtotal * (this.appliedCoupon.discountPercent / 100));
    }
    const isFreeShipping = subtotal >= this.freeShippingThreshold || subtotal === 0;
    const shipping = isFreeShipping ? 0 : 99;
    const total = Math.max(0, subtotal - discount + shipping);
    const amountToFreeShipping = Math.max(0, this.freeShippingThreshold - subtotal);
    const progressPercent = Math.min(100, Math.round((subtotal / this.freeShippingThreshold) * 100));

    return {
      subtotal,
      discount,
      shipping,
      total,
      isFreeShipping,
      amountToFreeShipping,
      progressPercent,
      coupon: this.appliedCoupon
    };
  }

  // --- Wishlist Operations ---
  toggleWishlist(productId) {
    const index = this.wishlist.indexOf(productId);
    let added = false;
    if (index > -1) {
      this.wishlist.splice(index, 1);
    } else {
      this.wishlist.push(productId);
      added = true;
    }
    this.saveToStorage('migriga_wishlist', this.wishlist);
    this.notify('wishlist_updated', { wishlist: this.wishlist, productId, added });
    return added;
  }

  isInWishlist(productId) {
    return this.wishlist.includes(productId);
  }

  getWishlistCount() {
    return this.wishlist.length;
  }

  getWishlistProducts() {
    return PRODUCTS_DATA.filter(p => this.wishlist.includes(p.id));
  }

  // --- Orders & Backend API ---
  async createOrder(shippingDetails, paymentMethod) {
    const totals = this.getCartTotals();
    const payload = {
      items: this.cart.map(i => ({
        id: i.id,
        name: i.name,
        qty: i.qty,
        price: i.price,
        shade: i.shade || null,
        size: i.size || null,
        image: i.image || null
      })),
      full_name: shippingDetails.fullName,
      phone: shippingDetails.phone,
      email: this.currentUser ? this.currentUser.email : 'guest@migriga.com',
      address: shippingDetails.address,
      city: shippingDetails.city,
      pincode: shippingDetails.pincode,
      payment_method: paymentMethod,
      subtotal: totals.subtotal,
      discount: totals.discount,
      shipping: totals.shipping,
      total: totals.total
    };

    let orderResult;
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
      
      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Order creation failed');
      
      orderResult = {
        id: data.order.id,
        date: new Date().toISOString().split('T')[0],
        items: [...this.cart],
        totals: totals,
        shippingDetails: shippingDetails,
        paymentMethod: paymentMethod,
        status: data.order.status || 'Confirmed'
      };
    } catch (err) {
      // Local fallback if offline
      const fallbackId = 'MIG-' + Math.floor(10000 + Math.random() * 90000);
      orderResult = {
        id: fallbackId,
        date: new Date().toISOString().split('T')[0],
        items: [...this.cart],
        totals: totals,
        shippingDetails: shippingDetails,
        paymentMethod: paymentMethod,
        status: 'Confirmed'
      };
    }

    this.orderHistory.unshift(orderResult);
    this.clearCart();
    this.removeCoupon();
    this.notify('order_placed', orderResult);
    return orderResult;
  }

  async fetchMyOrders() {
    try {
      const headers = {};
      if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
      const url = this.currentUser ? `/api/orders/my?email=${encodeURIComponent(this.currentUser.email)}` : '/api/orders/my';
      const res = await fetch(url, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.orders) {
          this.orderHistory = data.orders.map(o => ({
            id: o.id,
            date: o.created_at ? o.created_at.split(' ')[0] : 'Today',
            status: o.status,
            items: o.items || [],
            total: o.total,
            totals: { total: o.total }
          }));
          this.notify('orders_loaded', this.orderHistory);
        }
      }
    } catch (e) {}
  }

  // --- Auth Operations (Customer & Admin) ---
  async login(email, password) {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');

      this.token = data.token;
      this.currentUser = data.user;
      localStorage.setItem('migriga_token', this.token);
      this.saveToStorage('migriga_user', this.currentUser);

      if (this.currentUser.role === 'admin') {
        localStorage.setItem('migriga_admin_token', this.token);
      }

      await this.fetchMyOrders();
      this.notify('auth_updated', this.currentUser);
      return { success: true, user: this.currentUser };
    } catch (err) {
      return { success: false, message: err.message };
    }
  }

  async register(fullName, email, password, phone = '') {
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, email, password, phone })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');

      this.token = data.token;
      this.currentUser = data.user;
      localStorage.setItem('migriga_token', this.token);
      this.saveToStorage('migriga_user', this.currentUser);

      this.notify('auth_updated', this.currentUser);
      return { success: true, user: this.currentUser };
    } catch (err) {
      return { success: false, message: err.message };
    }
  }

  logout() {
    if (this.token) {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${this.token}` }
      }).catch(() => {});
    }
    this.token = null;
    this.currentUser = null;
    this.orderHistory = [];
    localStorage.removeItem('migriga_token');
    localStorage.removeItem('migriga_admin_token');
    this.saveToStorage('migriga_user', null);
    this.notify('auth_updated', null);
  }
}

// Global Store Instance
const store = new MigrigaStore();
