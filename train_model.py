import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression
import pickle
import os

# Define database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'erp_database.db')

def train_demand_model():
    # 1. Connect to your live database
    conn = sqlite3.connect(DB_PATH)
    
    # 2. Query product prices and total quantities sold from your relational tables
    query = '''
        SELECT p.price, SUM(oi.quantity) as total_sold
        FROM products p
        JOIN order_items oi ON p.name = oi.product_name
        GROUP BY p.name, p.price
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Check if we have enough data points to train
    if len(df) < 2:
        print("⚠️ Not enough order history yet! Please place a few more orders in your ERP system before training.")
        return

    # 3. Define features (X) and target (y)
    X = df[['price']]  # Independent variable: Price
    y = df['total_sold']  # Dependent variable: Demand / Units Sold

    # 4. Initialize and train the Linear Regression model
    model = LinearRegression()
    model.fit(X, y)
    
    print("✅ Machine Learning Model trained successfully!")
    print(f"Model Coefficient (Slope): {model.coef_[0]:.2f}")
    print(f"Model Intercept: {model.intercept_:.2f}")

    # 5. Save the trained model to disk so app.py can load it
    model_path = os.path.join(BASE_DIR, 'model.pkl')
    with open(model_path, 'wb') as file:
        pickle.dump(model, file)
    
    print(f"💾 Model saved successfully to {model_path}")

if __name__ == '__main__':
    train_demand_model()