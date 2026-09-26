import sqlite3
import os

# Locate the database path dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_database.db')

def seed_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Ensure tables exist (matching your app.py schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')

    # 2. Recommended Products to Add
    products = [
        ("Mechanical RGB Gaming Keyboard", 89.99, 40),
        ("Ergonomic Vertical Mouse", 45.50, 60),
        ("Ultra-Wide 34-Inch Curved Monitor", 399.00, 15),
        ("External 1TB NVMe SSD", 119.99, 50),
        ("16GB DDR5 RAM Kit", 85.00, 30),
        ("USB-C Multiport Docking Station", 129.50, 25)
    ]
    
    for name, price, stock in products:
        cursor.execute("SELECT id FROM products WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock))

    # 3. Sample Order Histories (Relational Parent-Child insertion)
    sample_orders = [
        ("Alpha Technologies", [("Mechanical RGB Gaming Keyboard", 2), ("Ergonomic Vertical Mouse", 3)]),
        ("Beta Global Industries", [("Ultra-Wide 34-Inch Curved Monitor", 1), ("External 1TB NVMe SSD", 2)]),
        ("Gamma Systems", [("16GB DDR5 RAM Kit", 4), ("USB-C Multiport Docking Station", 1)])
    ]
    
    for customer, items in sample_orders:
        total = 0
        resolved_items = []
        
        # Calculate order total dynamically from current product prices
        for prod_name, qty in items:
            cursor.execute("SELECT price FROM products WHERE name = ?", (prod_name,))
            res = cursor.fetchone()
            if res:
                unit_price = res[0]
                total += unit_price * qty
                resolved_items.append((prod_name, qty))
        
        # Insert parent order
        cursor.execute("INSERT INTO orders (customer, total, status) VALUES (?, ?, 'shipped')", (customer, total))
        order_id = cursor.lastrowid
        
        # Insert child order items
        for prod_name, qty in resolved_items:
            cursor.execute("INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)", (order_id, prod_name, qty))
            
    conn.commit()
    conn.close()
    print("✅ Database successfully seeded with products and order histories!")

if __name__ == '__main__':
    seed_data()