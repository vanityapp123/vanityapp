# bot.py
"""
Vanity Shop main bot file - Enhanced with Anonymous Referral System
- Full referral system with anonymous codes
- Enhanced /alert command for broadcasting
- Referral button with rules
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo, ParseMode
)

import db
import payments

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

# ---------- Config ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN not set in environment")
    raise SystemExit("BOT_TOKEN not set")

BOT_USERNAME = "vanityshopbot"

# ---------- Bot & Dispatcher ----------
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)

# ---------- Constants ----------
MEDIA_ROOT = "/root/locimg"
CITIES = ["Debrecen", "Miskolc", "Nyíregyháza", "Budapest-Keleti"]

# ---------- Alert State ----------
alert_states = {}

# ---------- Helpers / Keyboards ----------
def make_main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for i in range(0, len(CITIES), 2):
        row = [InlineKeyboardButton(c, callback_data=f"city:{c}") for c in CITIES[i:i+2]]
        kb.row(*row)
    kb.row(
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
        InlineKeyboardButton("📦 My Orders", callback_data="my_orders")
    )
    kb.add(InlineKeyboardButton("🎁 Referral", callback_data="referral_info"))
    kb.add(InlineKeyboardButton("🎁 Stuff", url=db.get_setting("stuff_link", "https://t.me/+oQMNK45adl9hNzk0")))
    kb.add(InlineKeyboardButton("💬 Support", url=db.get_setting("support_link", "https://t.me/vanitysupport")))
    return kb

def make_back_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
    return kb

async def safe_send_message(chat_id: int, text: str, **kwargs):
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception:
        await bot.send_message(chat_id, text)

# ---------- Command: /start ----------
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    try:
        args = message.get_args() or ""
        referred_by = None
        
        # Try to decode referral code
        if args:
            try:
                referred_by = db.decode_referral_code(args)
                logger.info(f"Decoded referral code {args} -> user_id {referred_by}")
            except Exception as e:
                logger.error(f"Error decoding referral code {args}: {e}")
                referred_by = None

        user = db.get_or_create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            referred_by=referred_by
        )

        if user and user.get("is_banned"):
            await message.answer("❌ You are banned.")
            return

        if user and not user.get("deposit_address"):
            try:
                payments.get_or_create_deposit_address(user["id"])
            except Exception as e:
                logger.exception("Failed to create deposit address for user %s: %s", user["id"], e)

        welcome_text = "🌟 <b>VANITY SHOP</b>\n\nChoose a city to browse products:"
        
        # Show referral bonus if they were referred
        if referred_by and user.get("referred_by"):
            welcome_text = "🎉 <b>Welcome! You joined via referral!</b>\n\n" \
                          "✅ You get <b>5% OFF</b> on all purchases!\n" \
                          "✅ Your referrer gets <b>5% commission</b>!\n\n" \
                          "🌟 <b>VANITY SHOP</b>\n\nChoose a city to browse products:"

        await message.answer(welcome_text, reply_markup=make_main_menu_kb())
    except Exception as e:
        logger.exception("Error in /start: %s", e)
        await message.answer("⚠️ Error. Try again later.")

# ---------- Command: /alert (Enhanced) ----------
@dp.message_handler(commands=["alert"])
async def cmd_alert(message: types.Message):
    if not db.is_admin(message.from_user.id):
        return
    
    alert_states[message.from_user.id] = {"messages": []}
    await message.answer(
        "📢 <b>Alert Mode Activated</b>\n\n"
        "Send any messages (text, photos, videos, locations) you want to broadcast.\n"
        "When done, send /send to broadcast to all users.\n"
        "Send /cancel to cancel.",
        parse_mode="HTML"
    )

@dp.message_handler(commands=["send"])
async def cmd_send_alert(message: types.Message):
    if not db.is_admin(message.from_user.id):
        return
    
    state = alert_states.get(message.from_user.id)
    if not state or not state.get("messages"):
        await message.answer("❌ No messages to send. Use /alert first.")
        return
    
    users = db.get_all_users(limit=10000)
    success = 0
    failed = 0
    
    await message.answer(f"📤 Broadcasting to {len(users)} users...")
    
    for user in users:
        try:
            for msg in state["messages"]:
                await bot.copy_message(
                    chat_id=user["telegram_id"],
                    from_chat_id=message.chat.id,
                    message_id=msg
                )
            success += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {user['telegram_id']}: {e}")
    
    alert_states.pop(message.from_user.id, None)
    await message.answer(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML"
    )

@dp.message_handler(commands=["cancel"])
async def cmd_cancel_alert(message: types.Message):
    if message.from_user.id in alert_states:
        alert_states.pop(message.from_user.id)
        await message.answer("❌ Alert cancelled.")

@dp.message_handler(lambda m: m.from_user.id in alert_states, content_types=types.ContentTypes.ANY)
async def collect_alert_messages(message: types.Message):
    state = alert_states.get(message.from_user.id)
    if state is not None:
        state["messages"].append(message.message_id)
        await message.answer(
            f"✅ Message added ({len(state['messages'])} total)\n\n"
            "Send more messages or /send to broadcast."
        )

# ---------- Callback: Back to main menu ----------
@dp.callback_query_handler(lambda c: c.data == "back")
async def callback_back_to_main(c: types.CallbackQuery):
    try:
        await c.answer()
        await c.message.edit_text("🌟 <b>VANITY SHOP</b>\n\nChoose a city to browse products:", reply_markup=make_main_menu_kb())
    except Exception as e:
        logger.exception("Error in back callback: %s", e)
        try:
            await bot.send_message(c.from_user.id, "🌟 <b>VANITY SHOP</b>\n\nChoose a city to browse products:", reply_markup=make_main_menu_kb())
        except Exception:
            pass

# ---------- Referral Info ----------
@dp.callback_query_handler(lambda c: c.data == "referral_info")
async def referral_info_handler(c: types.CallbackQuery):
    try:
        await c.answer()
        user = db.get_user_by_telegram_id(c.from_user.id)
        if not user:
            await c.message.edit_text("❌ User not found. Please /start first.")
            return
        
        # Generate anonymous referral code
        ref_code = db.generate_referral_code(user['id'])
        ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
        
        # Get referral stats with error handling
        try:
            stats = db.get_referral_stats(user["id"])
        except Exception as e:
            logger.error(f"Error getting referral stats: {e}")
            stats = {'referred_count': 0, 'total_earnings': 0.0, 'referral_purchases': 0}
        
        text = (
            "🎁 <b>Referral Program</b>\n\n"
            "📋 <b>How it works:</b>\n"
            "• Share your referral link\n"
            "• Your friends get <b>5% OFF</b> all purchases\n"
            "• You get <b>5% commission</b> on their purchases\n"
            "• You also get <b>5% bonus</b> on their deposits\n\n"
            f"🔗 <b>Your Referral Link:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"📊 <b>Your Stats:</b>\n"
            f"👥 Referred Users: {stats['referred_count']}\n"
            f"💰 Total Earnings: {stats['total_earnings']:.6f} SOL\n"
            f"🛍️ Purchases by Referrals: {stats['referral_purchases']}"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={ref_link}&text=Join%20Vanity%20Shop%20and%20get%205%25%20off!"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
        
        await c.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("Error in referral_info_handler: %s", e)
        await c.answer("⚠️ Error loading referral info. Please try again.", show_alert=True)

# ---------- City listing ----------
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("city:"))
async def city_handler(c: types.CallbackQuery):
    try:
        city = c.data.split(":", 1)[1]
        products = db.get_products(city=city, active_only=True)
        kb = InlineKeyboardMarkup(row_width=1)
        if not products:
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
            await c.message.edit_text(f"🏙️ <b>{city}</b>\n\nNo products yet.", reply_markup=kb)
            return

        for p in products:
            stock = "" if p["stock"] == -1 else (" [SOLD OUT]" if p["stock"] == 0 else f" [{p['stock']} left]")
            kb.add(InlineKeyboardButton(f"{p['name']} – {p['price_sol']} SOL{stock}", callback_data=f"product:{p['id']}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
        await c.message.edit_text(f"🏙️ <b>{city}</b>\nSelect a product:", reply_markup=kb)
    except Exception as e:
        logger.exception("Error in city_handler: %s", e)
        await c.answer("⚠️ Error")

# ---------- Product view ----------
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("product:"))
async def product_view(c: types.CallbackQuery):
    try:
        pid = int(c.data.split(":", 1)[1])
        product = db.get_product(pid)
        if not product or not product.get("is_active", 1):
            await c.message.edit_text("❌ Product unavailable.")
            return

        user = db.get_user_by_telegram_id(c.from_user.id)
        desc = product.get("description") or "No description."
        stock = f"\n📦 Stock: {product['stock']}" if product.get("stock", -1) != -1 else ""
        
        # Calculate price with discount
        price = product['price_sol']
        discount_text = ""
        if user and user.get("referred_by"):
            discount = price * 0.05
            discounted_price = price - discount
            discount_text = f"\n🎉 <b>Referral Discount: -{discount:.6f} SOL (5%)</b>\n💰 <b>Your Price: {discounted_price:.6f} SOL</b>"
            price = discounted_price
        
        text = (f"🛍️ <b>{product['name']}</b>\n\n"
                f"{desc}\n🏙 {product.get('city','')}{stock}\n\n"
                f"💰 <b>Regular Price: {product['price_sol']:.6f} SOL</b>{discount_text}")
        
        kb = InlineKeyboardMarkup()
        if user and user.get("balance_sol", 0) >= price:
            kb.add(InlineKeyboardButton("✅ Buy", callback_data=f"buy:{pid}"))
        else:
            kb.add(InlineKeyboardButton("⚠️ Not enough SOL", callback_data="balance"))
        kb.row(InlineKeyboardButton("🔙 Back", callback_data="back"),
               InlineKeyboardButton("💰 Deposit", callback_data="balance"))
        await c.message.edit_text(text, reply_markup=kb)
    except Exception as e:
        logger.exception("Error in product_view: %s", e)
        await c.answer("⚠️ Error")

# ---------- Buy ----------
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("buy:"))
async def buy_handler(c: types.CallbackQuery):
    try:
        pid = int(c.data.split(":", 1)[1])
        user = db.get_user_by_telegram_id(c.from_user.id)
        product = db.get_product(pid)
        
        if not product:
            await c.message.edit_text("❌ Product not found.")
            return
        
        # Calculate final price
        final_price = product["price_sol"]
        referrer_id = None
        
        if user.get("referred_by"):
            discount = final_price * 0.05
            final_price = final_price - discount
            referrer_id = user["referred_by"]
        
        if user["balance_sol"] < final_price:
            await c.message.edit_text("❌ Not enough SOL.")
            return

        # Deduct balance
        db.update_balance(user["id"], -final_price)
        
        # Update stock
        if product.get("stock", -1) != -1:
            db.decrease_stock(pid)
        
        # Create order
        order_id = db.create_order(user["id"], pid, final_price)
        db.record_transaction(user["id"], f"order_{order_id}", final_price, "purchase", order_id)
        
        # Give commission to referrer
        if referrer_id:
            commission = product["price_sol"] * 0.05
            db.update_balance(referrer_id, commission)
            db.record_transaction(referrer_id, f"ref_purchase_{order_id}", commission, "referral_commission", order_id)
            
            # Notify referrer
            try:
                referrer = db.get_user_by_id(referrer_id)
                if referrer:
                    await bot.send_message(
                        referrer["telegram_id"],
                        f"🎉 <b>Referral Commission!</b>\n\n"
                        f"Your referral made a purchase!\n"
                        f"💰 You earned: <b>{commission:.6f} SOL</b>\n\n"
                        f"New balance: <b>{referrer['balance_sol']:.6f} SOL</b>",
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Failed to notify referrer: {e}")

        # Deliver product
        await deliver_product(c.from_user.id, pid, order_id)
        await c.message.edit_text("✅ Purchase complete. Product delivered!")
    except Exception as e:
        logger.exception("Error in buy_handler: %s", e)
        await c.answer("⚠️ Error during purchase")

# ---------- Balance ----------
@dp.callback_query_handler(lambda c: c.data == "balance")
async def balance_handler(c: types.CallbackQuery):
    try:
        user = db.get_user_by_telegram_id(c.from_user.id)
        if not user:
            await c.answer("❌ User not found")
            return
        addr = user.get("deposit_address") or payments.get_or_create_deposit_address(user["id"])
        
        # Generate anonymous referral code
        ref_code = db.generate_referral_code(user['id'])
        ref = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
        
        # Get referral earnings
        earnings = user.get("referral_earnings", 0) or 0.0
        
        text = (f"💰 Balance: <b>{user['balance_sol']:.6f} SOL</b>\n\n"
                f"Deposit address:(Click to Copy) <code>{addr}</code>\n\n"
                f"🎁 Referral Earnings: <b>{earnings:.6f} SOL</b>\n"
                f"Referral Link: <code>{ref}</code>")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎁 Referral Info", callback_data="referral_info"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
        await c.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("Error in balance_handler: %s", e)
        await c.answer("⚠️ Error")

# ---------- My orders ----------
@dp.callback_query_handler(lambda c: c.data == "my_orders")
async def my_orders_handler(c: types.CallbackQuery):
    try:
        user = db.get_user_by_telegram_id(c.from_user.id)
        if not user:
            await c.answer("❌ User not found")
            return
        orders = db.get_user_orders(user["id"], limit=20)
        if not orders:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back"))
            await c.message.edit_text("You have no orders yet.", reply_markup=kb)
            return
        lines = []
        for o in orders:
            lines.append(f"• {o['order_id']} – {o['product_name']} – {o['price_sol']} SOL – {o.get('status','')}")
        text = "<b>Your Orders</b>\n\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="back"))
        await c.message.edit_text(text, reply_markup=kb)
    except Exception as e:
        logger.exception("Error in my_orders_handler: %s", e)
        await c.answer("⚠️ Error")

# ---------- Delivery ----------
async def deliver_product(telegram_id: int, product_id: int, order_id: str):
    try:
        product = db.get_product(product_id)
        if not product:
            await bot.send_message(telegram_id, "❌ Product not found.")
            return

        folder = os.path.join(MEDIA_ROOT, f"product_{product_id}")
        if not os.path.exists(folder):
            await bot.send_message(telegram_id, "⚠️ No media folder for this product.")
            db.mark_order_delivered(order_id)
            return

        files_all = sorted([f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".mp4"))])
        if not files_all:
            await bot.send_message(telegram_id, "⚠️ No media files found for this product.")
            db.mark_order_delivered(order_id)
            return

        images = [f for f in files_all if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        videos = [f for f in files_all if f.lower().endswith(".mp4")]

        chosen = []
        for im in images:
            chosen.append(im)
            if len(chosen) == 2:
                break
        if len(chosen) < 2:
            for v in videos:
                chosen.append(v)
                if len(chosen) == 2:
                    break

        if not chosen:
            await bot.send_message(telegram_id, "⚠️ No suitable media to send.")
            db.mark_order_delivered(order_id)
            return

        opened_files = []
        media_group = []
        for idx, fname in enumerate(chosen):
            path = os.path.join(folder, fname)
            fobj = open(path, "rb")
            opened_files.append(fobj)
            caption = f"<b>{product['name']}</b>" if idx == 0 else None
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                if caption:
                    media_group.append(InputMediaPhoto(fobj, caption=caption))
                else:
                    media_group.append(InputMediaPhoto(fobj))
            else:
                if caption:
                    media_group.append(InputMediaVideo(fobj, caption=caption))
                else:
                    media_group.append(InputMediaVideo(fobj))

        if len(media_group) == 1:
            item = media_group[0]
            if isinstance(item, InputMediaPhoto):
                await bot.send_photo(telegram_id, item.media, caption=(item.caption or None), parse_mode=ParseMode.HTML if item.caption else None)
            else:
                await bot.send_video(telegram_id, item.media, caption=(item.caption or None), parse_mode=ParseMode.HTML if item.caption else None)
        else:
            await bot.send_media_group(chat_id=telegram_id, media=media_group)

        for fo in opened_files:
            try:
                fo.close()
            except Exception:
                pass

        location = product.get("location")
        if location:
            try:
                loc_clean = location.replace(" ", "").replace("lat:", "").replace("lon:", "")
                lat_str, lon_str = loc_clean.split(",", 1)
                lat, lon = float(lat_str), float(lon_str)
                await bot.send_location(telegram_id, latitude=lat, longitude=lon)
            except Exception as e:
                logger.info("Failed to parse location for product %s: %s", product_id, location)

        db.mark_order_delivered(order_id)
        logger.info("Delivered product %s to user %s", product_id, telegram_id)

    except Exception as e:
        logger.exception("Error in deliver_product: %s", e)
        try:
            await bot.send_message(telegram_id, "⚠️ Error delivering your product. Contact support.")
        except Exception:
            pass

# ---------- Startup & Shutdown ----------
async def on_startup(dp):
    try:
        db.init_db()
    except Exception as e:
        logger.exception("Failed to init DB: %s", e)

    try:
        import admin as admin_module
        admin_module.register_admin_handlers(dp)
        logger.info("✅ Admin handlers registered")
    except Exception as e:
        logger.exception("Failed to register admin handlers: %s", e)

    try:
        asyncio.create_task(payments.payment_monitor_loop(bot))
    except Exception as e:
        logger.exception("Failed to start payments monitor: %s", e)

async def on_shutdown(dp):
    try:
        await bot.session.close()
    except Exception:
        pass

# ---------- Run ----------
if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)