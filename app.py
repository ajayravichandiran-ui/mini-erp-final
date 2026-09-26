import os
from flask import Flask, render_template, request, redirect, flash, session, Response, url_for, jsonify
import sqlite3

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
cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        processed_by TEXT, -- NEW: Tracks which employee processed this
        FOREIGN KEY(product_id) REFERENCES products(id)
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


def add():
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

@app.route('/order', methods=['POST'])
def order():
    if 'username' not in session:
        return redirect('/login')
        
    product_id = int(request.form['product_id'])
    quantity = int(request.form['quantity'])
    processed_by = session['username'] # Grab the employee's username
    
    conn = sqlite3.connect('erp_database.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, stock FROM products WHERE id = ?", (product_id,))
    result = cursor.fetchone()
    
    if not result:
        flash("Error: Product ID does not exist!", "error")
    elif result[1] < quantity:
        flash(f"Error: Not enough stock for {result[0]}. Only {result[1]} left.", "error")
    else:
        new_stock = result[1] - quantity
        cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
        
        # Save the transaction WITH the employee's name
        cursor.execute("INSERT INTO orders (product_id, quantity, processed_by) VALUES (?, ?, ?)", (product_id, quantity, processed_by))
        conn.commit()
        flash(f"Success: Order placed for {quantity}x {result[0]}!", "success")
        
    conn.close()
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
    
    # 1. Detailed Sales Ledger (Shows every individual transaction for the table)
    cursor.execute('''SELECT p.name, o.quantity, p.price, (o.quantity * p.price) AS revenue 
                      FROM orders o JOIN products p ON o.product_id = p.id''')
    sales = cursor.fetchall()
    
    # 2. Aggregated Data for the Chart (Groups revenue by product)
    cursor.execute('''SELECT p.name, SUM(o.quantity * p.price) 
                      FROM orders o JOIN products p ON o.product_id = p.id 
                      GROUP BY p.name''')
    chart_aggregation = cursor.fetchall()
    
    # Prepare Data for Chart.js
    chart_labels = []
    chart_data = []
    for row in chart_aggregation:
        chart_labels.append(row[0]) # Product Name
        chart_data.append(row[1])   # Total Aggregated Revenue
    
    # 3. Calculate Grand Totals
    cursor.execute('''SELECT SUM(o.quantity * p.price) FROM orders o JOIN products p ON o.product_id = p.id''')
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
    cursor.execute("SELECT name, stock FROM products WHERE name LIKE ?", ('%' + search_query + '%',))
    search_results = cursor.fetchall()
    conn.close()
    
    # Format the data exactly like the main index route for Chart.js and the Jinja loop
    labels = [item[0] for item in search_results]
    data = [item[1] for item in search_results]
    
    # Render the main dashboard, but only feed it the filtered search results
    return render_template('index.html', labels=labels, data=data)

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    if status_filter:
        cursor.execute("SELECT * FROM orders WHERE status = ?", (status_filter,))
    else:
        cursor.execute("SELECT * FROM orders")
        
    # THE FIX: Convert sqlite3.Row objects into standard Python dictionaries
    orders_data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('orders.html', orders=orders_data)

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
    cursor.execute("INSERT INTO orders (customer, items, total, status) VALUES ('Tech Corp', '10x Laptops, 5x Mice', 12500.00, 'pending')")
    cursor.execute("INSERT INTO orders (customer, items, total, status) VALUES ('Global Industries', '2x Server Racks', 4500.50, 'shipped')")
    conn.commit()
    conn.close()
    return redirect(url_for('orders'))


@app.route('/add_order', methods=['POST'])
def add_order():
    customer = request.form['customer']
    items = request.form['items']
    total = float(request.form['total'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # New orders default to 'pending' status
    cursor.execute("INSERT INTO orders (customer, items, total, status) VALUES (?, ?, ?, 'pending')", 
                   (customer, items, total))
    conn.commit()
    conn.close()
    
    return redirect(url_for('orders'))

if __name__ == '__main__':
    app.run(debug=True)