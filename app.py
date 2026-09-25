import os
from flask import Flask, render_template, request, redirect, flash, session, Response, url_for
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
    # 1. Connect to your SQLite database
    conn = sqlite3.connect('erp_database.db')
    cursor = conn.cursor()
    
    # 2. Fetch the product names and their current stock levels
    cursor.execute("SELECT name, stock FROM products")
    inventory_data = cursor.fetchall()
    conn.close()
    
    # 3. Separate the data into two lists for Chart.js
    product_names = [row[0] for row in inventory_data]
    stock_levels = [row[1] for row in inventory_data]
    
    # 4. Pass the lists into the HTML template
    return render_template('index.html', 
                           labels=product_names, 
                           data=stock_levels)

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

@app.route('/suppliers', methods=['GET', 'POST'])
def suppliers():
    # RBAC Security Check
    if 'username' not in session or session.get('role') != 'Manager':
        flash("Security Alert: Only Managers can access Vendor data.", "error")
        return redirect('/')
        
    conn = sqlite3.connect('erp_database.db')
    cursor = conn.cursor()
    
    # If the form was submitted, add the new supplier
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        email = request.form['email']
        
        cursor.execute("INSERT INTO suppliers (name, contact_person, email) VALUES (?, ?, ?)", (name, contact, email))
        conn.commit()
        flash(f"Success: Supplier {name} added to directory.", "success")
        return redirect('/suppliers')
        
    # Fetch all suppliers to display on the page
    cursor.execute("SELECT * FROM suppliers")
    vendors = cursor.fetchall()
    conn.close()
    
    return render_template('suppliers.html', vendors=vendors)

if __name__ == '__main__':
    app.run(debug=True)