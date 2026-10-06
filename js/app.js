// MIGRIGA Main Application Orchestrator (Connected to Backend & Admin)

// Global Modal & Drawer Control
function openDrawer(drawerId) {
  closeAllDrawers();
  const drawer = document.getElementById(drawerId);
  const backdrop = document.getElementById('global-backdrop');
  if (drawer) drawer.classList.add('open');
  if (backdrop) backdrop.classList.add('visible');
  document.body.style.overflow = 'hidden';
}

function closeAllDrawers() {
  document.querySelectorAll('.luxury-drawer').forEach(d => d.classList.remove('open'));
  const backdrop = document.getElementById('global-backdrop');
  if (backdrop) backdrop.classList.remove('visible');
  document.body.style.overflow = '';
}

function openModal(modalId) {
  closeAllModals();
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeAllModals() {
  document.querySelectorAll('.luxury-modal').forEach(m => m.classList.remove('open'));
  document.body.style.overflow = '';
}

function scrollToSection(sectionId) {
  const target = document.getElementById(sectionId);
  if (target) {
    const navHeight = document.querySelector('.main-header')?.offsetHeight || 80;
    const y = target.getBoundingClientRect().top + window.pageYOffset - navHeight - 10;
    window.scrollTo({ top: y, behavior: 'smooth' });
  }
}

// App Initialization
document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Bestsellers Grid (5 key products as requested)
  initBestsellersGrid();

  // 2. Initialize Full Shop Catalog with filters and sorting
  initShopCatalog();

  // 3. Initialize Instagram Grid
  initInstagramGrid();

  // 4. Initialize Testimonials Slider
  new TestimonialSlider();

  // 5. Initialize Countdown Timer
  startCountdownTimer();

  // 6. Setup Store Subscriptions & Event Delegation
  initStoreSubscribers();
  initGlobalDelegation();

  // 7. Setup Form Handlers (Newsletter, Checkout, Auth, Search)
  initForms();

  // 8. Sticky Header Scroll Effect
  initHeaderScroll();

  // 9. Initial draw & update UI if already logged in
  renderCartDrawer();
  renderWishlistDrawer();
  if (store.currentUser) {
    updateUserAccountUI(store.currentUser);
  }
});

// 1. Bestsellers Grid
function initBestsellersGrid() {
  const container = document.getElementById('bestsellers-grid');
  if (!container) return;

  const bestsellers = [
    PRODUCTS_DATA.find(p => p.id === 'mig-001'),
    PRODUCTS_DATA.find(p => p.id === 'mig-002'),
    PRODUCTS_DATA.find(p => p.id === 'mig-003'),
    PRODUCTS_DATA.find(p => p.id === 'mig-004'),
    PRODUCTS_DATA.find(p => p.id === 'mig-005'),
  ].filter(Boolean);

  container.innerHTML = bestsellers.map(p => renderProductCard(p)).join('');

  // Category filter tabs for bestsellers
  const tabs = document.querySelectorAll('.bestseller-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const cat = tab.dataset.category;

      let filtered;
      if (cat === 'all') {
        filtered = bestsellers;
      } else {
        filtered = PRODUCTS_DATA.filter(p => p.category === cat && p.isBestseller);
        if (filtered.length === 0) {
          filtered = PRODUCTS_DATA.filter(p => p.category === cat).slice(0, 5);
        }
      }
      container.innerHTML = filtered.map(p => renderProductCard(p)).join('');
    });
  });
}

// 2. Full Shop Catalog
let currentCatalogCategory = 'all';
let currentCatalogSort = 'featured';
let currentPriceRange = 'all';

function initShopCatalog() {
  renderCatalogProducts();

  const filterBtns = document.querySelectorAll('.catalog-filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCatalogCategory = btn.dataset.filter;
      renderCatalogProducts();
    });
  });

  const priceSelect = document.getElementById('catalog-price-filter');
  if (priceSelect) {
    priceSelect.addEventListener('change', (e) => {
      currentPriceRange = e.target.value;
      renderCatalogProducts();
    });
  }

  const sortSelect = document.getElementById('catalog-sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      currentCatalogSort = e.target.value;
      renderCatalogProducts();
    });
  }
}

function renderCatalogProducts() {
  const container = document.getElementById('full-shop-grid');
  const countEl = document.getElementById('shop-results-count');
  if (!container) return;

  let list = [...PRODUCTS_DATA];

  if (currentCatalogCategory !== 'all') {
    list = list.filter(p => p.category === currentCatalogCategory);
  }

  if (currentPriceRange === 'under-800') {
    list = list.filter(p => p.price < 800);
  } else if (currentPriceRange === '800-1200') {
    list = list.filter(p => p.price >= 800 && p.price <= 1200);
  } else if (currentPriceRange === 'over-1200') {
    list = list.filter(p => p.price > 1200);
  }

  if (currentCatalogSort === 'price-low') {
    list.sort((a, b) => a.price - b.price);
  } else if (currentCatalogSort === 'price-high') {
    list.sort((a, b) => b.price - a.price);
  } else if (currentCatalogSort === 'rating') {
    list.sort((a, b) => b.rating - a.rating);
  } else {
    list.sort((a, b) => (b.isBestseller ? 1 : 0) - (a.isBestseller ? 1 : 0));
  }

  if (countEl) {
    countEl.textContent = `Showing all ${list.length} luxury products`;
  }

  container.innerHTML = list.map(p => renderProductCard(p)).join('');
}

// 3. Instagram Grid
function initInstagramGrid() {
  const container = document.getElementById('instagram-gallery-grid');
  if (!container) return;

  container.innerHTML = INSTAGRAM_DATA.map(item => `
    <div class="insta-tile">
      <img src="${item.image}" alt="MIGRIGA Instagram Post" loading="lazy" />
      <div class="insta-overlay">
        <div class="insta-stats">
          <span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
            </svg>
            ${item.likes}
          </span>
          <span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
            ${item.comments}
          </span>
        </div>
        <span class="insta-tag">${item.tag}</span>
      </div>
    </div>
  `).join('');
}

// 4. Store Subscriptions
function initStoreSubscribers() {
  store.subscribe((event, payload) => {
    if (event === 'cart_updated') {
      renderCartDrawer();
      renderWishlistDrawer();
    } else if (event === 'wishlist_updated') {
      renderWishlistDrawer();
      document.querySelectorAll(`[data-wishlist-id="${payload.productId}"]`).forEach(btn => {
        btn.classList.toggle('active', payload.added);
        const svg = btn.querySelector('svg');
        if (svg) svg.setAttribute('fill', payload.added ? '#B07D62' : 'none');
      });
    } else if (event === 'auth_updated') {
      updateUserAccountUI(payload);
    } else if (event === 'orders_loaded') {
      if (store.currentUser) updateUserAccountUI(store.currentUser);
    }
  });
}

// 5. Global Event Delegation
function initGlobalDelegation() {
  const backdrop = document.getElementById('global-backdrop');
  if (backdrop) {
    backdrop.addEventListener('click', () => {
      closeAllDrawers();
      closeAllModals();
    });
  }

  document.querySelectorAll('.drawer-close-btn').forEach(btn => {
    btn.addEventListener('click', closeAllDrawers);
  });

  document.querySelectorAll('.modal-close-btn').forEach(btn => {
    btn.addEventListener('click', closeAllModals);
  });

  document.querySelectorAll('.nav-cart-trigger').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      openDrawer('cart-drawer');
    });
  });

  document.querySelectorAll('.nav-wishlist-trigger').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      openDrawer('wishlist-drawer');
    });
  });

  document.querySelectorAll('.nav-search-trigger').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      openModal('search-modal');
      setTimeout(() => document.getElementById('main-search-input')?.focus(), 150);
    });
  });

  document.querySelectorAll('.nav-account-trigger').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      openModal('account-modal');
      if (store.currentUser) {
        updateUserAccountUI(store.currentUser);
      }
    });
  });

  const mobileToggle = document.getElementById('mobile-menu-toggle');
  if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
      openDrawer('mobile-menu-drawer');
    });
  }

  // Smooth scroll links & category click links
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href').substring(1);
      if (['quickview', 'cart', 'search', 'account', 'wishlist'].includes(targetId)) return;
      if (targetId) {
        e.preventDefault();
        closeAllDrawers();
        closeAllModals();

        const catTrigger = link.dataset.catTrigger;
        if (catTrigger) {
          currentCatalogCategory = catTrigger;
          document.querySelectorAll('.catalog-filter-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.filter === catTrigger);
          });
          renderCatalogProducts();
          scrollToSection('shop');
          return;
        }

        scrollToSection(targetId);
      }
    });
  });

  document.querySelectorAll('.category-card').forEach(card => {
    card.addEventListener('click', () => {
      const category = card.dataset.category;
      if (category) {
        currentCatalogCategory = category;
        document.querySelectorAll('.catalog-filter-btn').forEach(b => {
          b.classList.toggle('active', b.dataset.filter === category);
        });
        renderCatalogProducts();
        scrollToSection('shop');
      }
    });
  });

  // Delegated Clicks
  document.addEventListener('click', (e) => {
    // 1. Add to Bag button
    const addToBagBtn = e.target.closest('[data-add-to-bag-id]');
    if (addToBagBtn) {
      e.preventDefault();
      const pId = addToBagBtn.dataset.addToBagId;
      const product = store.addToCart(pId, 1);
      if (product) {
        openDrawer('cart-drawer');
        ToastManager.show(`Added <strong>${product.name}</strong> to your shopping bag!`);
      }
      return;
    }

    // 2. Wishlist Heart Toggle
    const wishlistBtn = e.target.closest('[data-wishlist-id]');
    if (wishlistBtn && !wishlistBtn.closest('.wishlist-item')) {
      e.preventDefault();
      const pId = wishlistBtn.dataset.wishlistId;
      const added = store.toggleWishlist(pId);
      const product = PRODUCTS_DATA.find(p => p.id === pId);
      const name = product ? product.name : 'Item';
      ToastManager.show(
        added ? `Added <strong>${name}</strong> to your Wishlist` : `Removed <strong>${name}</strong> from Wishlist`,
        added ? 'wishlist' : 'info'
      );
      return;
    }

    // 3. Quick View Trigger
    const quickviewTrigger = e.target.closest('[data-quickview-id]');
    if (quickviewTrigger) {
      e.preventDefault();
      const pId = quickviewTrigger.dataset.quickviewId;
      renderQuickViewModal(pId);
      return;
    }

    // 4. Cart Qty Controls
    const qtyIncBtn = e.target.closest('[data-cart-qty-increase]');
    if (qtyIncBtn) {
      const idx = Number(qtyIncBtn.dataset.cartQtyIncrease);
      store.updateCartQty(idx, store.cart[idx].qty + 1);
      return;
    }
    const qtyDecBtn = e.target.closest('[data-cart-qty-decrease]');
    if (qtyDecBtn) {
      const idx = Number(qtyDecBtn.dataset.cartQtyDecrease);
      store.updateCartQty(idx, store.cart[idx].qty - 1);
      return;
    }

    // 5. Remove from Cart
    const removeCartBtn = e.target.closest('[data-remove-cart]');
    if (removeCartBtn) {
      const idx = Number(removeCartBtn.dataset.removeCart);
      store.removeFromCart(idx);
      ToastManager.show('Item removed from your shopping bag', 'info');
      return;
    }

    // 6. Move Wishlist item to Cart
    const moveToCartBtn = e.target.closest('[data-move-to-cart]');
    if (moveToCartBtn) {
      const pId = moveToCartBtn.dataset.moveToCart;
      store.addToCart(pId, 1);
      store.toggleWishlist(pId);
      renderCartDrawer();
      ToastManager.show('Item moved to your shopping bag!');
      return;
    }

    // 7. Remove from Wishlist
    const removeWishlistBtn = e.target.closest('[data-remove-wishlist]');
    if (removeWishlistBtn) {
      const pId = removeWishlistBtn.dataset.removeWishlist;
      store.toggleWishlist(pId);
      ToastManager.show('Item removed from Wishlist', 'info');
      return;
    }

    // 8. Apply Coupon Button in Cart
    if (e.target.id === 'apply-coupon-btn') {
      const input = document.getElementById('coupon-code-input');
      if (input) {
        store.applyCoupon(input.value).then(res => {
          ToastManager.show(res.message, res.success ? 'success' : 'error');
        });
      }
      return;
    }

    // 9. Remove Coupon Button in Cart
    if (e.target.id === 'remove-coupon-btn') {
      store.removeCoupon();
      ToastManager.show('Coupon removed', 'info');
      return;
    }

    // 10. Proceed to Checkout Trigger
    if (e.target.id === 'btn-proceed-checkout') {
      if (store.cart.length === 0) {
        ToastManager.show('Your bag is empty! Add items first.', 'error');
        return;
      }
      closeAllDrawers();
      renderCheckoutModal();
      openModal('checkout-modal');
      return;
    }

    // 11. Copy Promo Code Button
    const copyPromoBtn = e.target.closest('.copy-coupon-btn');
    if (copyPromoBtn) {
      const code = copyPromoBtn.dataset.coupon;
      navigator.clipboard?.writeText(code).then(() => {
        ToastManager.show(`Coupon code <strong>${code}</strong> copied to clipboard!`);
      }).catch(() => {
        ToastManager.show(`Use coupon: <strong>${code}</strong> at checkout!`);
      });
      return;
    }

    // 12. Quick Fill Demo Login Buttons
    if (e.target.id === 'btn-fill-customer') {
      document.getElementById('auth-email').value = 'customer@migriga.com';
      document.getElementById('auth-pass').value = 'customer123';
      ToastManager.show('Filled Customer credentials: customer@migriga.com', 'info');
      return;
    }
    if (e.target.id === 'btn-fill-admin') {
      document.getElementById('auth-email').value = 'admin@migriga.com';
      document.getElementById('auth-pass').value = 'admin123';
      ToastManager.show('Filled Admin credentials: admin@migriga.com', 'info');
      return;
    }
  });
}

// 6. Forms Handling
function initForms() {
  // Newsletter Form
  const newsletterForm = document.getElementById('newsletter-form');
  if (newsletterForm) {
    newsletterForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const emailInput = document.getElementById('newsletter-email');
      const email = emailInput?.value.trim();

      if (email && email.includes('@')) {
        try {
          await fetch('/api/newsletter', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
          });
        } catch (e) {}

        emailInput.value = '';
        const modal = document.getElementById('coupon-success-modal');
        if (modal) {
          openModal('coupon-success-modal');
        } else {
          ToastManager.show('Welcome to MIGRIGA! Use code <strong>WELCOME15</strong> for 15% off.');
        }
      } else {
        ToastManager.show('Please enter a valid email address.', 'error');
      }
    });
  }

  // Live Search Form
  const searchInput = document.getElementById('main-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      renderSearchResults(e.target.value);
    });
  }

  document.querySelectorAll('.trending-tag').forEach(tag => {
    tag.addEventListener('click', () => {
      if (searchInput) {
        searchInput.value = tag.dataset.query;
        renderSearchResults(tag.dataset.query);
      }
    });
  });

  // Checkout Form Submission (Connected to SQLite DB via /api/orders)
  const checkoutForm = document.getElementById('checkout-form');
  if (checkoutForm) {
    checkoutForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const fullName = document.getElementById('co-name')?.value.trim();
      const phone = document.getElementById('co-phone')?.value.trim();
      const address = document.getElementById('co-address')?.value.trim();
      const city = document.getElementById('co-city')?.value.trim();
      const pincode = document.getElementById('co-pincode')?.value.trim();
      const paymentMethod = document.querySelector('input[name="paymentMethod"]:checked')?.value || 'UPI';

      if (!fullName || !phone || !address || !city || !pincode) {
        ToastManager.show('Please fill in all delivery details.', 'error');
        return;
      }

      const submitBtn = checkoutForm.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Processing Secure Order...';
      }

      const order = await store.createOrder(
        { fullName, phone, address, city, pincode },
        paymentMethod
      );

      // Render Order Confirmation screen
      const modalBody = document.querySelector('#checkout-modal .modal-body');
      if (modalBody) {
        modalBody.innerHTML = `
          <div class="order-confirmed-screen">
            <div class="confirm-icon-circle">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#2E7D32" stroke-width="2.2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
            <h2 class="confirm-title">Order Successfully Placed!</h2>
            <p class="confirm-order-id">Order Reference: <strong>#${order.id}</strong></p>
            <p class="confirm-sub">Thank you, <strong>${order.shippingDetails.fullName}</strong>. A confirmation SMS & tracking details have been sent to <strong>${order.shippingDetails.phone}</strong>.</p>
            
            <div class="confirm-details-card">
              <div class="confirm-row">
                <span>Database Sync:</span>
                <strong style="color: #2E7D32;">✓ Saved in SQLite Database</strong>
              </div>
              <div class="confirm-row">
                <span>Estimated Luxury Delivery:</span>
                <strong>2-4 Business Days</strong>
              </div>
              <div class="confirm-row">
                <span>Shipping Address:</span>
                <span>${order.shippingDetails.address}, ${order.shippingDetails.city} - ${order.shippingDetails.pincode}</span>
              </div>
              <div class="confirm-row">
                <span>Payment Method:</span>
                <strong>${order.paymentMethod}</strong>
              </div>
              <div class="confirm-row highlight">
                <span>Total Amount Paid:</span>
                <strong>${formatPrice(order.totals.total)}</strong>
              </div>
            </div>

            <div class="confirm-actions" style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
              <button class="btn btn-primary" onclick="closeAllModals(); scrollToSection('shop');">
                Continue Shopping
              </button>
              <button class="btn btn-secondary" onclick="closeAllModals(); openModal('account-modal');">
                View in My Orders
              </button>
            </div>
          </div>
        `;
      }

      ToastManager.show(`Order #${order.id} confirmed and saved to SQLite!`);
    });
  }

  // Account Modal (Customer & Admin Unified Login)
  const authForm = document.getElementById('account-auth-form');
  if (authForm) {
    authForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('auth-email')?.value.trim();
      const password = document.getElementById('auth-pass')?.value;

      if (!email || !password) {
        ToastManager.show('Please enter email and password.', 'error');
        return;
      }

      const res = await store.login(email, password);
      if (res.success) {
        if (res.user.role === 'admin') {
          ToastManager.show(`Welcome Administrator! Admin Portal unlocked.`, 'success');
          updateUserAccountUI(res.user);
        } else {
          ToastManager.show(`Welcome back, ${res.user.full_name}!`);
          updateUserAccountUI(res.user);
        }
      } else {
        ToastManager.show(res.message || 'Login failed. Check credentials.', 'error');
      }
    });
  }
}

function updateUserAccountUI(user) {
  const profileContainer = document.getElementById('account-modal-body');
  if (!profileContainer) return;

  // Add/update top navbar admin badge if role === 'admin'
  let adminNavBtn = document.getElementById('header-admin-portal-btn');
  if (user && user.role === 'admin') {
    if (!adminNavBtn) {
      const headerActions = document.querySelector('.header-actions');
      adminNavBtn = document.createElement('a');
      adminNavBtn.id = 'header-admin-portal-btn';
      adminNavBtn.href = '/admin.html';
      adminNavBtn.className = 'btn btn-sm btn-primary';
      adminNavBtn.style.cssText = 'background: #C5A059; color: #141312; font-weight: 700; border-radius: 9999px; padding: 6px 14px;';
      adminNavBtn.innerHTML = '👑 Admin Portal';
      headerActions?.prepend(adminNavBtn);
    }
  } else {
    adminNavBtn?.remove();
  }

  if (user) {
    const isAdmin = user.role === 'admin';
    profileContainer.innerHTML = `
      <div class="account-logged-in">
        <div class="profile-header">
          <div class="profile-avatar" style="${isAdmin ? 'background: #C5A059; color: #141312;' : ''}">
            ${isAdmin ? '👑' : user.full_name.charAt(0).toUpperCase()}
          </div>
          <div class="profile-meta">
            <h3>${user.full_name}</h3>
            <p>${user.email}</p>
            <span class="migriga-tier" style="${isAdmin ? 'color: #C5A059; font-weight: 700;' : ''}">
              ${isAdmin ? '👑 Store Administrator' : '★ MIGRIGA VIP Member'}
            </span>
          </div>
        </div>

        ${isAdmin ? `
          <div style="background: rgba(197, 160, 89, 0.12); border: 1px solid #C5A059; border-radius: 10px; padding: 18px; text-align: center;">
            <h4 style="color: #C5A059; font-size: 1.1rem; margin-bottom: 6px;">Administrator Privileges Active</h4>
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 14px;">
              Manage customer orders, track inventory, view subscribers, and monitor store analytics.
            </p>
            <a href="/admin.html" class="btn btn-primary btn-block" style="background: #C5A059; color: #141312; font-weight: 700;">
              LAUNCH ADMIN PORTAL 👑
            </a>
          </div>
        ` : ''}

        <div class="profile-orders-section">
          <h4>${isAdmin ? 'All Recent Store Orders' : 'My Orders & Deliveries'}</h4>
          <div class="profile-orders-list">
            ${store.orderHistory.length === 0 ? `
              <p style="font-size: 0.85rem; color: var(--text-muted); text-align: center; padding: 20px;">
                No orders found. Discover our products and place your first order!
              </p>
            ` : store.orderHistory.map(order => `
              <div class="order-history-card">
                <div class="order-h-header">
                  <strong>#${order.id}</strong>
                  <span class="order-status-badge status-${(order.status || 'confirmed').toLowerCase()}">${order.status || 'Confirmed'}</span>
                </div>
                <div class="order-h-items">
                  ${(order.items || []).map(it => `<div>${it.product_name || it.name} (x${it.qty})</div>`).join('')}
                </div>
                <div class="order-h-total">
                  <span>${order.date}</span>
                  <strong>${formatPrice(order.totals ? order.totals.total : order.total)}</strong>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="profile-actions">
          <button class="btn btn-secondary btn-block" onclick="store.logout(); location.reload();">
            Sign Out
          </button>
        </div>
      </div>
    `;
  }
}

// 7. Sticky Header Scroll Effect
function initHeaderScroll() {
  const header = document.querySelector('.main-header');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 40) {
      header?.classList.add('scrolled');
    } else {
      header?.classList.remove('scrolled');
    }
  }, { passive: true });
}
