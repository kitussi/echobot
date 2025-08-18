import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest

import config
import db_utils

# English language setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Bot Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcomes the user and explains the new, robust workflow."""
    await update.message.reply_text(
        "👋 Hello! I'm your personal watcher bot.\n\n"
        "I help you forward messages from specific users to a chat of your choice. Here's how to use me:\n\n"
        "1️⃣ **Set Your Destination:** Add me to the group or channel where you want to receive alerts, and run `/set_destination` there.\n\n"
        "2️⃣ **Get IDs:** Add me to the source group (where the user you want to watch is). Reply to any of their messages with the command `/get_id`.\n\n"
        "3️⃣ **Start Watching:** I will send you the required IDs in a private message. Use them with the `/watch` command here.\n\n"
        "**Available Commands (in this private chat):**\n"
        "• `/watch <USER_ID> <GROUP_ID>`: Starts watching a user.\n"
        "• `/list`: Shows your current watchlist.\n"
        "• `/stop <USER_ID> <GROUP_ID>`: Stops watching a user."
    )

async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the current chat as the alert destination for the user."""
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    chat_title = update.effective_chat.title
    
    if update.effective_chat.type == 'channel':
        try:
            chat_admins = await context.bot.get_chat_administrators(chat_id)
            if not context.bot.id in [admin.user.id for admin in chat_admins]:
                await update.message.reply_text("⚠️ To use a channel as a destination, I must be an administrator there.")
                return
        except Exception as e:
            logger.error(f"Error checking admin status in channel {chat_id}: {e}")
            await context.bot.send_message(user_id, "⚠️ An error occurred. Please ensure I am an administrator in the destination channel.")
            return

    db_utils.set_user_destination(user_id, chat_id)
    await update.message.reply_text(f"✅ Destination set! All your alerts will be forwarded to this chat: '{chat_title}'.")
    await context.bot.send_message(user_id, f"I have set '<b>{chat_title}</b>' (ID: <code>{chat_id}</code>) as your new alert destination.", parse_mode=ParseMode.HTML)


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gets the User ID and Chat ID from a replied-to message in a group."""
    if not update.message.reply_to_message:
        await update.message.reply_text("Please reply to a user's message to use this command.")
        return

    target_user = update.message.reply_to_message.from_user
    source_chat = update.message.chat
    
    # ========================= THE FINAL FIX IS HERE =========================
    # Switched from MARKDOWN_V2 to HTML for robust parsing.
    # <b> for bold, <code> for code (copy-paste friendly).
    # HTML does not have issues with special characters like '!', '()', or '-'.
    message = (
        f"✅ IDs Acquired\n\n"
        f"👤 <b>User:</b> @{target_user.username or target_user.first_name} (<code>{target_user.id}</code>)\n"
        f"🏢 <b>Group:</b> {source_chat.title} (<code>{source_chat.id}</code>)\n\n"
        f"To start watching, copy and paste this command into our private chat:\n\n"
        f"<code>/watch {target_user.id} {source_chat.id}</code>"
    )
    
    try:
        # Using ParseMode.HTML now
        await context.bot.send_message(chat_id=update.effective_user.id, text=message, parse_mode=ParseMode.HTML)
        await update.message.reply_text("I've sent you the required IDs in a private message.")
    except BadRequest as e:
        logger.error(f"Failed to send private message for get_id: {e}")
        # This error message is now accurate if it ever appears.
        await update.message.reply_text("I couldn't send you a private message. Please start a conversation with me first and try again.")


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watcher_user_id = update.effective_user.id
    if not db_utils.get_user_destination(watcher_user_id):
        await update.message.reply_text("⚠️ **Action Required:** Before adding a target, please set your destination chat by running `/set_destination` in the desired group/channel.")
        return
    try:
        target_user_id = int(context.args[0])
        source_group_id = str(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Incorrect format. Use: `/watch <USER_ID> <GROUP_ID>`")
        return
    try:
        target_user_info = await context.bot.get_chat(target_user_id)
        target_username = target_user_info.username or f"User_{target_user_id}"
    except BadRequest:
        await update.message.reply_text("❌ Error: I could not find that User ID. Please make sure it's correct.")
        return
    if db_utils.add_watched_target(watcher_user_id, source_group_id, target_user_id, target_username):
        await update.message.reply_text(f"✅ Watch activated! I will now forward messages from @{target_username} in group <code>{source_group_id}</code>.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"ℹ️ You are already watching @{target_username} in that group.")


async def list_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watcher_user_id = update.effective_user.id
    targets = db_utils.get_user_watched_targets(watcher_user_id)
    if not targets:
        await update.message.reply_text("Your watchlist is currently empty.")
        return
    message = "<b>🎯 Your Watchlist:</b>\n\n"
    for target in targets:
        message += (f"👤 <b>User:</b> @{target['target_username']} (<code>{target['target_user_id']}</code>)\n"
                    f"🏢 <b>Source Group:</b> <code>{target['source_group_id']}</code>\n\n")
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def stop_watching(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watcher_user_id = update.effective_user.id
    try:
        target_user_id = int(context.args[0])
        source_group_id = context.args[1]
    except (IndexError, ValueError):
        await update.message.reply_text("Incorrect format. Use: `/stop <USER_ID> <GROUP_ID>`")
        return
    if db_utils.remove_watched_target(watcher_user_id, target_user_id, source_group_id):
        await update.message.reply_text("✅ Target removed from your watchlist.")
    else:
        await update.message.reply_text("❌ I couldn't find that target in your watchlist.")


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or not update.message.chat: return
    target_user_id = update.message.from_user.id
    source_group_id = str(update.message.chat.id)
    watcher_ids = db_utils.find_watchers_for_target(source_group_id, target_user_id)
    if not watcher_ids: return
    for watcher_id in watcher_ids:
        destination_chat_id = db_utils.get_user_destination(watcher_id)
        if destination_chat_id:
            try:
                await context.bot.forward_message(chat_id=destination_chat_id, from_chat_id=source_group_id, message_id=update.message.message_id)
            except Exception as e:
                logger.error(f"Failed to forward to {destination_chat_id} for watcher {watcher_id}: {e}")
                await context.bot.send_message(chat_id=watcher_id, text=f"⚠️ Error! I failed to forward a message from group <code>{source_group_id}</code>. Please ensure I am still a member of your destination chat.", parse_mode=ParseMode.HTML)


def main():
    if not config.TELEGRAM_TOKEN or config.TELEGRAM_TOKEN == "AQUÍ_VA_TU_TOKEN_DE_TELEGRAM":
        raise ValueError("Please add your TELEGRAM_TOKEN to config.py")
    db_utils.create_tables()
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("watch", watch, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("list", list_targets, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("stop", stop_watching, filters=filters.ChatType.PRIVATE))
    group_filter = filters.ChatType.GROUP | filters.ChatType.SUPERGROUP
    application.add_handler(CommandHandler("get_id", get_id, filters=group_filter))
    application.add_handler(CommandHandler("set_destination", set_destination, filters=group_filter | filters.ChatType.CHANNEL))
    application.add_handler(MessageHandler(group_filter & ~filters.COMMAND, group_message_handler))

    print("🚀 Robust multi-user bot started (v3.3 - HTML Fix). Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()