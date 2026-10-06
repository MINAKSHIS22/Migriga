// MIGRIGA UI Component Renderers & Interactions

// Utility: format INR currency
function formatPrice(amount) {
  return '₹' + Number(amount).toLocaleString('en-IN');
}

// Toast Notification Manager
class ToastManager {
  static show(message, type = 'success', duration = 3200) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `luxury-toast toast-${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'wishlist') {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="#C69279" stroke="#C69279" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
    } else {
      iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    }

    toast.innerHTML = `
      <div class="toast-icon">${iconSvg}</div>
      <div class="toast-body">${message}</div>
      <button class="toast-close" aria-label="Close">&times;</button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.classList.add('toast-hiding');
      setTimeout(() => toast.remove(), 300);
    });

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-visible'));

    setTimeout(() => {
      if (toast.parentElement) {
        toast.classList.add('toast-hiding');
        setTimeout(() => toast.remove(), 300);
      }
    }, duration);
  }
}

// Generate Star Rating HTML
function renderRatingStars(rating, reviewCount) {
  const fullStars = Math.floor(rating);
  let starsHtml = '';
  for (let i = 0; i < 5; i++) {
    if (i < fullStars) {
      starsHtml += `<span class="star-icon filled">★</span>`;
    } else {
      starsHtml += `<span class="star-icon empty">★</span>`;
    }
  }
  return `
    <div class="product-rating">
      <span class="stars">${starsHtml}</span>
      <span class="rating-num">${rating.toFixed(1)}</span>
      ${reviewCount ? `<span class="review-count">(${reviewCount.toLocaleString()})</span>` : ''}
    </div>
  `;
}

// Render Single Product Card HTML
function renderProductCard(product) {
  const isWishlisted = store.isInWishlist(product.id);
  const discountPercent = Math.round(((product.originalPrice - product.price) / product.originalPrice) * 100);

  return `
    <div class="product-card" data-product-id="${product.id}" data-category="${product.category}">
      <div class="product-media">
        ${product.badge ? `<span class="product-badge">${product.badge}</span>` : ''}
        ${discountPercent > 0 ? `<span class="product-discount-badge">-${discountPercent}%</span>` : ''}
        
        <button class="wishlist-btn ${isWishlisted ? 'active' : ''}" 
                data-wishlist-id="${product.id}" 
                aria-label="${isWishlisted ? 'Remove from Wishlist' : 'Add to Wishlist'}">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="${isWishlisted ? '#B07D62' : 'none'}" stroke="currentColor" stroke-width="1.8">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
        </button>

        <a href="#quickview" class="product-img-link" data-quickview-id="${product.id}">
          <img src="${product.image}" alt="${product.name}" class="product-img main-img" loading="lazy" />
          ${product.secondaryImage ? `<img src="${product.secondaryImage}" alt="${product.name}" class="product-img hover-img" loading="lazy" />` : ''}
        </a>

        <div class="product-overlay-actions">
          <button class="btn-quickview" data-quickview-id="${product.id}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
            Quick View
          </button>
          <button class="btn-add-to-bag" data-add-to-bag-id="${product.id}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <path d="M16 10a4 4 0 0 1-8 0"></path>
            </svg>
            Add To Bag
          </button>
        </div>
      </div>

      <div class="product-info">
        <span class="product-category-label">${product.categoryName}</span>
        <h3 class="product-title">
          <a href="#quickview" data-quickview-id="${product.id}">${product.name}</a>
        </h3>
        <p class="product-tagline">${product.tagline || product.description.substring(0, 60) + '...'}</p>
        
        ${renderRatingStars(product.rating, product.reviewCount)}

        <div class="product-pricing">
          <span class="current-price">${formatPrice(product.price)}</span>
          ${product.originalPrice ? `<span class="original-price">${formatPrice(product.originalPrice)}</span>` : ''}
        </div>

        ${product.shades ? `
          <div class="product-shades-preview">
            ${product.shades.slice(0, 4).map(s => `
              <span class="shade-dot" style="background-color: ${s.hex}" title="${s.name}"></span>
            `).join('')}
            ${product.shades.length > 4 ? `<span class="shade-more">+${product.shades.length - 4}</span>` : ''}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

// Render Cart Drawer
function renderCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  if (!drawer) return;

  const count = store.getCartCount();
  const totals = store.getCartTotals();

  // Update header badges
  document.querySelectorAll('.cart-count-badge').forEach(b => {
    b.textContent = count;
    b.style.display = count > 0 ? 'flex' : 'none';
  });

  const cartItemsList = drawer.querySelector('.drawer-items-list');
  const cartFooter = drawer.querySelector('.drawer-footer');
  const progressContainer = drawer.querySelector('.free-shipping-progress');

  // Free shipping banner
  if (progressContainer) {
    if (totals.isFreeShipping && count > 0) {
      progressContainer.innerHTML = `
        <div class="shipping-msg unlocked">
          <span>✨</span> Congratulations! You unlocked <strong>FREE Luxury Shipping</strong>
        </div>
        <div class="progress-bar-track">
          <div class="progress-bar-fill" style="width: 100%"></div>
        </div>
      `;
    } else if (count > 0) {
      progressContainer.innerHTML = `
        <div class="shipping-msg">
          Add <strong>${formatPrice(totals.amountToFreeShipping)}</strong> more to get <strong>FREE SHIPPING</strong>
        </div>
        <div class="progress-bar-track">
          <div class="progress-bar-fill" style="width: ${totals.progressPercent}%"></div>
        </div>
      `;
    } else {
      progressContainer.innerHTML = `
        <div class="shipping-msg">
          Free shipping on orders over <strong>${formatPrice(store.freeShippingThreshold)}</strong>
        </div>
      `;
    }
  }

  // Items list
  if (count === 0) {
    cartItemsList.innerHTML = `
      <div class="empty-cart-state">
        <div class="empty-cart-icon">
          <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#D3B8AA" stroke-width="1.2">
            <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <path d="M16 10a4 4 0 0 1-8 0"></path>
          </svg>
        </div>
        <h3>Your Shopping Bag is Empty</h3>
        <p>Discover our bestsellers and enhance your daily beauty ritual.</p>
        <button class="btn btn-primary" onclick="closeAllDrawers(); scrollToSection('bestsellers');">
          Start Shopping
        </button>
      </div>
    `;
    if (cartFooter) cartFooter.style.display = 'none';
  } else {
    if (cartFooter) cartFooter.style.display = 'block';
    cartItemsList.innerHTML = store.cart.map((item, index) => `
      <div class="cart-item" data-cart-index="${index}">
        <img src="${item.image}" alt="${item.name}" class="cart-item-img" />
        <div class="cart-item-details">
          <div class="cart-item-header">
            <h4 class="cart-item-name">${item.name}</h4>
            <button class="cart-item-remove" data-remove-cart="${index}" aria-label="Remove item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          ${item.shade ? `<div class="cart-item-meta"><span>Shade:</span> <strong>${item.shade}</strong></div>` : ''}
          ${item.size ? `<div class="cart-item-meta"><span>Size:</span> <strong>${item.size}</strong></div>` : ''}
          
          <div class="cart-item-bottom">
            <div class="qty-control">
              <button class="qty-btn" data-cart-qty-decrease="${index}">-</button>
              <span class="qty-val">${item.qty}</span>
              <button class="qty-btn" data-cart-qty-increase="${index}">+</button>
            </div>
            <div class="cart-item-price">
              ${formatPrice(item.price * item.qty)}
            </div>
          </div>
        </div>
      </div>
    `).join('');

    // Update coupon view in footer
    const couponContainer = cartFooter.querySelector('.cart-coupon-section');
    if (couponContainer) {
      if (totals.coupon) {
        couponContainer.innerHTML = `
          <div class="applied-coupon-pill">
            <span class="coupon-tag">✨ ${totals.coupon.code} applied (${totals.coupon.discountPercent}% OFF)</span>
            <button class="coupon-remove-btn" id="remove-coupon-btn">&times;</button>
          </div>
        `;
      } else {
        couponContainer.innerHTML = `
          <div class="coupon-input-group">
            <input type="text" id="coupon-code-input" placeholder="Promo code (e.g. GLOW20)" />
            <button type="button" id="apply-coupon-btn" class="btn btn-secondary btn-sm">Apply</button>
          </div>
        `;
      }
    }

    // Update totals
    cartFooter.querySelector('.summary-subtotal').textContent = formatPrice(totals.subtotal);
    const discountRow = cartFooter.querySelector('.summary-discount-row');
    if (totals.discount > 0) {
      discountRow.style.display = 'flex';
      discountRow.querySelector('.summary-discount').textContent = `-${formatPrice(totals.discount)}`;
    } else {
      discountRow.style.display = 'none';
    }
    cartFooter.querySelector('.summary-shipping').textContent = totals.shipping === 0 ? 'FREE' : formatPrice(totals.shipping);
    cartFooter.querySelector('.summary-total').textContent = formatPrice(totals.total);
  }
}

// Render Wishlist Drawer
function renderWishlistDrawer() {
  const drawer = document.getElementById('wishlist-drawer');
  if (!drawer) return;

  const count = store.getWishlistCount();
  document.querySelectorAll('.wishlist-count-badge').forEach(b => {
    b.textContent = count;
    b.style.display = count > 0 ? 'flex' : 'none';
  });

  const list = drawer.querySelector('.drawer-items-list');
  const products = store.getWishlistProducts();

  if (products.length === 0) {
    list.innerHTML = `
      <div class="empty-wishlist-state">
        <div class="empty-wishlist-icon">
          <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#D3B8AA" stroke-width="1.2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
        </div>
        <h3>Your Wishlist is Empty</h3>
        <p>Save your favorite beauty essentials here by clicking the heart icon on any product.</p>
        <button class="btn btn-primary" onclick="closeAllDrawers(); scrollToSection('shop');">
          Explore Products
        </button>
      </div>
    `;
  } else {
    list.innerHTML = products.map(product => `
      <div class="wishlist-item" data-wishlist-id="${product.id}">
        <img src="${product.image}" alt="${product.name}" class="wishlist-item-img" />
        <div class="wishlist-item-details">
          <h4 class="wishlist-item-name">${product.name}</h4>
          <span class="wishlist-item-price">${formatPrice(product.price)}</span>
          <div class="wishlist-item-actions">
            <button class="btn btn-secondary btn-sm" data-move-to-cart="${product.id}">
              Add to Bag
            </button>
            <button class="btn-text-danger" data-remove-wishlist="${product.id}">
              Remove
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }
}

// Render Quick View / Product Modal
function renderQuickViewModal(productId) {
  const modal = document.getElementById('quickview-modal');
  if (!modal) return;

  const product = PRODUCTS_DATA.find(p => p.id === productId);
  if (!product) return;

  const content = modal.querySelector('.modal-body');
  const discountPercent = Math.round(((product.originalPrice - product.price) / product.originalPrice) * 100);

  content.innerHTML = `
    <div class="quickview-grid">
      <div class="quickview-gallery">
        <div class="quickview-main-image-wrap">
          ${product.badge ? `<span class="product-badge">${product.badge}</span>` : ''}
          <img src="${product.image}" id="qv-main-image" alt="${product.name}" />
        </div>
        <div class="quickview-thumbnails">
          <button class="qv-thumb active" data-img-src="${product.image}">
            <img src="${product.image}" alt="Thumbnail 1" />
          </button>
          ${product.secondaryImage ? `
            <button class="qv-thumb" data-img-src="${product.secondaryImage}">
              <img src="${product.secondaryImage}" alt="Thumbnail 2" />
            </button>
          ` : ''}
        </div>
      </div>

      <div class="quickview-details">
        <span class="product-category-label">${product.categoryName}</span>
        <h2 class="qv-title">${product.name}</h2>
        <p class="qv-tagline">${product.tagline}</p>

        ${renderRatingStars(product.rating, product.reviewCount)}

        <div class="qv-pricing">
          <span class="current-price">${formatPrice(product.price)}</span>
          <span class="original-price">${formatPrice(product.originalPrice)}</span>
          ${discountPercent > 0 ? `<span class="save-badge">Save ${discountPercent}%</span>` : ''}
        </div>

        <p class="qv-desc">${product.description}</p>

        ${product.shades ? `
          <div class="qv-option-group">
            <label class="option-label">Shade: <strong id="selected-shade-name">${product.shades[0].name}</strong></label>
            <div class="shade-selector">
              ${product.shades.map((s, idx) => `
                <button type="button" class="shade-option-btn ${idx === 0 ? 'selected' : ''}" 
                        data-shade="${s.name}" 
                        style="background-color: ${s.hex}"
                        title="${s.name}" aria-label="${s.name}">
                </button>
              `).join('')}
            </div>
          </div>
        ` : ''}

        ${product.sizes ? `
          <div class="qv-option-group">
            <label class="option-label">Select Size / Volume:</label>
            <div class="size-selector">
              ${product.sizes.map((sz, idx) => `
                <button type="button" class="size-option-btn ${idx === 0 ? 'selected' : ''}" data-size="${sz}">
                  ${sz}
                </button>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div class="qv-actions-row">
          <div class="qty-control qv-qty">
            <button class="qty-btn" id="qv-qty-minus">-</button>
            <span class="qty-val" id="qv-qty-val">1</span>
            <button class="qty-btn" id="qv-qty-plus">+</button>
          </div>
          <button class="btn btn-primary btn-add-bag-qv" id="qv-add-to-cart-btn" data-product-id="${product.id}">
            Add to Bag • ${formatPrice(product.price)}
          </button>
          <button class="btn btn-secondary btn-wishlist-qv ${store.isInWishlist(product.id) ? 'active' : ''}" 
                  id="qv-wishlist-btn" data-product-id="${product.id}" title="Wishlist">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="${store.isInWishlist(product.id) ? '#B07D62' : 'none'}" stroke="currentColor" stroke-width="1.8">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
            </svg>
          </button>
        </div>

        <div class="qv-delivery-perks">
          <div class="perk-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#B07D62" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
            <span>Free Express Delivery on orders over ₹999</span>
          </div>
          <div class="perk-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#B07D62" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            <span>100% Dermatologically Tested & Cruelty-Free</span>
          </div>
        </div>

        <div class="qv-tabs">
          <div class="qv-tab-headers">
            <button class="qv-tab-btn active" data-tab="benefits">Key Benefits</button>
            <button class="qv-tab-btn" data-tab="ingredients">Ingredients</button>
            <button class="qv-tab-btn" data-tab="howtouse">How to Use</button>
          </div>
          <div class="qv-tab-content">
            <div class="tab-pane active" id="tab-benefits">
              <ul class="benefits-checklist">
                ${product.benefits.map(b => `<li><span class="check-icon">✓</span> ${b}</li>`).join('')}
              </ul>
            </div>
            <div class="tab-pane" id="tab-ingredients">
              <p class="tab-text">${product.ingredients}</p>
            </div>
            <div class="tab-pane" id="tab-howtouse">
              <p class="tab-text">${product.howToUse}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach quickview specific listeners
  modal.querySelectorAll('.qv-thumb').forEach(thumb => {
    thumb.addEventListener('click', () => {
      modal.querySelectorAll('.qv-thumb').forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
      modal.querySelector('#qv-main-image').src = thumb.dataset.imgSrc;
    });
  });

  // Shade selector
  modal.querySelectorAll('.shade-option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      modal.querySelectorAll('.shade-option-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      const shadeNameEl = modal.querySelector('#selected-shade-name');
      if (shadeNameEl) shadeNameEl.textContent = btn.dataset.shade;
    });
  });

  // Size selector
  modal.querySelectorAll('.size-option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      modal.querySelectorAll('.size-option-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    });
  });

  // Qty selector
  let qvQty = 1;
  const qtyVal = modal.querySelector('#qv-qty-val');
  modal.querySelector('#qv-qty-minus').addEventListener('click', () => {
    if (qvQty > 1) {
      qvQty--;
      qtyVal.textContent = qvQty;
      modal.querySelector('#qv-add-to-cart-btn').innerHTML = `Add to Bag • ${formatPrice(product.price * qvQty)}`;
    }
  });
  modal.querySelector('#qv-qty-plus').addEventListener('click', () => {
    if (qvQty < 10) {
      qvQty++;
      qtyVal.textContent = qvQty;
      modal.querySelector('#qv-add-to-cart-btn').innerHTML = `Add to Bag • ${formatPrice(product.price * qvQty)}`;
    }
  });

  // Add to Bag from Quick View
  modal.querySelector('#qv-add-to-cart-btn').addEventListener('click', () => {
    const selectedShadeBtn = modal.querySelector('.shade-option-btn.selected');
    const selectedSizeBtn = modal.querySelector('.size-option-btn.selected');
    const shade = selectedShadeBtn ? selectedShadeBtn.dataset.shade : null;
    const size = selectedSizeBtn ? selectedSizeBtn.dataset.size : null;

    store.addToCart(product.id, qvQty, { shade, size });
    closeAllModals();
    openDrawer('cart-drawer');
    ToastManager.show(`Added ${qvQty}x <strong>${product.name}</strong> to your shopping bag!`);
  });

  // Wishlist toggle from Quick View
  const wishlistBtn = modal.querySelector('#qv-wishlist-btn');
  wishlistBtn.addEventListener('click', () => {
    const added = store.toggleWishlist(product.id);
    wishlistBtn.classList.toggle('active', added);
    wishlistBtn.querySelector('svg').setAttribute('fill', added ? '#B07D62' : 'none');
    ToastManager.show(
      added ? `Added <strong>${product.name}</strong> to your Wishlist` : `Removed from Wishlist`,
      added ? 'wishlist' : 'info'
    );
  });

  // Tab switching
  modal.querySelectorAll('.qv-tab-btn').forEach(tabBtn => {
    tabBtn.addEventListener('click', () => {
      modal.querySelectorAll('.qv-tab-btn').forEach(b => b.classList.remove('active'));
      modal.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      tabBtn.classList.add('active');
      const targetPane = modal.querySelector(`#tab-${tabBtn.dataset.tab}`);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  modal.classList.add('open');
}

// Render Search Results
function renderSearchResults(query) {
  const container = document.getElementById('search-results-grid');
  const countEl = document.getElementById('search-result-count');
  if (!container) return;

  const clean = (query || '').trim().toLowerCase();
  if (!clean) {
    container.innerHTML = '';
    if (countEl) countEl.textContent = 'Type above to explore our luxury catalog';
    return;
  }

  const matches = PRODUCTS_DATA.filter(p => 
    p.name.toLowerCase().includes(clean) ||
    p.category.toLowerCase().includes(clean) ||
    p.description.toLowerCase().includes(clean) ||
    p.ingredients.toLowerCase().includes(clean)
  );

  if (countEl) {
    countEl.textContent = `Found ${matches.length} result${matches.length === 1 ? '' : 's'} for "${query}"`;
  }

  if (matches.length === 0) {
    container.innerHTML = `
      <div class="search-empty">
        <p>No products match your search. Try searching for <em>serum</em>, <em>lipstick</em>, <em>fragrance</em> or <em>cream</em>.</p>
      </div>
    `;
  } else {
    container.innerHTML = matches.map(p => renderProductCard(p)).join('');
  }
}

// Render Checkout Modal
function renderCheckoutModal() {
  const modal = document.getElementById('checkout-modal');
  if (!modal) return;

  const totals = store.getCartTotals();
  const summaryList = modal.querySelector('.checkout-order-items');
  const totalDisplay = modal.querySelector('.checkout-final-total');
  const subtotalDisplay = modal.querySelector('.checkout-subtotal');
  const shippingDisplay = modal.querySelector('.checkout-shipping');
  const discountDisplay = modal.querySelector('.checkout-discount');

  if (summaryList) {
    summaryList.innerHTML = store.cart.map(item => `
      <div class="checkout-item-row">
        <img src="${item.image}" alt="${item.name}" class="checkout-item-thumb" />
        <div class="checkout-item-meta">
          <span class="item-name">${item.name}</span>
          <span class="item-sub">Qty: ${item.qty} ${item.shade ? `• ${item.shade}` : ''}</span>
        </div>
        <span class="item-price">${formatPrice(item.price * item.qty)}</span>
      </div>
    `).join('');
  }

  if (subtotalDisplay) subtotalDisplay.textContent = formatPrice(totals.subtotal);
  if (shippingDisplay) shippingDisplay.textContent = totals.shipping === 0 ? 'FREE' : formatPrice(totals.shipping);
  if (discountDisplay) {
    if (totals.discount > 0) {
      discountDisplay.parentElement.style.display = 'flex';
      discountDisplay.textContent = `-${formatPrice(totals.discount)}`;
    } else {
      discountDisplay.parentElement.style.display = 'none';
    }
  }
  if (totalDisplay) totalDisplay.textContent = formatPrice(totals.total);
}

// Testimonials Carousel Controller
class TestimonialSlider {
  constructor() {
    this.testimonials = TESTIMONIALS_DATA;
    this.currentIndex = 0;
    this.cardEl = document.getElementById('testimonial-card-inner');
    this.dotsContainer = document.getElementById('testimonial-dots');
    this.init();
  }

  init() {
    if (!this.cardEl) return;
    this.render();
    this.renderDots();
    
    const prevBtn = document.getElementById('testimonial-prev-btn');
    const nextBtn = document.getElementById('testimonial-next-btn');

    if (prevBtn) prevBtn.addEventListener('click', () => this.prev());
    if (nextBtn) nextBtn.addEventListener('click', () => this.next());

    // Auto rotate every 7 seconds
    setInterval(() => this.next(), 7000);
  }

  render() {
    const t = this.testimonials[this.currentIndex];
    if (!t || !this.cardEl) return;

    this.cardEl.style.opacity = '0';
    this.cardEl.style.transform = 'translateY(10px)';

    setTimeout(() => {
      this.cardEl.innerHTML = `
        <div class="testimonial-avatar-wrap">
          <img src="${t.avatar}" alt="${t.name}" class="testimonial-avatar" />
          <div class="verified-badge" title="Verified Customer">✓</div>
        </div>
        <div class="testimonial-content">
          <div class="testimonial-stars">
            ${'★'.repeat(t.rating)}
          </div>
          <h4 class="testimonial-headline">“${t.headline}”</h4>
          <p class="testimonial-quote">“${t.quote}”</p>
          <div class="testimonial-author-block">
            <span class="testimonial-name">${t.name}</span>
            <span class="testimonial-role">${t.role}</span>
          </div>
        </div>
      `;
      this.cardEl.style.opacity = '1';
      this.cardEl.style.transform = 'translateY(0)';
    }, 200);

    this.updateDots();
  }

  renderDots() {
    if (!this.dotsContainer) return;
    this.dotsContainer.innerHTML = this.testimonials.map((_, i) => `
      <button class="slider-dot ${i === this.currentIndex ? 'active' : ''}" data-index="${i}" aria-label="Slide ${i+1}"></button>
    `).join('');

    this.dotsContainer.querySelectorAll('.slider-dot').forEach(dot => {
      dot.addEventListener('click', () => {
        this.currentIndex = Number(dot.dataset.index);
        this.render();
      });
    });
  }

  updateDots() {
    if (!this.dotsContainer) return;
    this.dotsContainer.querySelectorAll('.slider-dot').forEach((dot, i) => {
      dot.classList.toggle('active', i === this.currentIndex);
    });
  }

  next() {
    this.currentIndex = (this.currentIndex + 1) % this.testimonials.length;
    this.render();
  }

  prev() {
    this.currentIndex = (this.currentIndex - 1 + this.testimonials.length) % this.testimonials.length;
    this.render();
  }
}

// Countdown Timer Controller for Promotional Banner
function startCountdownTimer() {
  const hoursEl = document.getElementById('timer-hours');
  const minsEl = document.getElementById('timer-mins');
  const secsEl = document.getElementById('timer-secs');
  if (!hoursEl || !minsEl || !secsEl) return;

  // 2 days 14 hours 45 mins from now
  let remainingSeconds = (2 * 24 * 3600) + (14 * 3600) + (45 * 60) + 30;

  setInterval(() => {
    remainingSeconds--;
    if (remainingSeconds <= 0) remainingSeconds = 86400 * 3;

    const hours = Math.floor(remainingSeconds / 3600);
    const mins = Math.floor((remainingSeconds % 3600) / 60);
    const secs = remainingSeconds % 60;

    hoursEl.textContent = String(hours).padStart(2, '0');
    minsEl.textContent = String(mins).padStart(2, '0');
    secsEl.textContent = String(secs).padStart(2, '0');
  }, 1000);
}
