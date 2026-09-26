import os
from flask import Flask, render_template, request, redirect, flash, session, Response, url_for, jsonify
import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression

# 1. Extract
conn = sqlite3.connect('database.db')

model = LinearRegression()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_database.db')

app = Flask(__name__)
# A secret key is required to use flash messages securely
app.secret_key = "super_secret_erp_key" 

# --- MASTER DATABASE INITIALIZATION ---
conn = sqlite3.connect('erp_database.db')
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
        contact_person TEXT,
        email TEXT
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
        
        conn = sqlite3.connect('erp_database.db')
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
    
    conn = sqlite3.connect('erp_database.db')
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
        
    conn = sqlite3.connect('erp_database.db')
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
        
    conn = sqlite3.connect('erp_database.db')
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
        
    conn = sqlite3.connect('erp_database.db')
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
        
    conn = sqlite3.connect('erp_database.db')
    cursor = conn.cursor()
    
    # 1. Detailed Sales Ledger — join order_items → products to get price
    cursor.execute('''
        SELECT p.name, oi.quantity, p.price, (oi.quantity * p.price) AS revenue
        FROM order_items oi
        JOIN products p ON oi.product_name = p.name
    ''')
    sales = cursor.fetchall()

    # 2. Aggregated Data for the Chart (Groups revenue by product)
    cursor.execute('''
        SELECT p.name, SUM(oi.quantity * p.price)
        FROM order_items oi
        JOIN products p ON oi.product_name = p.name
        GROUP BY p.name
    ''')
    chart_aggregation = cursor.fetchall()

    # Prepare Data for Chart.js
    chart_labels = []
    chart_data = []
    for row in chart_aggregation:
        chart_labels.append(row[0])
        chart_data.append(row[1])

    # 3. Calculate Grand Totals
    cursor.execute('''
        SELECT SUM(oi.quantity * p.price)
        FROM order_items oi
        JOIN products p ON oi.product_name = p.name
    ''')
    total_revenue = cursor.fetchone()[0] or 0.0

    cursor.execute('''SELECT SUM(total_cost) FROM purchases''')
    total_expenses = cursor.fetchone()[0] or 0.0
    
    net_profit = total_revenue - total_expenses
    
    conn.close()
    
    return render_template('finance.html', sales=sales, total_revenue=total_revenue, 
                           total_expenses=total_expenses, net_profit=net_profit, 
                           chart_labels=chart_labels, chart_data=chart_data)
@app.route('/restock', methods=['POST'])
def restock():
    product_id = int(request.form['product_id'])
    restock_qty = int(request.form['quantity'])
    cost = float(request.form['cost']) # New: Get the cost of the shipment
    
    conn = sqlite3.connect('erp_database.db')
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
@app.route('/suppliers')
def suppliers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # ADD THIS LINE TEMPORARILY: Destroy the old misconfigured table
    
    # Automatically create the table if it is missing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            email TEXT
        )
    ''')
    
    # Fetch all suppliers and pass them to the Jinja template
    cursor.execute("SELECT id, name, contact, email FROM suppliers")
    suppliers_data = cursor.fetchall()
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
@app.route('/orders')
def orders():
    status_filter = request.args.get('status', '')
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    # The proper relational JOIN query to stitch the parent and child tables together
    query = '''
        SELECT o.id, o.customer, o.total, o.status, o.created_at,
               GROUP_CONCAT(oi.quantity || 'x ' || oi.product_name, ', ') as items
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
    '''
    
    if status_filter:
        query += " WHERE o.status = ? GROUP BY o.id"
        cursor.execute(query, (status_filter,))
    else:
        query += " GROUP BY o.id"
        cursor.execute(query)
        
    orders_data = [dict(row) for row in cursor.fetchall()]
    
    # Fetch active products for the dropdown
    cursor.execute("SELECT name FROM products")
    available_products = [row['name'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('orders.html', orders=orders_data, available_products=available_products)
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
    product_name = request.form['product_name']  # Now correctly matches the HTML dropdown
    quantity = int(request.form['quantity'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Look up the product's price to calculate the order total
    cursor.execute("SELECT price FROM products WHERE name = ?", (product_name,))
    product = cursor.fetchone()
    
    if product:
        unit_price = product[0]
        total = unit_price * quantity
        
        # Step A: Insert the parent transaction
        cursor.execute("INSERT INTO orders (customer, total, status) VALUES (?, ?, 'pending')", 
                       (customer, total))
        order_id = cursor.lastrowid 
        
        # Step B: Insert the child item linked to the Order ID
        cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)",
                       (order_id, product_name, quantity))
                       
        # Step C: Automatically deduct the purchased quantity from inventory
        cursor.execute("UPDATE products SET stock = stock - ? WHERE name = ?", 
                       (quantity, product_name))
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

if __name__ == '__main__':
    app.run(debug=True)