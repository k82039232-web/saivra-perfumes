from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import sqlite3
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'saivra_secret_key_2024_secure')

DATABASE = 'saivra.db'

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'saivra2024')

SITE_URL = 'https://saivra-perfumes.up.railway.app'

# ─────────────────────────────────────────
#  DATABASE HELPERS
# ─────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        description TEXT,
        price       REAL    NOT NULL,
        image_url   TEXT,
        category    TEXT    DEFAULT 'عطر',
        stock       INTEGER DEFAULT 0,
        active      INTEGER DEFAULT 1,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS orders (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name    TEXT  NOT NULL,
        customer_email   TEXT,
        customer_phone   TEXT,
        customer_address TEXT,
        items            TEXT  NOT NULL,
        total            REAL  NOT NULL,
        status           TEXT  DEFAULT 'pending',
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# ─────────────────────────────────────────
#  AUTH DECORATOR
# ─────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────
#  CONTEXT PROCESSOR – cart count in nav
# ─────────────────────────────────────────

@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    count = sum(cart.values())
    return dict(cart_count=count)

# ─────────────────────────────────────────
#  PUBLIC ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    conn = get_db()
    products = conn.execute(
        'SELECT * FROM products WHERE active=1 ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('index.html', products=products)


@app.route('/product/<int:product_id>')
def product(product_id):
    conn = get_db()
    prod = conn.execute(
        'SELECT * FROM products WHERE id=? AND active=1', (product_id,)
    ).fetchone()
    related = []
    if prod:
        related = conn.execute(
            'SELECT * FROM products WHERE active=1 AND id!=? AND category=? LIMIT 4',
            (product_id, prod['category'])
        ).fetchall()
    conn.close()
    if not prod:
        return redirect(url_for('index'))
    return render_template('product.html', product=prod, related=related)


@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items, total = [], 0
    if cart:
        conn = get_db()
        for pid, qty in cart.items():
            p = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
            if p:
                subtotal = p['price'] * qty
                cart_items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
                total += subtotal
        conn.close()
    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    cart = session.get('cart', {})
    qty  = int(request.form.get('qty', 1))
    cart[str(product_id)] = cart.get(str(product_id), 0) + qty
    session['cart'] = cart
    flash('تمت الإضافة إلى السلة ✓', 'success')
    return redirect(url_for('cart'))


@app.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    cart = session.get('cart', {})
    qty  = int(request.form.get('qty', 1))
    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = qty
    session['cart'] = cart
    return redirect(url_for('cart'))


@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('cart'))

    cart_items, total = [], 0
    conn = get_db()
    for pid, qty in cart.items():
        p = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if p:
            subtotal = p['price'] * qty
            cart_items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
            total += subtotal

    if request.method == 'POST':
        name       = request.form.get('name')
        email      = request.form.get('email', '')
        phone      = request.form.get('phone')
        address    = request.form.get('address')
        items_json = json.dumps([{'id': k, 'qty': v} for k, v in cart.items()])
        conn.execute(
            'INSERT INTO orders (customer_name,customer_email,customer_phone,customer_address,items,total) VALUES (?,?,?,?,?,?)',
            (name, email, phone, address, items_json, total)
        )
        conn.commit()
        conn.close()
        session['cart'] = {}
        flash('تم استلام طلبك بنجاح! سنتواصل معك قريباً ✓', 'success')
        return redirect(url_for('success'))

    conn.close()
    return render_template('checkout.html', cart_items=cart_items, total=total)


@app.route('/success')
def success():
    return render_template('success.html')


# ─────────────────────────────────────────
#  SITEMAP & SEO
# ─────────────────────────────────────────

@app.route('/sitemap.xml')
def sitemap():
    conn = get_db()
    products = conn.execute(
        'SELECT id FROM products WHERE active=1'
    ).fetchall()
    conn.close()

    urls = [
        f'<url><loc>{SITE_URL}/</loc><priority>1.0</priority></url>',
        f'<url><loc>{SITE_URL}/cart</loc><priority>0.5</priority></url>',
    ]
    for p in products:
        urls.append(
            f'<url><loc>{SITE_URL}/product/{p["id"]}</loc><priority>0.8</priority></url>'
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '\n'.join(urls)
    xml += '\n</urlset>'

    return Response(xml, mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    content = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml"
    return Response(content, mimetype='text/plain')


# ─────────────────────────────────────────
#  ADMIN ROUTES
# ─────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    orders   = conn.execute('SELECT * FROM orders   ORDER BY created_at DESC').fetchall()
    stats = {
        'total_products':  len(products),
        'active_products': sum(1 for p in products if p['active']),
        'total_orders':    len(orders),
        'pending_orders':  sum(1 for o in orders if o['status'] == 'pending'),
        'revenue':         sum(o['total'] for o in orders if o['status'] != 'cancelled'),
    }
    conn.close()
    return render_template('admin.html', products=products, orders=orders, stats=stats)


@app.route('/admin/add_product', methods=['POST'])
@admin_required
def add_product():
    conn = get_db()
    conn.execute(
        'INSERT INTO products (name,description,price,image_url,category,stock) VALUES (?,?,?,?,?,?)',
        (
            request.form.get('name'),
            request.form.get('description'),
            float(request.form.get('price', 0)),
            request.form.get('image_url', ''),
            request.form.get('category', 'عطر'),
            int(request.form.get('stock', 0)),
        )
    )
    conn.commit()
    conn.close()
    flash('تمت إضافة المنتج بنجاح ✓', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/edit_product/<int:pid>', methods=['POST'])
@admin_required
def edit_product(pid):
    active = 1 if request.form.get('active') else 0
    conn = get_db()
    conn.execute(
        'UPDATE products SET name=?,description=?,price=?,image_url=?,category=?,stock=?,active=? WHERE id=?',
        (
            request.form.get('name'),
            request.form.get('description'),
            float(request.form.get('price', 0)),
            request.form.get('image_url', ''),
            request.form.get('category', 'عطر'),
            int(request.form.get('stock', 0)),
            active,
            pid,
        )
    )
    conn.commit()
    conn.close()
    flash('تم تحديث المنتج ✓', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/toggle_product/<int:pid>')
@admin_required
def toggle_product(pid):
    conn = get_db()
    p = conn.execute('SELECT active FROM products WHERE id=?', (pid,)).fetchone()
    conn.execute('UPDATE products SET active=? WHERE id=?', (0 if p['active'] else 1, pid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))


@app.route('/admin/delete_product/<int:pid>')
@admin_required
def delete_product(pid):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id=?', (pid,))
    conn.commit()
    conn.close()
    flash('تم حذف المنتج', 'info')
    return redirect(url_for('admin'))


@app.route('/admin/update_order/<int:oid>', methods=['POST'])
@admin_required
def update_order(oid):
    status = request.form.get('status')
    conn = get_db()
    conn.execute('UPDATE orders SET status=? WHERE id=?', (status, oid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))


@app.route('/admin/delete_order/<int:oid>')
@admin_required
def delete_order(oid):
    conn = get_db()
    conn.execute('DELETE FROM orders WHERE id=?', (oid,))
    conn.commit()
    conn.close()
    flash('تم حذف الطلب بنجاح', 'success')
    return redirect(url_for('admin'))


# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)