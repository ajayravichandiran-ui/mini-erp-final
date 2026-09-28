import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"

def test_entire_erp_system(page: Page):
    # ==========================================
    # 1. AUTHENTICATION & SECURITY
    # ==========================================
    page.goto(f"{BASE_URL}/login")
    page.fill("input[name='username']", "admin")  # Use your local credentials
    page.fill("input[name='password']", "password123") 
    page.click("button[type='submit']")
    page.wait_for_url(f"{BASE_URL}/") 

    # ==========================================
    # 2. NAVIGATION & SMOKE TESTING (Checking for crashes)
    # ==========================================
    # Check Inventory (Home)
    expect(page.locator("h1").first).to_contain_text("Inventory", ignore_case=True)
    
    # Check Suppliers
    page.click("a[href='/suppliers']")
    page.wait_for_url(f"{BASE_URL}/suppliers")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    # Check Repairs
    page.click("a[href='/repairs']")
    page.wait_for_url(f"{BASE_URL}/repairs")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    # Check Procure-to-Pay (P2P)
    page.click("a[href='/p2p']")
    page.wait_for_url(f"{BASE_URL}/p2p")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    # Check Finance
    page.click("a[href='/finance']")
    page.wait_for_url(f"{BASE_URL}/finance")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    # ==========================================
    # 3. DATABASE WRITE TEST (O2C Pipeline)
    # ==========================================
    page.click("a[href='/orders']")
    page.wait_for_url(f"{BASE_URL}/orders")
    
    # Create Sales Order
    page.fill("input[name='customer']", "E2E Automated Corp")
    page.select_option("select[name='product_name']", index=1) 
    page.fill("input[name='quantity']", "10")
    page.click("text=Generate Sales Order")
    expect(page.locator("text=E2E Automated Corp").first).to_be_visible()
    
    # Outbound Delivery
    page.click("text=🚚 Outbound Delivery")
    page.select_option("#tab-delivery select[name='order_id']", index=1)
    page.fill("input[name='delivery_date']", "2026-10-31")
    page.click("text=Log Delivery & Deduct Stock")
    expect(page.locator("text=Dispatched").first).to_be_visible()
    
    # AR Invoice
    page.click("text=🧾 AR & Billing")
    page.select_option("#tab-invoice select[name='order_id']", index=1)
    page.fill("input[name='invoice_number']", "INV-E2E-999")
    page.fill("input[name='amount']", "1000")
    page.fill("input[name='due_date']", "2026-11-30")
    page.click("text=Generate Invoice")
    expect(page.locator("text=INV-E2E-999").first).to_be_visible()

    # ==========================================
    # 4. LOGOUT & SESSION CLEAR
    # ==========================================
    page.click("a[href='/logout']")
    page.wait_for_url(f"{BASE_URL}/login")
    expect(page.locator("button[type='submit']")).to_be_visible()