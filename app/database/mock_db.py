import sqlite3

def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cursor = conn.cursor()
    
    # Create Orders table
    cursor.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            purchase_date TEXT,
            days_ago INTEGER,
            amount REAL,
            item_name TEXT,
            category TEXT
        )
    """)
    
    # Create Policies table
    cursor.execute("""
        CREATE TABLE policies (
            category TEXT PRIMARY KEY,
            max_return_days INTEGER,
            allow_refund INTEGER
        )
    """)
    
    # Seed Mock Orders
    cursor.executemany("""
        INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ("ORDER101", "CUST_991", "2026-09-19", 5, 49.99, "Wireless Mouse", "Electronics"),
        ("ORDER102", "CUST_992", "2026-08-01", 54, 199.99, "Smart Watch", "Electronics"),
        ("ORDER103", "CUST_993", "2026-09-20", 4, 120.00, "Running Shoes", "Apparel")
    ])
    
    # Seed Mock Policies
    cursor.executemany("""
        INSERT INTO policies VALUES (?, ?, ?)
    """, [
        ("Electronics", 14, 1),
        ("Apparel", 30, 1)
    ])
    
    conn.commit()
    return conn

db_conn = init_db()

def get_order(order_id: str):
    cursor = db_conn.cursor()
    cursor.execute("SELECT order_id, customer_id, days_ago, amount, category, item_name FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "order_id": row[0],
        "customer_id": row[1],
        "days_ago": row[2],
        "amount": row[3],
        "category": row[4],
        "item_name": row[5]
    }

def get_policy(category: str):
    cursor = db_conn.cursor()
    cursor.execute("SELECT max_return_days, allow_refund FROM policies WHERE category = ?", (category,))
    row = cursor.fetchone()
    if not row:
        return {"max_return_days": 30, "allow_refund": True} # Default fallback policy
    return {"max_return_days": row[0], "allow_refund": bool(row[1])}