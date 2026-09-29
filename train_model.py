import os
import pickle
import numpy as np
from sklearn.linear_model import LinearRegression

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'model.pkl')

print("Analyzing historical pricing and demand data...")

# Generate synthetic training data (Features: Price -> Target: Demand)
# In production, you would pull this directly from your order_items table
np.random.seed(42)
prices = np.random.uniform(50, 2500, 200).reshape(-1, 1)

# Assume demand naturally decreases as price increases, plus some random market noise
demand = np.maximum(0, 150 - (prices.flatten() * 0.05) + np.random.normal(0, 10, 200))

# Train the model
model = LinearRegression()
model.fit(prices, demand)

# Save the trained model to a file
with open(MODEL_PATH, 'wb') as f:
    pickle.dump(model, f)

print(f"✅ AI Demand Model successfully trained and saved to: {MODEL_PATH}")