import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"

def test_o2c_pipeline(page: Page):
    # 1. Login
    page.goto(f"{BASE_URL}/login")
    page.fill("input[name='username']", "admin") 
    page.fill("input[name='password']", "password123") 
    page.click("button[type='submit']")
    page.wait_for_url(f"{BASE_URL}/") 

    # 2. Go to Orders Page
    page.goto(f"{BASE_URL}/orders")
    
    # 3. Create Sales Order
    page.fill("input[name='customer']", "Automated Test Corp")
    page.select_option("select[name='product_name']", index=1) 
    page.fill("input[name='quantity']", "5")
    page.click("text=Generate Sales Order")
    expect(page.locator("text=Automated Test Corp").first).to_be_visible()
    
    # 4. Outbound Delivery
    page.click("text=🚚 Outbound Delivery")
    # Tell Playwright to ONLY look inside the delivery tab
    page.select_option("#tab-delivery select[name='order_id']", index=1)
    page.fill("input[name='delivery_date']", "2026-10-31")
    page.click("text=Log Delivery & Deduct Stock")
    expect(page.locator("text=Dispatched").first).to_be_visible()
    
    # 5. AR Invoice
    page.click("text=🧾 AR & Billing")
    # Tell Playwright to ONLY look inside the invoice tab
    page.select_option("#tab-invoice select[name='order_id']", index=1)
    page.fill("input[name='invoice_number']", "INV-TEST-01")
    page.fill("input[name='amount']", "500")
    page.fill("input[name='due_date']", "2026-11-30")
    page.click("text=Generate Invoice")
    expect(page.locator("text=INV-TEST-01").first).to_be_visible()