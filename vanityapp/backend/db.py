"""
Database module - Enhanced with Referral System
"""
import os
import sqlite3
import time
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = "shop.db"

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def init_db():
    """Initialize database with all required tables"""
    with get_db() as conn:
        cur = conn.cursor()
        
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            balance_sol REAL DEFAULT 0,
            deposit_address TEXT UNIQUE,
            referred_by INTEGER,
            referral_earnings REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            last_active INTEGER
        );
        
        CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_users_deposit_address ON users(deposit_address);
        CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price_sol REAL NOT NULL,
            location TEXT,
            city TEXT,
            stock INTEGER DEFAULT -1,
            is_active INTEGER DEFAULT 1,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS product_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            channel_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            content_type TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            price_sol REAL NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at INTEGER NOT NULL,
            delivered_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_signature TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            amount_sol REAL NOT NULL,
            tx_type TEXT NOT NULL,
            related_order_id TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_signature ON transactions(tx_signature);

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            added_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at INTEGER
        );
        
        """)
        
        now = int(time.time())
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('referral_bonus_percent', '5', now))
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('referral_discount_percent', '5', now))
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('referral_commission_percent', '5', now))
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('min_deposit_sol', '0.001', now))
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('content_channel_id', '', now))
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('stuff_link', 'https://t.me/+oQMNK45adl9hNzk0', now))
        cur.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                   ('support_link', 'https://t.me/vanitysupport', now))           
        
        # Migrations
        if not column_exists(cur, 'users', 'deposit_address'):
            cur.execute("ALTER TABLE users ADD COLUMN deposit_address TEXT UNIQUE")
        if not column_exists(cur, 'users', 'referred_by'):
            cur.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if not column_exists(cur, 'users', 'referral_earnings'):
            cur.execute("ALTER TABLE users ADD COLUMN referral_earnings REAL DEFAULT 0")
        if not column_exists(cur, 'users', 'last_active'):
            cur.execute("ALTER TABLE users ADD COLUMN last_active INTEGER")
        if not column_exists(cur, 'products', 'city'):
            cur.execute("ALTER TABLE products ADD COLUMN city TEXT")
        if not column_exists(cur, 'products', 'stock'):
            cur.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT -1")
        if not column_exists(cur, 'products', 'is_active'):
            cur.execute("ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1")
        if not column_exists(cur, 'products', 'created_at'):
            cur.execute("ALTER TABLE products ADD COLUMN created_at INTEGER DEFAULT 0")
        
        conn.commit()

# ============ USER OPERATIONS ============

def generate_referral_code(user_id: int) -> str:
    """Generate a random-looking referral code from user ID"""
    import hashlib
    # Create hash from user_id + salt
    salt = "vanity_shop_ref_2024"
    raw = f"{user_id}{salt}".encode()
    hash_obj = hashlib.sha256(raw)
    # Take first 8 characters of hex for a clean code
    return hash_obj.hexdigest()[:8].upper()

def decode_referral_code(code: str) -> Optional[int]:
    """Try to find user_id from referral code"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, telegram_id FROM users")
        users = cur.fetchall()
        
        for user in users:
            if generate_referral_code(user[0]) == code.upper():
                return user[0]  # Return internal user id
        return None

def get_or_create_user(telegram_id: int, username: str = None, 
                       first_name: str = None, referred_by: int = None) -> Dict[str, Any]:
    """Get existing user or create new one"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        
        if row:
            cur.execute("UPDATE users SET last_active = ? WHERE telegram_id = ?", 
                       (int(time.time()), telegram_id))
            conn.commit()
            return dict(row)
        
        now = int(time.time())
        cur.execute("""
            INSERT INTO users (telegram_id, username, first_name, referred_by, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (telegram_id, username, first_name, referred_by, now, now))
        conn.commit()
        
        return get_user_by_telegram_id(telegram_id)

def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user by telegram ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by internal ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def update_user_deposit_address(telegram_id: int, address: str) -> bool:
    """Assign deposit address to user"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET deposit_address = ? WHERE telegram_id = ?", 
                   (address, telegram_id))
        conn.commit()
        return cur.rowcount > 0

def get_user_by_deposit_address(address: str) -> Optional[Dict[str, Any]]:
    """Find user by their deposit address"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE deposit_address = ?", (address,))
        row = cur.fetchone()
        return dict(row) if row else None

def update_balance(user_id: int, amount: float) -> bool:
    """Add to user balance (can be negative for deductions)"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance_sol = balance_sol + ? WHERE id = ?", 
                   (amount, user_id))
        # Track referral earnings separately
        if amount > 0:
            cur.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            last_tx = cur.fetchone()
            if last_tx and ('referral' in last_tx['tx_type']):
                cur.execute("UPDATE users SET referral_earnings = referral_earnings + ? WHERE id = ?",
                           (amount, user_id))
        conn.commit()
        return cur.rowcount > 0

def set_balance(user_id: int, amount: float) -> bool:
    """Set user balance to specific amount"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance_sol = ? WHERE id = ?", (amount, user_id))
        conn.commit()
        return cur.rowcount > 0

def ban_user(telegram_id: int) -> bool:
    """Ban a user"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_banned = 1 WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        return cur.rowcount > 0

def unban_user(telegram_id: int) -> bool:
    """Unban a user"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_banned = 0 WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        return cur.rowcount > 0

def get_all_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Get all users with pagination"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM users 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cur.fetchall()]

def search_users(query: str) -> List[Dict[str, Any]]:
    """Search users by username or telegram_id"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM users 
            WHERE username LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (f"%{query}%", f"%{query}%"))
        return [dict(row) for row in cur.fetchall()]

# ============ REFERRAL OPERATIONS ============

def get_referral_stats(user_id: int) -> Dict[str, Any]:
    """Get referral statistics for a user"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            # Count referred users
            try:
                cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
                referred_count = cur.fetchone()[0] or 0
            except Exception:
                referred_count = 0
            
            # Get total earnings from referrals
            try:
                cur.execute("""
                    SELECT COALESCE(SUM(amount_sol), 0) FROM transactions 
                    WHERE user_id = ? AND (tx_type = 'referral_bonus' OR tx_type = 'referral_commission')
                """, (user_id,))
                total_earnings = cur.fetchone()[0] or 0.0
            except Exception:
                total_earnings = 0.0
            
            # Count purchases made by referrals
            try:
                cur.execute("""
                    SELECT COUNT(*) FROM orders o
                    JOIN users u ON o.user_id = u.id
                    WHERE u.referred_by = ?
                """, (user_id,))
                referral_purchases = cur.fetchone()[0] or 0
            except Exception:
                referral_purchases = 0
            
            return {
                'referred_count': referred_count,
                'total_earnings': float(total_earnings),
                'referral_purchases': referral_purchases
            }
    except Exception as e:
        logger.error(f"Error in get_referral_stats: {e}")
        return {
            'referred_count': 0,
            'total_earnings': 0.0,
            'referral_purchases': 0
        }

def get_all_referrals() -> List[Dict[str, Any]]:
    """Get all referral relationships with details"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                u.id as user_id,
                u.telegram_id,
                u.username,
                u.referred_by as referrer_id,
                r.telegram_id as referrer_telegram_id,
                r.username as referrer_username,
                u.balance_sol,
                u.referral_earnings,
                u.created_at,
                (SELECT COUNT(*) FROM orders WHERE user_id = u.id) as purchase_count,
                (SELECT COALESCE(SUM(price_sol), 0) FROM orders WHERE user_id = u.id) as total_spent
            FROM users u
            LEFT JOIN users r ON u.referred_by = r.id
            WHERE u.referred_by IS NOT NULL
            ORDER BY u.created_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]

def get_referrals_by_user(referrer_id: int) -> List[Dict[str, Any]]:
    """Get all users referred by a specific user"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                u.*,
                (SELECT COUNT(*) FROM orders WHERE user_id = u.id) as purchase_count,
                (SELECT COALESCE(SUM(price_sol), 0) FROM orders WHERE user_id = u.id) as total_spent
            FROM users u
            WHERE u.referred_by = ?
            ORDER BY u.created_at DESC
        """, (referrer_id,))
        return [dict(row) for row in cur.fetchall()]

def get_top_referrers(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top referrers by earnings"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                u.id,
                u.telegram_id,
                u.username,
                u.referral_earnings,
                COUNT(DISTINCT ref.id) as referred_count,
                COALESCE(SUM(o.price_sol), 0) as total_referral_revenue
            FROM users u
            LEFT JOIN users ref ON ref.referred_by = u.id
            LEFT JOIN orders o ON o.user_id = ref.id
            WHERE u.referral_earnings > 0
            GROUP BY u.id
            ORDER BY u.referral_earnings DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

# ============ PRODUCT OPERATIONS ============

def create_product(name: str, price_sol: float, description: str = "",
                   city: str = "", location: str = "", stock: int = -1) -> int:
    """Create new product"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO products (name, description, price_sol, location, city, stock, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, description, price_sol, location, city, stock, int(time.time())))
        conn.commit()
        product_id = cur.lastrowid

    media_folder = f"/root/locimg/product_{product_id}"
    os.makedirs(media_folder, exist_ok=True)

    return product_id

def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    """Get product by ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_products(city: str = None, active_only: bool = True) -> List[Dict[str, Any]]:
    """Get all products, optionally filtered by city"""
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        
        if active_only:
            query += " AND is_active = 1"
        if city:
            query += " AND city = ?"
            params.append(city)
        
        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

def update_product(product_id: int, **kwargs) -> bool:
    """Update product fields"""
    if not kwargs:
        return False
    
    with get_db() as conn:
        cur = conn.cursor()
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [product_id]
        cur.execute(f"UPDATE products SET {fields} WHERE id = ?", values)
        conn.commit()
        return cur.rowcount > 0

def delete_product(product_id: int) -> bool:
    """Soft delete product"""
    return update_product(product_id, is_active=0)

def decrease_stock(product_id: int) -> bool:
    """Decrease product stock by 1"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE products 
            SET stock = stock - 1 
            WHERE id = ? AND (stock > 0 OR stock = -1)
        """, (product_id,))
        conn.commit()
        return cur.rowcount > 0

# ============ PRODUCT CONTENT ============

def add_product_content(product_id: int, channel_id: str, message_id: int, 
                        content_type: str = "media") -> int:
    """Link channel message to product"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO product_content (product_id, channel_id, message_id, content_type)
            VALUES (?, ?, ?, ?)
        """, (product_id, channel_id, message_id, content_type))
        conn.commit()
        return cur.lastrowid

def get_product_content(product_id: int) -> List[Dict[str, Any]]:
    """Get all content items for a product"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM product_content 
            WHERE product_id = ? 
            ORDER BY id ASC
        """, (product_id,))
        return [dict(row) for row in cur.fetchall()]

def delete_product_content(product_id: int) -> bool:
    """Delete all content for a product"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM product_content WHERE product_id = ?", (product_id,))
        conn.commit()
        return cur.rowcount > 0

# ============ ORDER OPERATIONS ============

def create_order(user_id: int, product_id: int, price_sol: float) -> str:
    """Create new order"""
    import uuid
    order_id = uuid.uuid4().hex[:16]
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orders (order_id, user_id, product_id, price_sol, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (order_id, user_id, product_id, price_sol, int(time.time())))
        conn.commit()
    
    return order_id

def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    """Get order by ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_user_orders(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Get user's orders"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT o.*, p.name as product_name 
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC
            LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cur.fetchall()]

def mark_order_delivered(order_id: str) -> bool:
    """Mark order as delivered"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE orders SET delivered_at = ? WHERE order_id = ?
        """, (int(time.time()), order_id))
        conn.commit()
        return cur.rowcount > 0

# ============ TRANSACTION OPERATIONS ============

def record_transaction(user_id: int, tx_signature: str, amount_sol: float, 
                       tx_type: str, related_order_id: str = None) -> int:
    """Record a blockchain transaction"""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO transactions (user_id, tx_signature, amount_sol, tx_type, related_order_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, tx_signature, amount_sol, tx_type, related_order_id, int(time.time())))
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return 0

def get_transaction_by_signature(signature: str) -> Optional[Dict[str, Any]]:
    """Check if transaction already processed"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM transactions WHERE tx_signature = ?", (signature,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_recent_transactions(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent transactions"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.*, u.username, u.telegram_id
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

# ============ ADMIN OPERATIONS ============

def add_admin(telegram_id: int, username: str = None) -> bool:
    """Add admin user"""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO admin_users (telegram_id, username, added_at)
                VALUES (?, ?, ?)
            """, (telegram_id, username, int(time.time())))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def is_admin(telegram_id: int) -> bool:
    """Check if user is admin"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM admin_users WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone() is not None

def get_all_admins() -> List[Dict[str, Any]]:
    """Get all admins"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin_users ORDER BY added_at DESC")
        return [dict(row) for row in cur.fetchall()]

def remove_admin(telegram_id: int) -> bool:
    """Remove admin"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM admin_users WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        return cur.rowcount > 0

# ============ STATISTICS ============

def get_stats() -> Dict[str, Any]:
    """Get overall statistics"""
    with get_db() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE created_at > ?", 
                   (int(time.time()) - 86400,))
        new_users_today = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM orders")
        total_orders = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM orders WHERE created_at > ?", 
                   (int(time.time()) - 86400,))
        orders_today = cur.fetchone()[0]
        
        cur.execute("SELECT COALESCE(SUM(price_sol), 0) FROM orders")
        total_revenue = cur.fetchone()[0]
        
        cur.execute("SELECT COALESCE(SUM(price_sol), 0) FROM orders WHERE created_at > ?", 
                   (int(time.time()) - 86400,))
        revenue_today = cur.fetchone()[0]
        
        cur.execute("SELECT COALESCE(SUM(amount_sol), 0) FROM transactions WHERE tx_type = 'deposit'")
        total_deposits = cur.fetchone()[0]
        
        # Referral stats
        cur.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
        total_referrals = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COALESCE(SUM(amount_sol), 0) FROM transactions 
            WHERE tx_type IN ('referral_bonus', 'referral_commission')
        """)
        total_referral_earnings = cur.fetchone()[0]
        
        return {
            'total_users': total_users,
            'new_users_today': new_users_today,
            'total_orders': total_orders,
            'orders_today': orders_today,
            'total_revenue': total_revenue,
            'revenue_today': revenue_today,
            'total_deposits': total_deposits,
            'total_referrals': total_referrals,
            'total_referral_earnings': total_referral_earnings
        }

# ============ SETTINGS ============

def get_setting(key: str, default: str = None) -> Optional[str]:
    """Get setting value"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

def set_setting(key: str, value: str) -> bool:
    """Set setting value"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, int(time.time())))
        conn.commit()
        return True