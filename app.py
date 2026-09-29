import os
from flask import Flask, render_template, request, redirect, flash, session, Response, url_for, jsonify
import sqlite3
import pandas as pd
import pickle
from sklearn.linear_model import LinearRegression

import webview
import threading
import sys

from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

# Configure your API key (You will need to paste your actual key here)
from groq import Groq
import json

# Replace with your actual Groq API key
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

model = LinearRegression()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_database.db')
MODEL_PATH = os.path.join(BASE_DIR, 'model.pkl')
demand_model = None
try:
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, 'rb') as f:
            demand_model = pickle.load(f)
except Exception as e:
    print(f"⚠️ Could not load ML model due to version mismatch: {e}")
    demand_model = None

app = Flask(__name__)
# A secret key is required to use flash messages securely
app.secret_key = "super_secret_erp_key" 

# --- MASTER DATABASE INITIALIZATION ---
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# 1. Products Table

cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    )
''')

# 2. Orders Table
# Update the orders table in app.py
# 2. Orders Table (Parent)
# 2. Orders Table (Parent)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer TEXT NOT NULL,
        total REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 3. Order Items Table (Child)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id)
    )
''')

# 3. Purchases Table (Expenses)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        total_cost REAL
    )
''')

# 4. Employees Table (HR/Auth)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
''')

# 5. Suppliers Table (Vendor Management)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT,
        email TEXT
    )
''')

# 6. Repairs
cursor.execute('''
    CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        client_contact TEXT NOT NULL,
        device TEXT NOT NULL,
        issue TEXT NOT NULL,
        estimated_cost REAL,
        priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 7. P2P — Purchase Requisitions
cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchase_requisitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        required_date TEXT,
        department TEXT,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 8. P2P — RFQ
cursor.execute('''
    CREATE TABLE IF NOT EXISTS rfqs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pr_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        quoted_price REAL,
        delivery_days INTEGER,
        notes TEXT,
        status TEXT DEFAULT 'sent',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pr_id) REFERENCES purchase_requisitions(id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
    )
''')

# 9. P2P — Purchase Orders
cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rfq_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_value REAL NOT NULL,
        delivery_date TEXT,
        status TEXT DEFAULT 'ordered',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
    )
''')

# 10. P2P — GRN
cursor.execute('''
    CREATE TABLE IF NOT EXISTS grns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        received_qty INTEGER NOT NULL,
        received_date TEXT,
        condition TEXT DEFAULT 'good',
        product_name TEXT,
        remarks TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
    )
''')

# 11. P2P — Vendor Invoices
cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendor_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        invoice_number TEXT NOT NULL,
        amount REAL NOT NULL,
        invoice_date TEXT,
        due_date TEXT,
        notes TEXT,
        status TEXT DEFAULT 'invoiced',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
    )
''')

# 12. Finance — General Ledger (GL)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS general_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT NOT NULL,
        account_type TEXT NOT NULL, -- Asset, Liability, Equity, Revenue, Expense
        balance REAL DEFAULT 0.0
    )
''')

# 13. Finance — Sub-Ledgers (AR / AP)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sub_ledgers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_name TEXT NOT NULL, -- Customer or Supplier Name
        amount REAL NOT NULL,
        ledger_type TEXT NOT NULL, -- 'AR' (Receivable) or 'AP' (Payable)
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 14. Billing — Memos
cursor.execute('''
    CREATE TABLE IF NOT EXISTS billing_memos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memo_type TEXT NOT NULL, -- 'Credit', 'Debit', or 'Cancellation'
        customer TEXT NOT NULL,
        amount REAL NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 14. O2C — Outbound Deliveries
cursor.execute('''
    CREATE TABLE IF NOT EXISTS outbound_deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        delivery_date TEXT,
        carrier TEXT,
        tracking_number TEXT,
        status TEXT DEFAULT 'dispatched',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
''')

# 15. O2C — Customer Billing (Accounts Receivable)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS customer_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        invoice_number TEXT NOT NULL,
        amount REAL NOT NULL,
        due_date TEXT,
        status TEXT DEFAULT 'unpaid',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
''')

# 16. O2C — Customer Special Requests (Back-to-Back)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS customer_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer TEXT NOT NULL,
        requested_item TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        status TEXT DEFAULT 'pending_sourcing',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Auto-inject default users if they don't exist
cursor.execute("SELECT COUNT(*) FROM employees")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO employees (username, password, role) VALUES ('admin', 'password123', 'Manager')")
    cursor.execute("INSERT INTO employees (username, password, role) VALUES ('worker', 'worker123', 'Warehouse')")

conn.commit()
conn.close()
# --------------------------------------

def get_inventory():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    items = cursor.fetchall()
    conn.close()
    return items

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM employees WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['username'] = username
            session['role'] = user[0]
            return redirect('/')
        else:
            flash("Error: Invalid username or password", "error")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect('/login')


@app.route('/')
def index():
    if 'username' not in session:
        return redirect('/login')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Fetch name, stock, AND price from the products table
    cursor.execute("SELECT name, stock, price FROM products")
    inventory_data = cursor.fetchall()
    conn.close()
    
    # Separate the data into lists for Jinja and Chart.js 
    labels = [item[0] for item in inventory_data]
    data = [item[1] for item in inventory_data]
    prices = [item[2] for item in inventory_data] # Extract the prices
    
    # Pass the prices list to index.html
    return render_template('index.html', labels=labels, data=data, prices=prices)

@app.route('/add_item', methods=['POST'])
def add_item():
    # Grab all three fields from the form
    item_name = request.form['name']
    item_stock = request.form['stock'] 
    item_price = request.form['price']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update the query to include the price column
    cursor.execute("INSERT INTO products (name, stock, price) VALUES (?, ?, ?)", (item_name, item_stock, item_price))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/delete_item/<item_name>', methods=['POST'])
def delete_item(item_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Delete the specific product from the database
    cursor.execute("DELETE FROM products WHERE name = ?", (item_name,))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/add', methods=['POST'])
def add():
    # Security check: must be logged in
    if 'username' not in session:
        return redirect('/login')
        
    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock))
    conn.commit()
    conn.close()
    
    flash(f"Success: {name} added to inventory!", "success")
    return redirect('/')





@app.route('/delete/<int:id>')
def delete(id):
    if 'username' not in session or session.get('role') != 'Manager':
        flash("Error: Security Alert. Only Managers can delete products.", "error")
        return redirect('/')
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    flash("System: Product deleted successfully.", "success")
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'username' not in session or session.get('role') != 'Manager':
        flash("Error: Security Alert. Only Managers can edit products.", "error")
        return redirect('/')
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        
        # Update the specific product in the database
        cursor.execute("UPDATE products SET name = ?, price = ? WHERE id = ?", (name, price, id))
        conn.commit()
        conn.close()
        flash("System: Product updated successfully.", "success")
        return redirect('/')
    else:
        # Fetch the current details to pre-fill the form
        cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
        product = cursor.fetchone()
        conn.close()
        return render_template('edit.html', product=product)
    
@app.route('/export')
def export():
    # Security check
    if 'username' not in session:
        return redirect('/login')
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products")
    items = cursor.fetchall()
    conn.close()
    
    # Build the CSV data structure in memory
    csv_data = "ID,Product Name,Price,Stock\n"
    for item in items:
        csv_data += f"{item[0]},{item[1]},{item[2]},{item[3]}\n"
        
    # Send the file to the user's browser as a download
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventory_report.csv"}
    )

@app.route('/finance')
def finance():
    if 'username' not in session:
        return redirect('/login')
    if session.get('role') != 'Manager':
        flash("Security Alert: Access Denied. Only Managers can view financial data.", "error")
        return redirect('/')
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Revenue & Expenses
    cursor.execute("SELECT SUM(total) FROM orders WHERE status != 'cancelled'")
    total_revenue = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(total_cost) FROM purchases")
    total_expenses = cursor.fetchone()[0] or 0.0
    
    # Subtract Credit Memos (Refunds) from Revenue
    cursor.execute("SELECT SUM(amount) FROM billing_memos WHERE memo_type = 'Credit'")
    total_refunds = cursor.fetchone()[0] or 0.0
    
    # Define net_revenue here so it doesn't throw a NameError!
    net_revenue = total_revenue - total_refunds
    net_profit = net_revenue - total_expenses

    # 2. Balance Sheet Calculations (Assets = Liabilities + Equity)
    cursor.execute("SELECT SUM(stock * price) FROM products")
    inventory_value = cursor.fetchone()[0] or 0.0
    total_assets = net_profit + inventory_value
    
    cursor.execute("SELECT SUM(amount) FROM vendor_invoices WHERE status != 'paid'")
    total_liabilities = cursor.fetchone()[0] or 0.0
    
    total_equity = total_assets - total_liabilities

    # 3. Fetch Billing Memos for the UI
    cursor.execute("SELECT * FROM billing_memos ORDER BY id DESC")
    memos = [dict(row) for row in cursor.fetchall()]
    
    # 4. Fetch Sales Ledger for Chart
    cursor.execute('''
        SELECT p.name, SUM(oi.quantity * p.price) as revenue
        FROM order_items oi
        JOIN products p ON oi.product_name = p.name
        GROUP BY p.name
    ''')
    chart_data = cursor.fetchall()
    labels = [row['name'] for row in chart_data]
    data = [row['revenue'] for row in chart_data]

    conn.close()
    
    return render_template('finance.html', 
                           total_revenue=net_revenue, total_expenses=total_expenses, 
                           net_profit=net_profit, assets=total_assets, 
                           liabilities=total_liabilities, equity=total_equity,
                           inventory_value=inventory_value, memos=memos,
                           chart_labels=labels, chart_data=data)

@app.route('/finance/add_memo', methods=['POST'])
def finance_add_memo():
    if 'username' not in session: 
        return redirect('/login')
    
    memo_type = request.form['memo_type']
    customer = request.form['customer'] # Capturing customer from HTML
    amount = float(request.form['amount'])
    reason = request.form['reason']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert using the customer name
    cursor.execute(
        "INSERT INTO billing_memos (memo_type, customer, amount, reason) VALUES (?, ?, ?, ?)",
        (memo_type, customer, amount, reason)
    )
    conn.commit()
    conn.close()
    
    flash(f"Success: {memo_type} Memo for ${amount} generated.", "success")
    return redirect(url_for('finance'))

@app.route('/restock', methods=['POST'])
def restock():
    product_id = int(request.form['product_id'])
    restock_qty = int(request.form['quantity'])
    cost = float(request.form['cost']) # New: Get the cost of the shipment
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, stock FROM products WHERE id = ?", (product_id,))
    result = cursor.fetchone()
    
    if not result:
        flash("Error: Product ID does not exist!", "error")
    else:
        name, current_stock = result
        new_stock = current_stock + restock_qty
        
        # Update stock and log the purchase expense
        cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
        cursor.execute("INSERT INTO purchases (product_id, quantity, total_cost) VALUES (?, ?, ?)", (product_id, restock_qty, cost))
        conn.commit()
        
        flash(f"Success: Restocked {restock_qty}x {name} for ${cost}. Total stock is {new_stock}.", "success")
        
    conn.close()
    return redirect('/')



@app.route('/api/inventory', methods=['GET'])
def api_inventory():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch all products from the database
    cursor.execute("SELECT name, stock, price FROM products")
    items = cursor.fetchall()
    conn.close()
    
    # Convert the SQLite rows into a structured list of dictionaries
    inventory_list = []
    for item in items:
        inventory_list.append({
            "name": item[0],
            "stock": item[1],
            "price": item[2]
        })
        
    # Transmit the data as pure JSON
    return jsonify({
        "status": "success",
        "total_items": len(inventory_list),
        "data": inventory_list
    })

@app.route('/update_item/<item_name>', methods=['POST'])
def update_item(item_name):
    # Grab the new stock quantity from the form
    new_stock = request.form['new_stock']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update the specific product in the database
    cursor.execute("UPDATE products SET stock = ? WHERE name = ?", (new_stock, item_name))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))
# 1. Load the Suppliers Page
@app.route('/suppliers', methods=['GET', 'POST'])
def suppliers():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Handle adding a new supplier via form submission
    if request.method == 'POST':
        name = request.form.get('name')
        contact = request.form.get('contact')
        email = request.form.get('email')
        
        if name and contact:
            cursor.execute(
                "INSERT INTO suppliers (name, contact, email) VALUES (?, ?, ?)",
                (name, contact, email)
            )
            conn.commit()
        return redirect(url_for('suppliers'))
    
    # Fetch all suppliers to display in the template
    cursor.execute("SELECT id, name, contact, email FROM suppliers")
    suppliers_data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('suppliers.html', suppliers=suppliers_data)
# 2. Add a New Supplier
@app.route('/add_supplier', methods=['POST'])
def add_supplier():
    name = request.form['name']
    contact = request.form['contact']
    email = request.form['email']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO suppliers (name, contact, email) VALUES (?, ?, ?)", (name, contact, email))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('suppliers'))


# 3. Delete a Supplier
@app.route('/delete_supplier/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Delete based on the unique ID
    cursor.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('suppliers'))

@app.route('/search')
def search():
    # Grab the search term from the URL (?q=...)
    search_query = request.args.get('q', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Query the database for matching item names, ignoring case
    # Fetch name, stock AND price so index.html doesn't crash on {{ prices[i] }}
    cursor.execute("SELECT name, stock, price FROM products WHERE name LIKE ?", ('%' + search_query + '%',))
    search_results = cursor.fetchall()
    conn.close()

    labels = [item[0] for item in search_results]
    data   = [item[1] for item in search_results]
    prices = [item[2] for item in search_results]

    return render_template('index.html', labels=labels, data=data, prices=prices)

@app.route('/settings')
def settings():
    return render_template('settings.html')

# 1. Load the Orders Page & Handle Filtering
# ══════════════════════════════════════════════════════════════
# O2C MODULE — Order to Cash
# ══════════════════════════════════════════════════════════════

@app.route('/orders')
def orders():
    if 'username' not in session:
        return redirect('/login')
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Fetch Sales Orders (with items concatenated)
    cursor.execute('''
        SELECT o.id, o.customer, o.total, o.status, o.created_at,
        GROUP_CONCAT(oi.product_name || ' (x' || oi.quantity || ')', ', ') AS item_list
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        GROUP BY o.id
        ORDER BY o.id DESC
    ''')
    sales_orders = [dict(row) for row in cursor.fetchall()]

    # 2. Fetch Outbound Deliveries
    cursor.execute("SELECT * FROM outbound_deliveries ORDER BY id DESC")
    deliveries = [dict(row) for row in cursor.fetchall()]

    # 3. Fetch Customer Invoices (AR)
    cursor.execute("SELECT * FROM customer_invoices ORDER BY id DESC")
    invoices = [dict(row) for row in cursor.fetchall()]

    # 4. Fetch Products for the SO creation form
    cursor.execute("SELECT name, stock FROM products")
    available_products = cursor.fetchall()

    cursor.execute("SELECT * FROM customer_requests ORDER BY id DESC")
    special_requests = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return render_template('orders.html', 
                           sales_orders=sales_orders, 
                           deliveries=deliveries, 
                           invoices=invoices, 
                           available_products=available_products,
                           special_requests=special_requests)

@app.route('/o2c/delivery/add', methods=['POST'])
def o2c_delivery_add():
    if 'username' not in session: return redirect('/login')
    
    order_id = request.form['order_id']
    delivery_date = request.form['delivery_date']
    carrier = request.form.get('carrier', 'In-House')
    tracking = request.form.get('tracking_number', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Log the delivery
    cursor.execute(
        "INSERT INTO outbound_deliveries (order_id, delivery_date, carrier, tracking_number) VALUES (?, ?, ?, ?)",
        (order_id, delivery_date, carrier, tracking)
    )
    
    # CRITICAL: Deduct inventory stock here during fulfillment!
    cursor.execute("SELECT product_name, quantity FROM order_items WHERE order_id = ?", (order_id,))
    items = cursor.fetchall()
    for item in items:
        cursor.execute("UPDATE products SET stock = stock - ? WHERE name = ?", (item[1], item[0]))
        
    # Update SO status
    cursor.execute("UPDATE orders SET status = 'shipped' WHERE id = ?", (order_id,))
    
    conn.commit()
    conn.close()
    flash("Delivery dispatched and inventory stock deducted.", "success")
    return redirect(url_for('orders') + '#delivery')

@app.route('/o2c/invoice/add', methods=['POST'])
def o2c_invoice_add():
    if 'username' not in session: return redirect('/login')
    
    order_id = request.form['order_id']
    invoice_num = request.form['invoice_number']
    amount = float(request.form['amount'])
    due_date = request.form.get('due_date', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO customer_invoices (order_id, invoice_number, amount, due_date) VALUES (?, ?, ?, ?)",
        (order_id, invoice_num, amount, due_date)
    )
    cursor.execute("UPDATE orders SET status = 'invoiced' WHERE id = ?", (order_id,))
    
    conn.commit()
    conn.close()
    flash(f"AR Invoice {invoice_num} generated.", "success")
    return redirect(url_for('orders') + '#invoice')

@app.route('/o2c/invoice/pay/<int:id>', methods=['POST'])
def o2c_invoice_pay(id):
    if 'username' not in session: return redirect('/login')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE customer_invoices SET status = 'paid' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    flash("Payment received successfully.", "success")
    return redirect(url_for('orders') + '#invoice')

# 2. Update Order Status
@app.route('/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    new_status = request.form['new_status']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('orders'))


# 3. Delete an Order
@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('orders'))

@app.route('/seed_orders')
def seed_orders():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Insert parent order rows (no 'items' column in the new schema)
    cursor.execute("INSERT INTO orders (customer, total, status) VALUES ('Tech Corp', 12500.00, 'pending')")
    order1_id = cursor.lastrowid
    cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, 'Laptop', 10)", (order1_id,))

    cursor.execute("INSERT INTO orders (customer, total, status) VALUES ('Global Industries', 4500.50, 'shipped')")
    order2_id = cursor.lastrowid
    cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, 'Server Rack', 2)", (order2_id,))

    conn.commit()
    conn.close()
    return redirect(url_for('orders'))


@app.route('/add_order', methods=['POST'])
def add_order():
    customer = request.form['customer']
    product_name = request.form['product_name']  
    quantity = int(request.form['quantity'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT price FROM products WHERE name = ?", (product_name,))
    product = cursor.fetchone()
    
    if product:
        unit_price = product[0]
        total = unit_price * quantity
        
        # Step A: Insert the parent Sales Order transaction
        cursor.execute("INSERT INTO orders (customer, total, status) VALUES (?, ?, 'pending')", 
                       (customer, total))
        order_id = cursor.lastrowid 
        
        # Step B: Insert the child item linked to the Order ID
        cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)",
                       (order_id, product_name, quantity))
                       
        # NOTE: Stock deduction has been removed from here. 
        # It will now occur during the Outbound Delivery step!
        
        conn.commit()
        
    conn.close()
    return redirect(url_for('orders'))

@app.route('/reset_db')
def reset_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Destroy the old tables
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS order_items")
    
    # 2. Build the new parent table (NO 'items' column!)
    cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. Build the new child table
    cursor.execute('''
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')
    
    # 4. FORCE the database to save these structural changes
    conn.commit()
    conn.close()
    
    return "Database reset successfully! You can now go back to the Orders page."

@app.route('/predict-demand/<float:price>')
def predict_demand(price):
    if not demand_model:
        return {"error": "Model not trained yet!"}
    
    # Predict expected sales volume for a given price
    predicted_units = demand_model.predict([[price]])[0]
    return {
        "price": price,
        "predicted_demand": round(float(predicted_units), 2)
    }

# ══════════════════════════════════════════════════════════════
# REPAIRS MODULE
# ══════════════════════════════════════════════════════════════

@app.route('/repairs')
def repairs():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM repairs ORDER BY id DESC")
    repairs_data = [dict(row) for row in cur.fetchall()]
    conn.close()

    return render_template('repairs.html', repairs=repairs_data)

@app.route('/repairs/add', methods=['POST'])
def repairs_add():
    if 'username' not in session:
        return redirect('/login')

    client_name = request.form['client_name']
    client_contact = request.form['client_contact']
    device = request.form['device']
    issue = request.form['issue']
    estimated_cost_raw = request.form.get('estimated_cost')
    priority = request.form.get('priority', 'medium')

    estimated_cost = float(estimated_cost_raw) if estimated_cost_raw not in (None, '') else None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO repairs (client_name, client_contact, device, issue, estimated_cost, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (client_name, client_contact, device, issue, estimated_cost, priority)
    )
    conn.commit()
    conn.close()

    flash("Repair job created successfully.", "success")
    return redirect(url_for('repairs'))

@app.route('/repairs/update/<int:id>', methods=['POST'])
def repairs_update(id):
    if 'username' not in session:
        return redirect('/login')

    new_status = request.form['new_status']
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE repairs SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()

    flash(f"Repair job #{id} updated.", "success")
    return redirect(url_for('repairs'))

@app.route('/repairs/delete/<int:id>', methods=['POST'])
def repairs_delete(id):
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM repairs WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash(f"Repair job #{id} deleted.", "success")
    return redirect(url_for('repairs'))

# ══════════════════════════════════════════════════════════════
# P2P MODULE — Procure to Pay
# ══════════════════════════════════════════════════════════════

def p2p_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/p2p')
def p2p():
    if 'username' not in session:
        return redirect('/login')
    conn = p2p_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM purchase_requisitions ORDER BY id DESC")
    prs = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT r.*, s.name as supplier_name
        FROM rfqs r LEFT JOIN suppliers s ON r.supplier_id = s.id
        ORDER BY r.id DESC
    """)
    rfqs = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM purchase_orders ORDER BY id DESC")
    pos = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM grns ORDER BY id DESC")
    grns = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM vendor_invoices ORDER BY id DESC")
    invoices = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT id, name, contact FROM suppliers ORDER BY name")
    suppliers = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT name, stock FROM products ORDER BY name")
    products = cur.fetchall()
    conn.close()
    return render_template('p2p.html',
        prs=prs, rfqs=rfqs, pos=pos, grns=grns,
        invoices=invoices, suppliers=suppliers, products=products)

# ── PR routes ──────────────────────────────────────────────────
@app.route('/p2p/pr/add', methods=['POST'])
def p2p_pr_add():
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO purchase_requisitions (item_name, quantity, required_date, department, reason) VALUES (?,?,?,?,?)",
        (request.form['item_name'], int(request.form['quantity']),
         request.form['required_date'], request.form['department'], request.form.get('reason',''))
    )
    conn.commit(); conn.close()
    flash(f"PR raised for {request.form['item_name']}.", "success")
    return redirect(url_for('p2p') + '#pr')

@app.route('/p2p/pr/update/<int:id>', methods=['POST'])
def p2p_pr_update(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db()
    cur = conn.cursor()
    cur.execute("UPDATE purchase_requisitions SET status=? WHERE id=?", (request.form['new_status'], id))
    conn.commit()
    conn.close()
    flash(f"PR-{id} updated.", "success")
    return redirect(url_for('p2p')) 

@app.route('/p2p/pr/delete/<int:id>', methods=['POST'])
def p2p_pr_delete(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("DELETE FROM purchase_requisitions WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash(f"PR-{id} deleted.", "success")
    return redirect(url_for('p2p'))

# ── RFQ routes ─────────────────────────────────────────────────
@app.route('/p2p/rfq/add', methods=['POST'])
def p2p_rfq_add():
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    qp = request.form.get('quoted_price') or None
    dd = request.form.get('delivery_days') or None
    cur.execute(
        "INSERT INTO rfqs (pr_id, supplier_id, quoted_price, delivery_days, notes) VALUES (?,?,?,?,?)",
        (int(request.form['pr_id']), int(request.form['supplier_id']),
         float(qp) if qp else None, int(dd) if dd else None, request.form.get('notes',''))
    )
    conn.commit(); conn.close()
    flash("RFQ sent to supplier.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/rfq/update/<int:id>', methods=['POST'])
def p2p_rfq_update(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("UPDATE rfqs SET status=? WHERE id=?", (request.form['new_status'], id))
    conn.commit(); conn.close()
    flash(f"RFQ-{id} updated.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/rfq/delete/<int:id>', methods=['POST'])
def p2p_rfq_delete(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("DELETE FROM rfqs WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash(f"RFQ-{id} deleted.", "success")
    return redirect(url_for('p2p'))

# ── PO routes ──────────────────────────────────────────────────
@app.route('/p2p/po/add', methods=['POST'])
def p2p_po_add():
    if 'username' not in session: return redirect('/login')
    qty   = int(request.form['quantity'])
    price = float(request.form['unit_price'])
    total = qty * price
    conn = p2p_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO purchase_orders (rfq_id, item_name, quantity, unit_price, total_value, delivery_date) VALUES (?,?,?,?,?,?)",
        (int(request.form['rfq_id']), request.form['item_name'], qty, price, total, request.form['delivery_date'])
    )
    conn.commit(); conn.close()
    flash(f"PO created — Total ₹{total:,.2f}.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/po/update/<int:id>', methods=['POST'])
def p2p_po_update(id):
    if 'username' not in session: return redirect('/login')
    
    new_status = request.form['new_status']
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Update the PO status
    cur.execute("UPDATE purchase_orders SET status=? WHERE id=?", (new_status, id))
    
    # 2. Trigger the Smart Inventory injection (CASE INSENSITIVE CHECK)
    if new_status.lower() == 'received':
        # Fetch the PO details to know what to add to inventory
        cur.execute("SELECT item_name, quantity, unit_price FROM purchase_orders WHERE id=?", (id,))
        po = cur.fetchone()
        
        if po:
            item_name, qty, purchase_cost = po[0], po[1], po[2]
            
            # Check if item exists in master inventory
            cur.execute("SELECT id FROM products WHERE name = ? COLLATE NOCASE", (item_name,))
            existing_product = cur.fetchone()
            
            if existing_product:
                # PATH A: It exists. Add received qty to existing stock.
                cur.execute("UPDATE products SET stock = stock + ? WHERE name = ? COLLATE NOCASE", (qty, item_name))
            else:
                # PATH B: Brand new item! Create it and apply a 20% markup for Retail Price.
                retail_price = purchase_cost * 1.20 
                cur.execute(
                    "INSERT INTO products (name, stock, price) VALUES (?, ?, ?)", 
                    (item_name, qty, retail_price)
                )
                
    conn.commit()
    conn.close()
    flash(f"PO-{id} updated to {new_status}.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/po/delete/<int:id>', methods=['POST'])
def p2p_po_delete(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("DELETE FROM purchase_orders WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash(f"PO-{id} deleted.", "success")
    return redirect(url_for('p2p'))

# ── GRN routes ─────────────────────────────────────────────────
@app.route('/p2p/grn/add', methods=['POST'])
def p2p_grn_add():
    if 'username' not in session: return redirect('/login')
    product = request.form.get('product_name') or None
    conn = p2p_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO grns (po_id, received_qty, received_date, condition, product_name, remarks) VALUES (?,?,?,?,?,?)",
        (int(request.form['po_id']), int(request.form['received_qty']),
         request.form['received_date'], request.form['condition'],
         product, request.form.get('remarks',''))
    )
    # Auto-update PO status to received
    cur.execute("UPDATE purchase_orders SET status='received' WHERE id=?", (int(request.form['po_id']),))
    # Auto-increase inventory stock if product linked
    if product:
        cur.execute("UPDATE products SET stock = stock + ? WHERE name = ?",
                    (int(request.form['received_qty']), product))
    conn.commit(); conn.close()
    msg = f"GRN recorded."
    if product:
        msg += f" Inventory updated for '{product}'."
    flash(msg, "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/grn/update/<int:id>', methods=['POST'])
def p2p_grn_update(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("UPDATE grns SET status=? WHERE id=?", (request.form['new_status'], id))
    conn.commit(); conn.close()
    flash(f"GRN-{id} updated.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/grn/delete/<int:id>', methods=['POST'])
def p2p_grn_delete(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("DELETE FROM grns WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash(f"GRN-{id} deleted.", "success")
    return redirect(url_for('p2p'))

# ── Invoice routes ─────────────────────────────────────────────
@app.route('/p2p/invoice/add', methods=['POST'])
def p2p_invoice_add():
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO vendor_invoices (po_id, invoice_number, amount, invoice_date, due_date, notes) VALUES (?,?,?,?,?,?)",
        (int(request.form['po_id']), request.form['invoice_number'],
         float(request.form['amount']), request.form['invoice_date'],
         request.form.get('due_date') or None, request.form.get('notes',''))
    )
    conn.commit(); conn.close()
    flash(f"Invoice {request.form['invoice_number']} recorded.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/invoice/update/<int:id>', methods=['POST'])
def p2p_invoice_update(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("UPDATE vendor_invoices SET status=? WHERE id=?", (request.form['new_status'], id))
    conn.commit(); conn.close()
    flash(f"Invoice #{id} marked as {request.form['new_status']}.", "success")
    return redirect(url_for('p2p'))

@app.route('/p2p/invoice/delete/<int:id>', methods=['POST'])
def p2p_invoice_delete(id):
    if 'username' not in session: return redirect('/login')
    conn = p2p_db(); cur = conn.cursor()
    cur.execute("DELETE FROM vendor_invoices WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash(f"Invoice #{id} deleted.", "success")
    return redirect(url_for('p2p'))

@app.route('/o2c/request/add', methods=['POST'])
def o2c_request_add():
    if 'username' not in session: return redirect('/login')
    
    customer = request.form['customer']
    requested_item = request.form['requested_item']
    quantity = int(request.form['quantity'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO customer_requests (customer, requested_item, quantity) VALUES (?, ?, ?)",
        (customer, requested_item, quantity)
    )
    conn.commit()
    conn.close()
    flash(f"Special request logged for {customer}.", "success")
    return redirect(url_for('orders') + '#request')

@app.route('/o2c/request/convert', methods=['POST'])
def o2c_request_convert():
    if 'username' not in session: return redirect('/login')
    
    request_id = request.form['request_id']
    actual_product = request.form['actual_product']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Get original request details
    cursor.execute("SELECT customer, quantity FROM customer_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()
    
    # 2. Get current inventory price for the sourced item
    cursor.execute("SELECT price FROM products WHERE name = ?", (actual_product,))
    prod = cursor.fetchone()
    
    if req and prod:
        customer, quantity = req
        unit_price = prod[0]
        total = unit_price * quantity
        
        # 3. Create the Sales Order
        cursor.execute("INSERT INTO orders (customer, total, status) VALUES (?, ?, 'pending')", (customer, total))
        order_id = cursor.lastrowid
        cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)", (order_id, actual_product, quantity))
        
        # 4. Mark request as converted
        cursor.execute("UPDATE customer_requests SET status = 'converted' WHERE id = ?", (request_id,))
        conn.commit()
        flash("Request successfully converted to a Sales Order!", "success")
    else:
        flash("Error finding product or request.", "error")
        
    conn.close()
    return redirect(url_for('orders') + '#so')

@app.route('/order/smart_route', methods=['POST'])
def smart_route_order():
    if 'username' not in session: return redirect('/login')
    
    customer = request.form['customer']
    item_name = request.form['item_name'].strip()
    quantity = int(request.form['quantity'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check if the exact item exists in the master inventory
    # Using COLLATE NOCASE so "laptop" matches "Laptop"
    cursor.execute("SELECT price FROM products WHERE name = ? COLLATE NOCASE", (item_name,))
    product = cursor.fetchone()
    
    if product:
        # PATH A: It exists! Create a standard Sales Order ready for delivery
        unit_price = product[0]
        total = unit_price * quantity
        
        cursor.execute("INSERT INTO orders (customer, total, status) VALUES (?, ?, 'pending')", (customer, total))
        order_id = cursor.lastrowid
        cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)", (order_id, item_name, quantity))
        flash(f"Item found! Created Sales Order SO-{order_id} instantly.", "success")
    else:
        # PATH B: It does not exist. Route to the Procurement holding area
        cursor.execute(
            "INSERT INTO customer_requests (customer, requested_item, quantity) VALUES (?, ?, ?)",
            (customer, item_name, quantity)
        )
        flash(f"'{item_name}' is not in inventory. Routed to Special Requests for purchasing.", "success")
        
    conn.commit()
    conn.close()
    return redirect(url_for('orders'))

@app.route('/api/copilot', methods=['POST'])
def copilot():
    if 'username' not in session: 
        return jsonify({"reply": "Security Error: You must be logged in."})
    
    user_text = request.json.get('prompt')
    
    # 1. Added the new audit_invoice instruction here
    system_prompt = f"""
    You are AJ ERP Copilot. Convert the user's request into a strict JSON object. Do not include markdown.
    If they ask to check stock: {{"action": "check_stock", "item_name": "Name"}}
    If they ask to order a special item: {{"action": "special_request", "item_name": "Name", "quantity": number}}
    If they ask to add a product: {{"action": "add_product", "item_name": "Name", "price": number, "stock": number}}
    If they ask to remove the last product: {{"action": "remove_last_product"}}
    If they ask for recent orders: {{"action": "recent_orders", "limit": number}}
    If they ask to find or list suppliers: {{"action": "find_suppliers", "search_term": "Name or empty"}}
    If they ask to audit or match an invoice: {{"action": "audit_invoice", "po_number": number, "invoice_text": "Full text of the invoice"}}
    If they say a greeting or you don't understand: {{"action": "chat", "message": "Hello! I am your AJ ERP Copilot. How can I help you today?"}}
    User request: {user_text}
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="openai/gpt-oss-20b",
            temperature=0.1
        )
        
        raw_json = response.choices[0].message.content.replace('```json', '').replace('```', '').strip()
        command = json.loads(raw_json)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        action = command.get('action', 'chat')
        
        if action == 'chat':
            reply = command.get('message', 'Hello! How can I help you automate your workflow today?')
            
        elif action == 'check_stock':
            cursor.execute("SELECT stock FROM products WHERE name LIKE ? COLLATE NOCASE", ('%' + command['item_name'] + '%',))
            result = cursor.fetchone()
            reply = f"We currently have {result[0]} units of {command['item_name']} in stock." if result else f"Item '{command['item_name']}' not found."
            
        elif action == 'special_request':
            cursor.execute(
                "INSERT INTO customer_requests (customer, requested_item, quantity) VALUES (?, ?, ?)",
                (session['username'], command['item_name'], command['quantity'])
            )
            conn.commit()
            reply = f"Successfully logged a special request for {command['quantity']}x {command['item_name']}."
            
        elif action == 'add_product':
            cursor.execute(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                (command['item_name'], command['price'], command['stock'])
            )
            conn.commit()
            reply = f"Added {command['stock']} units of '{command['item_name']}' at ₹{command['price']} to master inventory."
            
        elif action == 'remove_last_product':
            cursor.execute("SELECT id, name FROM products ORDER BY id DESC LIMIT 1")
            last_product = cursor.fetchone()
            if last_product:
                cursor.execute("DELETE FROM products WHERE id = ?", (last_product[0],))
                conn.commit()
                reply = f"Successfully removed the last added product: '{last_product[1]}'."
            else:
                reply = "The inventory is already empty, nothing to remove."

        elif action == 'recent_orders':
            limit = command.get('limit', 3) 
            cursor.execute("SELECT id, customer, total, status FROM orders ORDER BY id DESC LIMIT ?", (limit,))
            orders = cursor.fetchall()
            if orders:
                reply = f"Here are your last {limit} orders:<br>"
                for o in orders:
                    reply += f"• <b>SO-{o[0]}</b>: {o[1]} - ₹{o[2]:,.2f} ({o[3]})<br>"
            else:
                reply = "No recent orders found."

        elif action == 'find_suppliers':
            search_term = command.get('search_term', '')
            if search_term:
                cursor.execute("SELECT name, contact, email FROM suppliers WHERE name LIKE ? COLLATE NOCASE", ('%' + search_term + '%',))
            else:
                cursor.execute("SELECT name, contact, email FROM suppliers LIMIT 5")
                
            suppliers = cursor.fetchall()
            if suppliers:
                reply = "Here are the matching suppliers:<br>"
                for s in suppliers:
                    reply += f"• <b>{s[0]}</b> (Contact: {s[1]} | Email: {s[2]})<br>"
            else:
                reply = "No suppliers found matching that request."

        # 2. NEW BLOCK: The Invoice Auditor Logic
        elif action == 'audit_invoice':
            po_number = command.get('po_number')
            invoice_text = command.get('invoice_text')
            
            # Fetch the expected order details from the database (assuming 'purchase_orders' table exists)
            try:
                cursor.execute("SELECT item_name, quantity, expected_price FROM purchase_orders WHERE id = ?", (po_number,))
                po_data = cursor.fetchone()
                
                if not po_data:
                    reply = f"Purchase Order #{po_number} not found in the database. Cannot complete audit."
                else:
                    po_item, po_qty, po_price = po_data
                    expected_total = po_qty * po_price
                    
                    # Ask the AI to compare the invoice text against your database facts
                    audit_prompt = f"""
                    Compare this supplier invoice: "{invoice_text}"
                    Against our internal PO: {po_qty}x {po_item} at ₹{po_price} each (Total expected: ₹{expected_total}).
                    If it matches perfectly, say: "✅ 3-Way Match Successful. Ready for payment."
                    If they overcharged or sent the wrong amount, say: "⚠️ Discrepancy Detected:" and explain why.
                    Keep it short and professional.
                    """
                    
                    audit_response = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": audit_prompt}],
                        model="openai/gpt-oss-20b",
                        temperature=0.1
                    )
                    
                    reply = audit_response.choices[0].message.content.strip()
            except sqlite3.OperationalError:
                # Fallback just in case you haven't created the purchase_orders table in your DB yet!
                reply = "The 'purchase_orders' table doesn't exist in the database yet. Please set up the P2P tables first."
                
        else:
            reply = "I understood the request, but I don't have the backend logic to perform that action yet."
            
        conn.close()
        return jsonify({"reply": reply})
        
    except Exception as e:
        return jsonify({"reply": f"System Error: {str(e)}"})

@app.route('/api/auto_procure', methods=['POST'])
def auto_procure():
    if 'username' not in session or session.get('role') != 'Manager':
        return jsonify({"status": "error", "message": "Security Alert: Only Managers can run Auto-Procurement."})

    if not demand_model:
        return jsonify({"status": "error", "message": "Demand model not found. Run train_model.py first!"})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check current inventory
    cursor.execute("SELECT id, name, price, stock FROM products")
    products = cursor.fetchall()
    
    requisitions_created = 0
    
    for prod in products:
        prod_id, name, price, current_stock = prod
        
        # Predict how many units will sell 
        predicted_demand = demand_model.predict([[price]])[0]
        
        # If the AI predicts you will sell more than you currently have (plus a 5-unit safety buffer)
        if predicted_demand > current_stock:
            qty_needed = int((predicted_demand - current_stock) + 5)
            
            if qty_needed > 0:
                cursor.execute(
                    """INSERT INTO purchase_requisitions 
                       (item_name, quantity, required_date, department, reason, status) 
                       VALUES (?, ?, date('now', '+7 days'), 'AI Auto-Procurement', 'Predicted demand exceeds current stock', 'pending')""",
                    (name, qty_needed)
                )
                requisitions_created += 1
            
    conn.commit()
    conn.close()
    
    return jsonify({
        "status": "success", 
        "message": f"Forecasting complete! The AI automatically generated {requisitions_created} Purchase Requisitions for low-stock items."
    })

@app.route('/api/match_invoice', methods=['POST'])
def match_invoice():
    if 'username' not in session: 
        return jsonify({"status": "error", "reply": "Security Alert: Please log in."})
        
    # In a full production app, you would use an OCR library (like Tesseract or Google Vision) 
    # to extract this text directly from an uploaded PDF.
    invoice_text = request.json.get('invoice_text') 
    po_number = request.json.get('po_number')
    
    # 1. Fetch the original PO from your database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Assuming you have a purchase_orders table. Adjust table/column names to match your schema.
    cursor.execute("SELECT item_name, quantity, expected_price FROM purchase_orders WHERE id = ?", (po_number,))
    po_data = cursor.fetchone()
    conn.close()
    
    if not po_data:
        return jsonify({"status": "error", "reply": f"Purchase Order #{po_number} not found in database."})
        
    po_item, po_qty, po_price = po_data
    expected_total = po_qty * po_price
    
    # 2. Instruct the AI to act as a financial auditor
    system_prompt = f"""
    You are an AI financial auditor for AJ ERP. Extract the billed item, quantity, and total price from the user's invoice text.
    Compare it against our internal Purchase Order details:
    - Expected Item: {po_item}
    - Expected Quantity: {po_qty}
    - Expected Unit Price: ₹{po_price}
    - Expected Total: ₹{expected_total}
    
    If the invoice matches our expectations exactly, set "match" to true. If they overcharged us or sent the wrong quantity, set "match" to false.
    Output a strict JSON object: {{"match": boolean, "reason": "Brief explanation of any discrepancies or confirmation of match"}}
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Supplier Invoice Text: {invoice_text}"}
            ],
            model="openai/gpt-oss-20b",
            temperature=0.1
        )
        
        raw_json = response.choices[0].message.content.replace('```json', '').replace('```', '').strip()
        audit = json.loads(raw_json)
        
        # 3. Return the audit result
        if audit['match']:
            return jsonify({"status": "success", "reply": f"✅ 3-Way Match Successful: {audit['reason']} Ready for finance to issue payment."})
        else:
            return jsonify({"status": "warning", "reply": f"⚠️ Discrepancy Detected: {audit['reason']} Invoice paused and routed to management."})
            
    except Exception as e:
        return jsonify({"status": "error", "reply": f"Audit Failed: {str(e)}"})
    
# ══════════════════════════════════════════════════════════════

# 1. Create a function to run your Flask app
def start_server():
    # Turn off debug mode for production security
    app.run(host='127.0.0.1', port=5000, debug=False)

if __name__ == '__main__':
    # 2. Start the Flask server in a background thread
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # 3. Open the native Windows desktop application window
    # It points directly to your local Flask server
    webview.create_window('AJ ERP System', 'http://127.0.0.1:5000', width=1200, height=800)
    webview.start()
    
    # Shut down completely when the user closes the window
    sys.exit()