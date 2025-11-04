# admin.py
"""
Admin panel for Vanity Shop - Enhanced with Referral Dashboard
"""

import os
import time
import logging
from datetime import datetime
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import Dispatcher
import db

logger = logging.getLogger(__name__)

MEDIA_ROOT = "/root/locimg"

# ========== UTILITIES ==========

def admin_main_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Add Product", callback_data="admin_add_product"),
        InlineKeyboardButton("📝 Edit Product", callback_data="admin_edit_product")
    )
    kb.add(
        InlineKeyboardButton("❌ Delete Product", callback_data="admin_delete_product"),
        InlineKeyboardButton("📸 Link Media", callback_data="admin_link_media")
    )
    kb.add(
        InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        InlineKeyboardButton("🎁 Referrals", callback_data="admin_referrals")
    )
    kb.add(
        InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage_admins")
    )
    return kb

def product_list_kb(action_prefix="edit"):
    kb = InlineKeyboardMarkup(row_width=1)
    products = db.get_products(active_only=False)
    for p in products:
        kb.add(InlineKeyboardButton(f"{p['id']} – {p['name']}", callback_data=f"admin_{action_prefix}:{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_main"))
    return kb

# ========== HANDLERS ==========

def register_admin_handlers(dp: Dispatcher):
    """Register all admin handlers on dispatcher"""

    @dp.message_handler(commands=["admin"])
    async def cmd_admin(message: types.Message):
        user_id = message.from_user.id
        if not db.is_admin(user_id):
            await message.answer("❌ You are not an admin.")
            return
        await message.answer("👑 <b>Admin Panel</b>", parse_mode="HTML", reply_markup=admin_main_kb())

    # --- Navigation back to main admin menu ---
    @dp.callback_query_handler(lambda c: c.data == "admin_main")
    async def admin_main_cb(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            await c.answer("Not admin")
            return
        await c.message.edit_text("👑 <b>Admin Panel</b>", parse_mode="HTML", reply_markup=admin_main_kb())

    # --- Add product ---
    admin_states = {}

    @dp.callback_query_handler(lambda c: c.data == "admin_add_product")
    async def add_product_start(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        admin_states[c.from_user.id] = {"step": "name"}
        await c.message.edit_text("🆕 Enter product name:")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "name")
    async def add_product_name(message: types.Message):
        state = admin_states[message.from_user.id]
        state["name"] = message.text
        state["step"] = "desc"
        await message.answer("✏️ Enter description:")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "desc")
    async def add_product_desc(message: types.Message):
        state = admin_states[message.from_user.id]
        state["desc"] = message.text
        state["step"] = "price"
        await message.answer("💰 Enter price (SOL):")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "price")
    async def add_product_price(message: types.Message):
        state = admin_states[message.from_user.id]
        try:
            price = float(message.text)
        except ValueError:
            await message.answer("❌ Invalid price. Enter a number.")
            return
        state["price"] = price
        state["step"] = "city"
        await message.answer("🏙️ Enter city:")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "city")
    async def add_product_city(message: types.Message):
        state = admin_states[message.from_user.id]
        state["city"] = message.text
        state["step"] = "location"
        await message.answer("📍 Enter location coordinates (lat,lon):")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "location")
    async def add_product_location(message: types.Message):
        state = admin_states.pop(message.from_user.id)
        location = message.text
        pid = db.create_product(
            name=state["name"],
            price_sol=state["price"],
            description=state["desc"],
            city=state["city"],
            location=location,
            stock=-1
        )
        folder = os.path.join(MEDIA_ROOT, f"product_{pid}")
        os.makedirs(folder, exist_ok=True)
        await message.answer(f"✅ Product <b>{state['name']}</b> added (ID: {pid})\n"
                             f"Folder created: {folder}", parse_mode="HTML")

    # --- Edit product ---
    @dp.callback_query_handler(lambda c: c.data == "admin_edit_product")
    async def edit_product_menu(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        await c.message.edit_text("✏️ Select a product to edit:", reply_markup=product_list_kb("editid"))

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_editid:"))
    async def edit_product_select(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        pid = int(c.data.split(":", 1)[1])
        product = db.get_product(pid)
        if not product:
            await c.answer("Not found")
            return
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("💰 Edit Price", callback_data=f"admin_editprice:{pid}"),
            InlineKeyboardButton("📦 Edit Stock", callback_data=f"admin_editstock:{pid}")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_edit_product"))
        await c.message.edit_text(
            f"Editing <b>{product['name']}</b>\nPrice: {product['price_sol']}\nStock: {product['stock']}",
            parse_mode="HTML", reply_markup=kb
        )

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_editprice:"))
    async def edit_price_start(c: types.CallbackQuery):
        pid = int(c.data.split(":", 1)[1])
        admin_states[c.from_user.id] = {"step": "edit_price", "pid": pid}
        await c.message.edit_text("💰 Enter new price:")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "edit_price")
    async def edit_price_set(message: types.Message):
        try:
            price = float(message.text)
        except ValueError:
            await message.answer("❌ Invalid number.")
            return
        pid = admin_states.pop(message.from_user.id)["pid"]
        db.update_product(pid, price_sol=price)
        await message.answer("✅ Price updated successfully.")

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_editstock:"))
    async def edit_stock_start(c: types.CallbackQuery):
        pid = int(c.data.split(":", 1)[1])
        admin_states[c.from_user.id] = {"step": "edit_stock", "pid": pid}
        await c.message.edit_text("📦 Enter new stock (-1 for unlimited):")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "edit_stock")
    async def edit_stock_set(message: types.Message):
        try:
            stock = int(message.text)
        except ValueError:
            await message.answer("❌ Invalid number.")
            return
        pid = admin_states.pop(message.from_user.id)["pid"]
        db.update_product(pid, stock=stock)
        await message.answer("✅ Stock updated successfully.")

    # --- Delete product ---
    @dp.callback_query_handler(lambda c: c.data == "admin_delete_product")
    async def delete_product_menu(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        await c.message.edit_text("❌ Select a product to delete:", reply_markup=product_list_kb("deleteid"))

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_deleteid:"))
    async def delete_product_confirm(c: types.CallbackQuery):
        pid = int(c.data.split(":", 1)[1])
        product = db.get_product(pid)
        if not product:
            await c.answer("Not found")
            return
        db.delete_product(pid)
        await c.message.edit_text(f"✅ Deleted <b>{product['name']}</b>", parse_mode="HTML")

    # --- Link Media ---
    @dp.callback_query_handler(lambda c: c.data == "admin_link_media")
    async def link_media_start(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        await c.message.edit_text("📸 Select a product to view its media folder:", reply_markup=product_list_kb("mediaid"))

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_mediaid:"))
    async def show_media_folder(c: types.CallbackQuery):
        pid = int(c.data.split(":", 1)[1])
        folder = os.path.join(MEDIA_ROOT, f"product_{pid}")
        os.makedirs(folder, exist_ok=True)
        await c.message.edit_text(f"📁 Folder for product {pid}:\n<code>{folder}</code>\n\n"
                                  f"Upload 2 media files manually there (jpg/png/mp4).",
                                  parse_mode="HTML")

    # --- Stats ---
    @dp.callback_query_handler(lambda c: c.data == "admin_stats")
    async def admin_stats(c: types.CallbackQuery):
        s = db.get_stats()
        text = (f"📊 <b>Statistics</b>\n\n"
                f"👥 Users: {s['total_users']} (+{s['new_users_today']} today)\n"
                f"🛍️ Orders: {s['total_orders']} (+{s['orders_today']} today)\n"
                f"💰 Revenue: {s['total_revenue']:.2f} SOL (+{s['revenue_today']:.2f} today)\n"
                f"💵 Deposits: {s['total_deposits']:.2f} SOL\n\n"
                f"🎁 <b>Referral Stats:</b>\n"
                f"👥 Total Referrals: {s['total_referrals']}\n"
                f"💰 Total Ref. Earnings: {s['total_referral_earnings']:.6f} SOL")
        await c.message.edit_text(text, parse_mode="HTML", reply_markup=admin_main_kb())

    # --- REFERRALS DASHBOARD ---
    @dp.callback_query_handler(lambda c: c.data == "admin_referrals")
    async def admin_referrals_menu(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📋 All Referrals", callback_data="admin_ref_all"),
            InlineKeyboardButton("🏆 Top Referrers", callback_data="admin_ref_top")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_main"))
        
        stats = db.get_stats()
        text = (f"🎁 <b>Referral Dashboard</b>\n\n"
                f"👥 Total Referred Users: {stats['total_referrals']}\n"
                f"💰 Total Referral Earnings: {stats['total_referral_earnings']:.6f} SOL\n\n"
                f"Select an option:")
        
        await c.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query_handler(lambda c: c.data == "admin_ref_all")
    async def admin_ref_all(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        
        referrals = db.get_all_referrals()
        
        if not referrals:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_referrals"))
            await c.message.edit_text("No referrals yet.", reply_markup=kb)
            return
        
        # Paginate results
        page_size = 10
        total_pages = (len(referrals) + page_size - 1) // page_size
        
        # For now, show first page
        page_referrals = referrals[:page_size]
        
        lines = ["📋 <b>All Referrals</b> (Latest)\n"]
        for ref in page_referrals:
            date = datetime.fromtimestamp(ref['created_at']).strftime('%Y-%m-%d')
            lines.append(
                f"👤 @{ref['username'] or ref['telegram_id']}\n"
                f"  Referred by: @{ref['referrer_username'] or 'Unknown'}\n"
                f"  Balance: {ref['balance_sol']:.6f} SOL\n"
                f"  Purchases: {ref['purchase_count']} ({ref['total_spent']:.6f} SOL)\n"
                f"  Joined: {date}\n"
            )
        
        text = "\n".join(lines)
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_referrals"))
        
        await c.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query_handler(lambda c: c.data == "admin_ref_top")
    async def admin_ref_top(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        
        top_referrers = db.get_top_referrers(limit=10)
        
        if not top_referrers:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_referrals"))
            await c.message.edit_text("No referrers yet.", reply_markup=kb)
            return
        
        lines = ["🏆 <b>Top Referrers</b>\n"]
        for idx, ref in enumerate(top_referrers, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            lines.append(
                f"{medal} @{ref['username'] or ref['telegram_id']}\n"
                f"  💰 Earnings: {ref['referral_earnings']:.6f} SOL\n"
                f"  👥 Referred: {ref['referred_count']} users\n"
                f"  📊 Total Revenue: {ref['total_referral_revenue']:.6f} SOL\n"
            )
        
        text = "\n".join(lines)
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_referrals"))
        
        await c.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

    # --- Manage Admins ---
    @dp.callback_query_handler(lambda c: c.data == "admin_manage_admins")
    async def manage_admins_menu(c: types.CallbackQuery):
        if not db.is_admin(c.from_user.id):
            return
        admins = db.get_all_admins()
        lines = [f"• {a['username']} ({a['telegram_id']})" for a in admins]
        text = "👥 <b>Current Admins</b>\n\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("➕ Add Admin", callback_data="admin_add_admin"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="admin_remove_admin")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_main"))
        await c.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query_handler(lambda c: c.data == "admin_add_admin")
    async def add_admin_start(c: types.CallbackQuery):
        admin_states[c.from_user.id] = {"step": "add_admin"}
        await c.message.edit_text("👤 Enter Telegram ID to add as admin:")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "add_admin")
    async def add_admin_id(message: types.Message):
        try:
            tid = int(message.text.strip())
            db.add_admin(tid)
            await message.answer("✅ Admin added.")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
        admin_states.pop(message.from_user.id, None)

    @dp.callback_query_handler(lambda c: c.data == "admin_remove_admin")
    async def remove_admin_start(c: types.CallbackQuery):
        admin_states[c.from_user.id] = {"step": "remove_admin"}
        await c.message.edit_text("👤 Enter Telegram ID to remove from admins:")

    @dp.message_handler(lambda m: m.from_user.id in admin_states and admin_states[m.from_user.id]["step"] == "remove_admin")
    async def remove_admin_id(message: types.Message):
        try:
            tid = int(message.text.strip())
            db.remove_admin(tid)
            await message.answer("✅ Admin removed.")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
        admin_states.pop(message.from_user.id, None)

    logger.info("✅ Admin panel loaded successfully with referral dashboard")
