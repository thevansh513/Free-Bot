import os
import requests
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from storage import UserDataStorage

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
    
ADMIN_ID = int(os.environ.get('ADMIN_ID', '7981712298'))
ORDER_API_URL = "https://testuser2.onrender.com/order"
ADS_SCRIPT = "https://libtl.com/sdk.js?zone=9870348&sdk=show_9870348"

# Initialize storage
storage = UserDataStorage()

# Main menu keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["🪧 Watch Ads", "👥 Refer & Earn"],
    ["📦 Buy Views", "💳 Balance"],
    ["📞 Contact Admin"]
], resize_keyboard=True)

# User states for conversation flow
user_states = {}
WAITING_FOR_VIDEO_LINK = "waiting_for_video_link"
WAITING_FOR_QUANTITY = "waiting_for_quantity"
WAITING_FOR_BROADCAST = "waiting_for_broadcast"

# Rate limiting for ads (simple in-memory tracking)
user_last_ad_time = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    # Check if user came from referral link
    referral_code = None
    if context.args:
        referral_code = context.args[0]
    
    # Create user if new
    is_new_user = storage.create_user(user_id, user.username, user.first_name)
    
    # Process referral if applicable
    if is_new_user and referral_code:
        if storage.process_referral(user_id, referral_code):
            await update.message.reply_text(
                "🎉 Welcome! You've been referred by another user. Both of you received rewards!",
                reply_markup=MAIN_KEYBOARD
            )
        else:
            await update.message.reply_text(
                "👋 Welcome to the bot!",
                reply_markup=MAIN_KEYBOARD
            )
    else:
        await update.message.reply_text(
            "👋 Welcome back to the bot!",
            reply_markup=MAIN_KEYBOARD
        )
    
    storage.update_user_activity(user_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Update user activity
    storage.update_user_activity(user_id)
    
    # Check user state for conversation flow
    if user_id in user_states:
        await handle_user_state(update, context)
        return
    
    # Handle main menu buttons
    if message_text == "🪧 Watch Ads":
        await show_ads(update, context)
    elif message_text == "👥 Refer & Earn":
        await show_referral(update, context)
    elif message_text == "📦 Buy Views":
        await buy_views_start(update, context)
    elif message_text == "💳 Balance":
        await show_balance(update, context)
    elif message_text == "📞 Contact Admin":
        await contact_admin(update, context)
    else:
        await update.message.reply_text(
            "Please use the menu buttons below 👇",
            reply_markup=MAIN_KEYBOARD
        )

async def show_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show ads to user with button to open URL"""
    user_id = update.effective_user.id
    import time
    
    # Simple rate limiting (30 seconds between ads)
    current_time = time.time()
    if user_id in user_last_ad_time:
        time_since_last = current_time - user_last_ad_time[user_id]
        if time_since_last < 30:  # 30 seconds cooldown
            remaining = int(30 - time_since_last)
            await update.message.reply_text(
                f"⏰ Please wait {remaining} seconds before watching another ad.",
                reply_markup=MAIN_KEYBOARD
            )
            return
    
    # Get current stats
    user_data = storage.get_user(user_id)
    ads_watched = user_data.get('ads_watched', 0) if user_data else 0
    
    message = f"📺 **Ad Viewing**\n\n"
    message += f"📊 Total ads watched: {ads_watched}\n"
    message += f"💰 Views earned: {ads_watched // 10}\n"
    message += f"🎯 Next reward in: {10 - (ads_watched % 10)} ads\n\n"
    message += f"🔗 Click 'Open Ad' button below to view the advertisement:\n\n"
    message += "💡 **How it works:**\n"
    message += "• Click 'Open Ad' to view advertisement\n"
    message += "• After viewing, click 'I Watched Ad' to get reward\n"
    message += "• Watch 10 ads = Get 1 view added to your balance\n"
    message += "• 30 seconds cooldown between ads"
    
    # Create inline keyboard with Open Ad button
    keyboard = [
        [InlineKeyboardButton("🔗 Open Ad", url=ADS_SCRIPT)],
        [InlineKeyboardButton("✅ I Watched Ad", callback_data=f"watched_ad_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral information"""
    user_id = update.effective_user.id
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    user_data = storage.get_user(user_id)
    if not user_data:
        await update.message.reply_text("❌ User data not found. Please use /start first.")
        return
    
    referral_link = storage.get_referral_link(user_id, bot_username)
    referrals_count = user_data.get("referrals_count", 0)
    
    message = f"👥 **Referral Program**\n\n"
    message += f"🔗 Your referral link:\n`{referral_link}`\n\n"
    message += f"📊 **Your Stats:**\n"
    message += f"• Total referrals: {referrals_count}\n"
    message += f"• Total earned: {referrals_count * 100} views\n\n"
    message += f"💰 **Rewards:**\n"
    message += f"• +100 views for each new user who joins with your link\n"
    message += f"• Unlimited referrals allowed\n\n"
    message += f"📱 **How to share:**\n"
    message += f"Send your referral link to friends and earn views for each person who joins!"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def buy_views_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buy views process"""
    user_id = update.effective_user.id
    user_states[user_id] = WAITING_FOR_VIDEO_LINK
    
    await update.message.reply_text(
        "📦 **Buy Views**\n\n"
        "Please send me the video link you want to promote:\n\n"
        "💡 Supported platforms:\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Instagram\n"
        "• And more...\n\n"
        "Send /cancel to cancel this process."
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user balance"""
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ User data not found. Please use /start first.")
        return
    
    balance = user_data.get("balance", 0)
    ads_watched = user_data.get("ads_watched", 0)
    referrals_count = user_data.get("referrals_count", 0)
    
    message = f"💳 **Your Balance**\n\n"
    message += f"💰 Available views: **{balance}**\n\n"
    message += f"📊 **Account Summary:**\n"
    message += f"• Ads watched: {ads_watched}\n"
    message += f"• Referrals made: {referrals_count}\n"
    message += f"• Total earned from ads: {ads_watched // 10} views\n"
    message += f"• Total earned from referrals: {referrals_count * 100} views\n\n"
    message += f"🎯 **How to earn more:**\n"
    message += f"• Watch ads (10 ads = 1 view)\n"
    message += f"• Refer friends (+100 views each)\n"
    message += f"• Use your views to promote your content!"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin contact information"""
    message = f"📞 **Contact Admin**\n\n"
    message += f"Need help or have questions?\n\n"
    message += f"💬 Contact our admin:\n"
    message += f"👤 Admin ID: {ADMIN_ID}\n\n"
    message += f"📝 **Common Issues:**\n"
    message += f"• Balance not updating\n"
    message += f"• Order problems\n"
    message += f"• Technical support\n"
    message += f"• Partnership inquiries\n\n"
    message += f"⏰ Response time: Usually within 24 hours"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def handle_user_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user states during conversation flows"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    if message_text == "/cancel":
        user_states.pop(user_id, None)
        await update.message.reply_text(
            "❌ Process cancelled.",
            reply_markup=MAIN_KEYBOARD
        )
        return
    
    state = user_states.get(user_id)
    
    if state == WAITING_FOR_VIDEO_LINK:
        # Store video link and ask for quantity
        context.user_data['video_link'] = message_text
        user_states[user_id] = WAITING_FOR_QUANTITY
        
        user_data = storage.get_user(user_id)
        balance = user_data.get("balance", 0)
        
        await update.message.reply_text(
            f"✅ Video link received!\n\n"
            f"💰 Your current balance: {balance} views\n\n"
            f"📦 How many views do you want to buy?\n"
            f"💡 1 view = 1 balance point\n\n"
            f"Enter a number (e.g., 100, 500, 1000):"
        )
    
    elif state == WAITING_FOR_QUANTITY:
        try:
            quantity = int(message_text)
            if quantity <= 0:
                await update.message.reply_text("❌ Please enter a positive number.")
                return
            
            user_data = storage.get_user(user_id)
            balance = user_data.get("balance", 0)
            
            if quantity > balance:
                await update.message.reply_text(
                    f"❌ Insufficient balance!\n\n"
                    f"💰 Your balance: {balance} views\n"
                    f"📦 Requested: {quantity} views\n"
                    f"💡 Need {quantity - balance} more views\n\n"
                    f"Watch more ads or refer friends to earn more views!",
                    reply_markup=MAIN_KEYBOARD
                )
                user_states.pop(user_id, None)
                return
            
            # Process the order
            video_link = context.user_data.get('video_link', '')
            await process_order(update, context, user_id, video_link, quantity)
            
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
    
    elif state == WAITING_FOR_BROADCAST and user_id == ADMIN_ID:
        # Admin broadcast message
        await broadcast_message(update, context, message_text)
        user_states.pop(user_id, None)

async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, video_link: str, quantity: int):
    """Process order through API"""
    try:
        import urllib.parse
        
        # URL encode parameters properly
        encoded_video = urllib.parse.quote(video_link, safe='')
        api_url = f"{ORDER_API_URL}?video={encoded_video}&qty={quantity}"
        response = requests.get(api_url, timeout=30)
        
        if response.status_code == 200:
            # Deduct balance
            if storage.subtract_balance(user_id, quantity):
                # Create order record
                order_id = storage.create_order(user_id, video_link, quantity, quantity)
                
                message = f"✅ **Order Confirmed!**\n\n"
                message += f"🆔 Order ID: `{order_id}`\n"
                message += f"🔗 Video: {video_link}\n"
                message += f"📦 Quantity: {quantity} views\n"
                message += f"💰 Cost: {quantity} balance points\n\n"
                message += f"🚀 Your order is being processed!\n"
                message += f"📊 Views will be delivered within 24 hours.\n\n"
                
                user_data = storage.get_user(user_id)
                remaining_balance = user_data.get("balance", 0)
                message += f"💳 Remaining balance: {remaining_balance} views"
                
                await update.message.reply_text(
                    message,
                    parse_mode='Markdown',
                    reply_markup=MAIN_KEYBOARD
                )
            else:
                await update.message.reply_text(
                    "❌ Failed to process payment. Please try again.",
                    reply_markup=MAIN_KEYBOARD
                )
        else:
            await update.message.reply_text(
                f"❌ Order failed. API returned status: {response.status_code}\n"
                f"Please contact admin if this persists.",
                reply_markup=MAIN_KEYBOARD
            )
    
    except requests.RequestException as e:
        await update.message.reply_text(
            "❌ Network error while processing order.\n"
            "Please try again later or contact admin.",
            reply_markup=MAIN_KEYBOARD
        )
    
    finally:
        user_states.pop(user_id, None)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin commands"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    
    if not context.args:
        message = f"👑 **Admin Panel**\n\n"
        message += f"📊 **Available Commands:**\n"
        message += f"• `/admin stats` - Show bot statistics\n"
        message += f"• `/admin broadcast` - Broadcast message to all users\n"
        message += f"• `/admin users` - Show user count\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    command = context.args[0].lower()
    
    if command == "stats":
        stats = storage.get_stats()
        message = f"📊 **Bot Statistics**\n\n"
        message += f"👥 Total users: {stats['total_users']}\n"
        message += f"📦 Total orders: {stats['total_orders']}\n"
        message += f"🔗 Total referrals: {stats['total_referrals']}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    elif command == "broadcast":
        user_states[user_id] = WAITING_FOR_BROADCAST
        await update.message.reply_text(
            "📢 **Broadcast Message**\n\n"
            "Send me the message you want to broadcast to all users:\n\n"
            "Send /cancel to cancel."
        )
    
    elif command == "users":
        all_users = storage.get_all_users()
        message = f"👥 **User List**\n\n"
        message += f"Total users: {len(all_users)}\n\n"
        
        for user_id_str, user_data in list(all_users.items())[:10]:  # Show first 10
            username = user_data.get('username', 'No username')
            balance = user_data.get('balance', 0)
            message += f"• @{username} (ID: {user_id_str}) - {balance} views\n"
        
        if len(all_users) > 10:
            message += f"\n... and {len(all_users) - 10} more users"
        
        await update.message.reply_text(message, parse_mode='Markdown')

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Broadcast message to all users"""
    all_users = storage.get_all_users()
    success_count = 0
    fail_count = 0
    
    await update.message.reply_text(
        f"📢 Broadcasting message to {len(all_users)} users..."
    )
    
    for user_id_str, user_data in all_users.items():
        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=f"📢 **Message from Admin:**\n\n{message_text}",
                parse_mode='Markdown'
            )
            success_count += 1
        except Exception as e:
            fail_count += 1
            logging.error(f"Failed to send message to {user_id_str}: {e}")
    
    await update.message.reply_text(
        f"✅ **Broadcast Complete**\n\n"
        f"📤 Sent successfully: {success_count}\n"
        f"❌ Failed: {fail_count}",
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing process"""
    user_id = update.effective_user.id
    user_states.pop(user_id, None)
    
    await update.message.reply_text(
        "❌ Current process cancelled.",
        reply_markup=MAIN_KEYBOARD
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = query.from_user.id
    
    if callback_data.startswith("watched_ad_"):
        # Extract user_id from callback data
        ad_user_id = int(callback_data.split("_")[-1])
        
        # Verify it's the same user
        if user_id != ad_user_id:
            await query.edit_message_text("❌ Invalid action.")
            return
        
        # Check rate limiting
        import time
        current_time = time.time()
        if user_id in user_last_ad_time:
            time_since_last = current_time - user_last_ad_time[user_id]
            if time_since_last < 30:  # 30 seconds cooldown
                remaining = int(30 - time_since_last)
                await query.edit_message_text(
                    f"⏰ Please wait {remaining} seconds before watching another ad."
                )
                return
        
        # Update last ad time and add ad view
        user_last_ad_time[user_id] = current_time
        ads_watched = storage.add_ad_view(user_id)
        
        # Calculate rewards
        views_earned = ads_watched // 10
        next_reward = 10 - (ads_watched % 10)
        
        message = f"✅ **Ad Verified!**\n\n"
        message += f"📊 Total ads watched: {ads_watched}\n"
        message += f"💰 Views earned: {views_earned}\n"
        
        if next_reward < 10:
            message += f"🎯 Next reward in: {next_reward} ads\n\n"
        else:
            message += f"🎉 You just earned a view! Next reward in: 10 ads\n\n"
        
        message += f"💡 Keep watching ads to earn more views for your video promotions!"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown'
        )
        
        # Send main menu after 3 seconds
        import asyncio
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=user_id,
            text="Choose your next action:",
            reply_markup=MAIN_KEYBOARD
        )

def run_bot():
    """Run the Telegram bot with polling"""
    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start polling
    print("🚀 Bot started with polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# Simple Flask app to keep service alive on hosting platforms
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "Bot is running",
        "mode": "polling",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

def run_flask():
    """Run Flask app in background"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    # Start Flask in background thread to keep service alive
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start bot with polling
    run_bot()