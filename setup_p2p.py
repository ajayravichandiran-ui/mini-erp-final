import sqlite3

# Ensure this matches the DB_PATH from your app_2.py file (e.g., 'erp.db' or 'inventory.db')
DB_PATH = 'erp_database.db' 

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Create the table
cursor.execute('''
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT,
    quantity INTEGER,
    expected_price REAL
)
''')

# 2. Insert PO #2 for your test
# We will set our expected internal price to ₹8 so the AI catches the supplier's ₹10 overcharge!
cursor.execute("INSERT OR REPLACE INTO purchase_orders (id, item_name, quantity, expected_price) VALUES (2, 'Qa cables', 5, 8.0)")

conn.commit()
conn.close()

print("P2P table successfully created and PO #2 inserted!")