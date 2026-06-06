/* ScanKart — shop page: scanner, catalog browse, cart, checkout */
(() => {
  const { outletId, outletName, razorpayEnabled } = window.SCANKART;
  const CART_KEY = `scankart_cart_${outletId}`;

  let products = [];            // full catalog for this outlet
  let cart = loadCart();        // { productId: qty }
  let scanner = null;
  let lastScan = { code: null, at: 0 };

  const $ = (id) => document.getElementById(id);
  const rupees = (n) => '₹' + n.toFixed(2);

  // ---------- cart persistence ----------
  function loadCart() {
    try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; }
    catch { return {}; }
  }
  function saveCart() { localStorage.setItem(CART_KEY, JSON.stringify(cart)); }

  // ---------- catalog ----------
  async function loadProducts() {
    const res = await fetch(`/api/outlets/${outletId}/products`);
    products = await res.json();
    renderProducts();
    renderCart();
  }

  function productById(id) { return products.find(p => p.id === Number(id)); }

  function renderProducts() {
    const term = $('search').value.trim().toLowerCase();
    const list = $('product-list');
    const filtered = products.filter(p =>
      !term || p.name.toLowerCase().includes(term) || p.category.toLowerCase().includes(term));
    if (!filtered.length) {
      list.innerHTML = '<p class="col-span-full text-center text-sm text-gray-400 py-8">No products found</p>';
      return;
    }
    list.innerHTML = filtered.map(p => {
      const qty = cart[p.id] || 0;
      const out = p.stock <= 0;
      return `
      <div class="bg-white rounded-2xl border border-gray-100 shadow-sm p-3 flex items-center gap-3 ${out ? 'opacity-50' : ''}">
        <div class="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center text-2xl shrink-0">${p.emoji}</div>
        <div class="flex-1 min-w-0">
          <p class="font-semibold text-sm leading-tight truncate">${p.name}</p>
          <p class="text-xs text-gray-400">${p.category} · ${rupees(p.price)}</p>
        </div>
        ${out
          ? '<span class="text-[10px] font-bold text-red-500 uppercase">Out of stock</span>'
          : qty === 0
            ? `<button data-add="${p.id}" class="bg-emerald-600 text-white text-sm font-bold rounded-xl px-4 py-2 active:scale-95 transition">Add</button>`
            : stepper(p.id, qty)}
      </div>`;
    }).join('');
  }

  function stepper(id, qty) {
    return `
      <div class="flex items-center gap-2 bg-emerald-50 rounded-xl px-1 py-1">
        <button data-dec="${id}" class="w-8 h-8 rounded-lg bg-white shadow-sm font-bold text-emerald-700 active:scale-95 transition">−</button>
        <span class="w-5 text-center font-bold text-sm">${qty}</span>
        <button data-inc="${id}" class="w-8 h-8 rounded-lg bg-emerald-600 text-white shadow-sm font-bold active:scale-95 transition">+</button>
      </div>`;
  }

  // ---------- cart ops ----------
  function addToCart(product, viaScanner = false) {
    const current = cart[product.id] || 0;
    if (current + 1 > product.stock) { toast(`Only ${product.stock} in stock`, true); return; }
    cart[product.id] = current + 1;
    saveCart(); renderProducts(); renderCart();
    toast(`${product.emoji} ${product.name} added`);
    if (viaScanner && navigator.vibrate) navigator.vibrate(60);
  }

  function changeQty(id, delta) {
    const product = productById(id);
    const next = (cart[id] || 0) + delta;
    if (product && next > product.stock) { toast(`Only ${product.stock} in stock`, true); return; }
    if (next <= 0) delete cart[id]; else cart[id] = next;
    saveCart(); renderProducts(); renderCart();
  }

  function cartTotals() {
    let subtotal = 0, gst = 0, total = 0, count = 0;
    for (const [id, qty] of Object.entries(cart)) {
      const p = productById(id);
      if (!p) continue;
      const line = p.price * qty;
      const taxable = line / (1 + p.gst_percent / 100);
      subtotal += taxable; gst += line - taxable; total += line; count += qty;
    }
    return { subtotal, gst, total, count };
  }

  function renderCart() {
    const { subtotal, gst, total, count } = cartTotals();
    $('cart-bar').classList.toggle('hidden', count === 0);
    $('cart-count').textContent = count;
    $('cart-total').textContent = rupees(total);
    $('sum-subtotal').textContent = rupees(subtotal);
    $('sum-gst').textContent = rupees(gst);
    $('sum-total').textContent = rupees(total);

    const box = $('cart-items');
    const entries = Object.entries(cart).filter(([id]) => productById(id));
    if (!entries.length) {
      box.innerHTML = '<p class="text-center text-sm text-gray-400 py-8">Your cart is empty</p>';
      closeCart();
      return;
    }
    box.innerHTML = entries.map(([id, qty]) => {
      const p = productById(id);
      return `
      <div class="flex items-center gap-3">
        <div class="w-11 h-11 bg-emerald-50 rounded-xl flex items-center justify-center text-xl shrink-0">${p.emoji}</div>
        <div class="flex-1 min-w-0">
          <p class="font-semibold text-sm leading-tight truncate">${p.name}</p>
          <p class="text-xs text-gray-400">${rupees(p.price)} × ${qty} = <span class="font-semibold text-gray-600">${rupees(p.price * qty)}</span></p>
        </div>
        ${stepper(p.id, qty)}
      </div>`;
    }).join('');
  }

  // ---------- scanner ----------
  const SCAN_CONFIG = {
    fps: 10,
    // size the scan box to the video so small laptop previews don't error out
    qrbox: (vw, vh) => ({ width: Math.min(260, Math.floor(vw * 0.8)), height: Math.min(160, Math.floor(vh * 0.6)) }),
    videoConstraints: { width: { ideal: 1280 }, height: { ideal: 720 } },
  };

  function cameraErrorMessage(err) {
    if (!navigator.mediaDevices) return 'Camera needs HTTPS or localhost — type the barcode instead';
    const name = err && err.name;
    if (name === 'NotAllowedError') return 'Camera permission denied — allow it in browser settings';
    if (name === 'NotFoundError') return 'No camera found — type the barcode instead';
    if (name === 'NotReadableError') return 'Camera is in use by another app';
    return 'Camera unavailable — type the barcode or use Browse';
  }

  let cameras = [];
  let camIndex = -1; // -1 = started via facingMode, not a specific device

  function backCameraIndex(cams) {
    return cams.findIndex(c => /back|rear|environment/i.test(c.label || ''));
  }

  async function startWith(source) {
    await scanner.start(source, SCAN_CONFIG, onScan, () => {});
  }

  async function openScanner() {
    $('scanner-overlay').classList.remove('hidden');
    $('scanner-overlay').classList.add('flex');
    scanner = new Html5Qrcode('reader');
    try { cameras = (await Html5Qrcode.getCameras()) || []; } catch { cameras = []; }
    $('switch-camera').classList.toggle('hidden', cameras.length < 2);
    try {
      const back = backCameraIndex(cameras);
      if (back >= 0) {
        // a camera is explicitly labelled back/rear — use it
        camIndex = back;
        await startWith(cameras[camIndex].id);
      } else {
        // labels don't identify the back camera — let the browser pick it
        camIndex = -1;
        await startWith({ facingMode: 'environment' });
      }
    } catch (err) {
      // last resort: any camera at all (laptops, permission quirks)
      try {
        if (cameras.length) { camIndex = 0; await startWith(cameras[0].id); }
        else { camIndex = -1; await startWith({ facingMode: 'user' }); }
      } catch (err2) {
        closeScanner();
        toast(cameraErrorMessage(err2), true);
      }
    }
  }

  async function switchCamera() {
    if (!scanner || cameras.length < 2) return;
    camIndex = (camIndex + 1) % cameras.length;
    try { await scanner.stop(); } catch {}
    try {
      await startWith(cameras[camIndex].id);
      const label = cameras[camIndex].label || `Camera ${camIndex + 1}`;
      toast(`📷 ${label}`);
    } catch {
      toast('Could not switch camera', true);
    }
  }

  async function closeScanner() {
    $('scanner-overlay').classList.add('hidden');
    $('scanner-overlay').classList.remove('flex');
    if (scanner) { try { await scanner.stop(); scanner.clear(); } catch {} scanner = null; }
  }

  async function lookupAndAdd(code, viaScanner = false) {
    const local = products.find(p => p.barcode === code);
    if (local) { addToCart(local, viaScanner); return true; }
    // not in cached catalog — check server (product may be newly added)
    try {
      const res = await fetch(`/api/outlets/${outletId}/products/by-barcode/${encodeURIComponent(code)}`);
      if (res.ok) {
        const p = await res.json();
        products.push(p);
        addToCart(p, viaScanner);
        return true;
      }
      toast('Product not found in this store', true);
      return false;
    } catch { toast('Network error — try again', true); return false; }
  }

  async function onScan(code) {
    const now = Date.now();
    if (code === lastScan.code && now - lastScan.at < 2500) return; // debounce repeats
    lastScan = { code, at: now };
    await lookupAndAdd(code, true);
  }

  // ---------- manual barcode entry ----------
  async function manualAdd(inputId) {
    const input = $(inputId);
    const code = input.value.trim();
    if (!code) return;
    if (await lookupAndAdd(code)) input.value = '';
    input.focus();
  }

  // ---------- checkout ----------
  async function checkout() {
    const items = Object.entries(cart).map(([product_id, qty]) => ({ product_id: Number(product_id), qty }));
    if (!items.length) return;
    const btn = $('checkout-btn');
    btn.disabled = true; btn.textContent = 'Processing…';
    try {
      const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outlet_id: outletId, items }),
      });
      const data = await res.json();
      if (!res.ok) { toast(data.detail || 'Checkout failed', true); return; }
      if (data.mode === 'razorpay') openRazorpay(data);
      else window.location.href = `/pay/mock/${data.order_id}`;
    } catch {
      toast('Network error — try again', true);
    } finally {
      btn.disabled = false; btn.textContent = 'Pay & checkout';
    }
  }

  function openRazorpay(data) {
    const rzp = new Razorpay({
      key: data.key_id,
      amount: data.amount_paise,
      currency: 'INR',
      name: 'ScanKart',
      description: data.outlet_name,
      order_id: data.razorpay_order_id,
      theme: { color: '#059669' },
      handler: async (resp) => {
        const res = await fetch('/api/payment/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            order_id: data.order_id,
            razorpay_order_id: resp.razorpay_order_id,
            razorpay_payment_id: resp.razorpay_payment_id,
            razorpay_signature: resp.razorpay_signature,
          }),
        });
        const result = await res.json();
        if (res.ok) {
          localStorage.removeItem(CART_KEY);
          window.location.href = result.bill_url;
        } else {
          toast('Payment verification failed', true);
        }
      },
    });
    rzp.on('payment.failed', () => toast('Payment failed — try again', true));
    rzp.open();
  }

  // ---------- ui helpers ----------
  let toastTimer = null;
  function toast(msg, error = false) {
    const el = $('toast-inner');
    el.textContent = msg;
    el.classList.toggle('bg-red-600', error);
    el.classList.toggle('bg-gray-900', !error);
    el.classList.remove('opacity-0');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('opacity-0'), 1800);
  }

  function openCart() {
    renderCart();
    $('cart-sheet-backdrop').classList.remove('hidden');
    requestAnimationFrame(() => $('cart-sheet').classList.remove('translate-y-full'));
  }
  function closeCart() {
    $('cart-sheet').classList.add('translate-y-full');
    $('cart-sheet-backdrop').classList.add('hidden');
  }

  // ---------- events ----------
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-add],[data-inc],[data-dec]');
    if (!t) return;
    if (t.dataset.add) addToCart(productById(t.dataset.add));
    if (t.dataset.inc) changeQty(t.dataset.inc, +1);
    if (t.dataset.dec) changeQty(t.dataset.dec, -1);
  });
  $('search').addEventListener('input', renderProducts);
  $('toggle-manual').addEventListener('click', () => {
    $('manual-entry').classList.toggle('hidden');
    if (!$('manual-entry').classList.contains('hidden')) $('manual-barcode').focus();
  });
  $('manual-add').addEventListener('click', () => manualAdd('manual-barcode'));
  $('manual-barcode').addEventListener('keydown', (e) => { if (e.key === 'Enter') manualAdd('manual-barcode'); });
  $('overlay-add').addEventListener('click', () => manualAdd('overlay-barcode'));
  $('overlay-barcode').addEventListener('keydown', (e) => { if (e.key === 'Enter') manualAdd('overlay-barcode'); });
  $('open-scanner').addEventListener('click', openScanner);
  $('close-scanner').addEventListener('click', closeScanner);
  $('switch-camera').addEventListener('click', switchCamera);
  $('open-cart').addEventListener('click', openCart);
  $('close-cart').addEventListener('click', closeCart);
  $('cart-sheet-backdrop').addEventListener('click', closeCart);
  $('checkout-btn').addEventListener('click', checkout);

  loadProducts();
})();
