#!/usr/bin/env python3
"""
Management utility script for Vanity Shop Bot
Usage: python manage.py <command> [options]
"""

import sys
import argparse
from datetime import datetime

import db


def add_admin(telegram_id: int, username: str = None):
    """Add a new admin user"""
    if db.add_admin(telegram_id, username):
        print(f"✅ Admin added: {telegram_id} (@{username})")
    else:
        print(f"❌ Admin already exists or error occurred")


def remove_admin(telegram_id: int):
    """Remove an admin user"""
    if db.remove_admin(telegram_id):
        print(f"✅ Admin removed: {telegram_id}")
    else:
        print(f"❌ Admin not found")


def list_admins():
    """List all admin users"""
    admins = db.get_all_admins()
    if not admins:
        print("No admins found")
        return
    
    print("\n📋 Admin Users:")
    print("-" * 50)
    for admin in admins:
        date = datetime.fromtimestamp(admin['added_at']).strftime('%Y-%m-%d')
        print(f"  {admin['telegram_id']} (@{admin['username']}) - Added: {date}")
    print("-" * 50)


def stats():
    """Show bot statistics"""
    stats = db.get_stats()
    
    print("\n📊 Bot Statistics")
    print("=" * 50)
    print(f"\n👥 Users:")
    print(f"   Total: {stats['total_users']}")
    print(f"   New Today: {stats['new_users_today']}")
    
    print(f"\n📦 Orders:")
    print(f"   Total: {stats['total_orders']}")
    print(f"   Today: {stats['orders_today']}")
    
    print(f"\n💰 Revenue:")
    print(f"   Total: {stats['total_revenue']:.6f} SOL")
    print(f"   Today: {stats['revenue_today']:.6f} SOL")
    
    print(f"\n💳 Deposits:")
    print(f"   Total: {stats['total_deposits']:.6f} SOL")
    print("=" * 50)


def list_users(limit: int = 10, search: str = None):
    """List users"""
    if search:
        users = db.search_users(search)
    else:
        users = db.get_all_users(limit=limit)
    
    if not users:
        print("No users found")
        return
    
    print(f"\n👥 Users (showing {len(users)}):")
    print("-" * 70)
    for user in users:
        status = "🚫 BANNED" if user['is_banned'] else "✅"
        print(f"{status} {user['telegram_id']} | @{user['username'] or 'N/A':<15} | "
              f"Balance: {user['balance_sol']:>10.6f} SOL")
    print("-" * 70)


def list_products():
    """List all products"""
    products = db.get_products(active_only=False)
    
    if not products:
        print("No products found")
        return
    
    print(f"\n📦 Products (total: {len(products)}):")
    print("-" * 80)
    for p in products:
        status = "✅" if p['is_active'] else "❌"
        stock = f"{p['stock']}" if p['stock'] != -1 else "♾️"
        print(f"{status} [{p['id']:>3}] {p['name']:<30} | "
              f"{p['price_sol']:>8.4f} SOL | "
              f"Stock: {stock:<4} | "
              f"City: {p['city'] or 'N/A'}")
    print("-" * 80)


def delete_product_cmd(product_id: int):
    """Delete (deactivate) a product"""
    product = db.get_product(product_id)
    if not product:
        print(f"❌ Product {product_id} not found")
        return
    
    if db.delete_product(product_id):
        print(f"✅ Product deleted: {product['name']} (ID: {product_id})")
    else:
        print(f"❌ Error deleting product")


def activate_product_cmd(product_id: int):
    """Activate a product"""
    product = db.get_product(product_id)
    if not product:
        print(f"❌ Product {product_id} not found")
        return
    
    if db.update_product(product_id, is_active=1):
        print(f"✅ Product activated: {product['name']} (ID: {product_id})")
    else:
        print(f"❌ Error activating product")


def add_balance_cmd(telegram_id: int, amount: float):
    """Add balance to a user"""
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        print(f"❌ User {telegram_id} not found")
        return
    
    db.update_balance(user['id'], amount)
    new_balance = db.get_user_by_id(user['id'])['balance_sol']
    
    print(f"✅ Balance updated for @{user['username'] or telegram_id}")
    print(f"   Added: {amount:.6f} SOL")
    print(f"   New balance: {new_balance:.6f} SOL")


def ban_user_cmd(telegram_id: int):
    """Ban a user"""
    if db.ban_user(telegram_id):
        print(f"✅ User {telegram_id} banned")
    else:
        print(f"❌ User not found")


def unban_user_cmd(telegram_id: int):
    """Unban a user"""
    if db.unban_user(telegram_id):
        print(f"✅ User {telegram_id} unbanned")
    else:
        print(f"❌ User not found")


def recent_transactions(limit: int = 20):
    """Show recent transactions"""
    transactions = db.get_recent_transactions(limit=limit)
    
    if not transactions:
        print("No transactions found")
        return
    
    print(f"\n💰 Recent Transactions (last {len(transactions)}):")
    print("-" * 90)
    for tx in transactions:
        date = datetime.fromtimestamp(tx['created_at']).strftime('%Y-%m-%d %H:%M')
        tx_type_emoji = {
            'deposit': '📥',
            'purchase': '🛍️',
            'referral_bonus': '🎁'
        }.get(tx['tx_type'], '💸')
        
        print(f"{tx_type_emoji} {tx['amount_sol']:>10.6f} SOL | "
              f"@{tx['username'] or str(tx['telegram_id']):<15} | "
              f"{tx['tx_type']:<15} | {date}")
    print("-" * 90)


def backup_database(output_path: str = None):
    """Create a database backup"""
    import shutil
    from datetime import datetime
    
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"backups/shop_{timestamp}.db"
    
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    shutil.copy2("shop.db", output_path)
    print(f"✅ Database backed up to: {output_path}")
    
    # Also backup keypairs
    keypairs_backup = output_path.replace('.db', '_keypairs.json')
    if os.path.exists('user_keypairs.json'):
        shutil.copy2("user_keypairs.json", keypairs_backup)
        print(f"✅ Keypairs backed up to: {keypairs_backup}")


def set_setting_cmd(key: str, value: str):
    """Set a configuration setting"""
    if db.set_setting(key, value):
        print(f"✅ Setting updated: {key} = {value}")
    else:
        print(f"❌ Error updating setting")


def get_setting_cmd(key: str):
    """Get a configuration setting"""
    value = db.get_setting(key)
    if value:
        print(f"{key} = {value}")
    else:
        print(f"❌ Setting not found: {key}")


def main():
    parser = argparse.ArgumentParser(
        description='Vanity Shop Bot Management Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage.py stats
  python manage.py add-admin 123456789 username
  python manage.py list-users --limit 20
  python manage.py add-balance 123456789 0.5
  python manage.py backup
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Stats command
    subparsers.add_parser('stats', help='Show bot statistics')
    
    # Admin commands
    admin_add = subparsers.add_parser('add-admin', help='Add admin user')
    admin_add.add_argument('telegram_id', type=int, help='Telegram user ID')
    admin_add.add_argument('username', nargs='?', help='Username (optional)')
    
    admin_remove = subparsers.add_parser('remove-admin', help='Remove admin user')
    admin_remove.add_argument('telegram_id', type=int, help='Telegram user ID')
    
    subparsers.add_parser('list-admins', help='List all admins')
    
    # User commands
    users_list = subparsers.add_parser('list-users', help='List users')
    users_list.add_argument('--limit', type=int, default=10, help='Number of users to show')
    users_list.add_argument('--search', type=str, help='Search term')
    
    balance_add = subparsers.add_parser('add-balance', help='Add balance to user')
    balance_add.add_argument('telegram_id', type=int, help='Telegram user ID')
    balance_add.add_argument('amount', type=float, help='Amount in SOL')
    
    ban = subparsers.add_parser('ban-user', help='Ban a user')
    ban.add_argument('telegram_id', type=int, help='Telegram user ID')
    
    unban = subparsers.add_parser('unban-user', help='Unban a user')
    unban.add_argument('telegram_id', type=int, help='Telegram user ID')
    
    # Product commands
    subparsers.add_parser('list-products', help='List all products')
    
    delete_product = subparsers.add_parser('delete-product', help='Delete (deactivate) a product')
    delete_product.add_argument('product_id', type=int, help='Product ID')
    
    activate_product = subparsers.add_parser('activate-product', help='Activate a product')
    activate_product.add_argument('product_id', type=int, help='Product ID')
    
    # Transaction commands
    txs = subparsers.add_parser('transactions', help='Show recent transactions')
    txs.add_argument('--limit', type=int, default=20, help='Number of transactions')
    
    # Backup command
    backup = subparsers.add_parser('backup', help='Backup database and keypairs')
    backup.add_argument('--output', type=str, help='Output path (optional)')
    
    # Settings commands
    set_setting = subparsers.add_parser('set-setting', help='Set configuration')
    set_setting.add_argument('key', type=str, help='Setting key')
    set_setting.add_argument('value', type=str, help='Setting value')
    
    get_setting = subparsers.add_parser('get-setting', help='Get configuration')
    get_setting.add_argument('key', type=str, help='Setting key')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database
    db.init_db()
    
    # Execute command
    try:
        if args.command == 'stats':
            stats()
        elif args.command == 'add-admin':
            add_admin(args.telegram_id, args.username)
        elif args.command == 'remove-admin':
            remove_admin(args.telegram_id)
        elif args.command == 'list-admins':
            list_admins()
        elif args.command == 'list-users':
            list_users(args.limit, args.search)
        elif args.command == 'add-balance':
            add_balance_cmd(args.telegram_id, args.amount)
        elif args.command == 'ban-user':
            ban_user_cmd(args.telegram_id)
        elif args.command == 'unban-user':
            unban_user_cmd(args.telegram_id)
        elif args.command == 'list-products':
            list_products()
        elif args.command == 'transactions':
            recent_transactions(args.limit)
        elif args.command == 'backup':
            backup_database(args.output)
        elif args.command == 'set-setting':
            set_setting_cmd(args.key, args.value)
        elif args.command == 'get-setting':
            get_setting_cmd(args.key)
        else:
            parser.print_help()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()