import sqlite3

c = sqlite3.connect(r"c:\Users\AJAY RAVICHANDIRAN\Desktop\mini-erp\erp_database.db")
cur = c.cursor()
cur.execute("SELECT id, name, stock, price FROM products")
print("BEFORE:", cur.fetchall())
cur.execute(
    "DELETE FROM products WHERE name = '' OR CAST(stock AS TEXT) = '' OR stock IS NULL"
)
print("deleted", cur.rowcount)
c.commit()
cur.execute("SELECT id, name, stock, price FROM products")
print("AFTER:", cur.fetchall())
c.close()
