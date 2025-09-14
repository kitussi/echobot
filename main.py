# main.py (Version 6.0 - Final with Token Analysis)

import logging
import re
import base58
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

import config
import db_utils
import api_client

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SELECTING_FILTER_TYPE, AWAITING_KEYWORD_INCLUDE, AWAITING_KEYWORD_EXCLUDE, AWAITING_CONTENT_TYPE = range(4)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    user = update.effective_user
    bot_username = context.bot.username
    add_to_group_url = f"https://t.me/{bot_username}?startgroup=true"

    message_text = (
        f"👋 <b>Welcome, {user.mention_html()}!</b>\n\n"
        "I can help you create custom feeds by forwarding messages from specific users in any group. Here’s how to get started in 3 simple steps:\n\n"
        "1️⃣ <b>Set Your Destination</b>\n"
        "First, add me to the private group or channel where you want to receive alerts. Then, send the <code>/set_destination</code> command in that chat.\n\n"
        "2️⃣ <b>Add Me to the Source Group</b>\n"
        "Next, use the '➕ Add Bot to a Group' button below to add me to the group where the person you want to watch is active.\n\n"
        "3️⃣ <b>Start Watching</b>\n"
        "In the source group, <b>reply</b> to any message from the user you want to watch and send the <code>/get_id</code> command. I will send you a private message with a <code>/watch</code> command to finalize the setup here.\n\n"
        "--- \n"
        "Use the buttons below to manage your bot."
    )

    keyboard = [
        [InlineKeyboardButton("➕ Add Bot to a Group", url=add_to_group_url)],
        [InlineKeyboardButton("🎯 View My Watchlist", callback_data="show_list")],
        [InlineKeyboardButton("⚙️ Manage Destination", callback_data="manage_destination")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    user_id = update.effective_user.id
    chat = update.effective_chat
    db_utils.set_user_destination(user_id, str(chat.id))
    await update.message.reply_text(f"✅ Destination set! Alerts will be forwarded to '{chat.title}'.")
    try:
        await context.bot.send_message(
            user_id,
            f"I have set '<b>{chat.title}</b>' (<code>{chat.id}</code>) as your new alert destination.",
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        logger.warning(f"Could not send PM to {user_id}, user has not started a conversation with the bot.")


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    if not update.message.reply_to_message:
        await update.message.reply_text("Please reply to a user's message to use this command.")
        return

    target_user = update.message.reply_to_message.from_user
    source_chat = update.message.chat
    message = (
        f"✅ IDs Acquired\n\n"
        f"👤 <b>User:</b> @{target_user.username or target_user.first_name} (<code>{target_user.id}</code>)\n"
        f"🏢 <b>Group:</b> {source_chat.title} (<code>{source_chat.id}</code>)\n\n"
        f"To start watching, copy/paste this command into our private chat:\n\n"
        f"<code>/watch {target_user.id} {source_chat.id}</code>"
    )
    try:
        await context.bot.send_message(chat_id=update.effective_user.id, text=message, parse_mode=ParseMode.HTML)
        await update.message.reply_text("I've sent you the required IDs in a private message.")
    except BadRequest:
        await update.message.reply_text("I couldn't send you a PM. Please start a conversation with me first and try again.")


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    watcher_user_id = update.effective_user.id
    if not db_utils.get_user_destination(watcher_user_id):
        await update.message.reply_text("⚠️ Please set your destination chat first with `/set_destination`.")
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
        await update.message.reply_text("❌ Error: I could not find that User ID.")
        return
    if db_utils.add_watched_target(watcher_user_id, source_group_id, target_user_id, target_username):
        await update.message.reply_text(f"✅ Watch activated for @{target_username}.")
    else:
        await update.message.reply_text(f"ℹ️ You are already watching @{target_username} in that group.")


# --- UI and Menu Handlers ---

async def list_targets(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    # ... (Sin cambios)
    user_id = update.effective_user.id
    query = update.callback_query
    
    targets = db_utils.get_user_watched_targets(user_id)
    message_text = "<b>🎯 Your Watchlist:</b>\n\n"
    keyboard = []

    if not targets:
        message_text = "Your watchlist is empty."
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_start")])
    else:
        for target in targets:
            message_text += f"👤 @{target['target_username']} in group <code>{target['source_group_id']}</code>\n"
            buttons = [
                InlineKeyboardButton("⚙️ Manage Filters", callback_data=f"manage:{target['id']}"),
                InlineKeyboardButton("🗑️ Stop Watching", callback_data=f"stop:{target['id']}")
            ]
            keyboard.append(buttons)
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_start")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if is_callback and query:
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def destination_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    user_id = update.effective_user.id
    destination_chat_id = db_utils.get_user_destination(user_id)
    
    message_text = "<b>⚙️ Destination Management</b>\n\n"
    keyboard = []
    if destination_chat_id:
        try:
            chat_info = await context.bot.get_chat(destination_chat_id)
            message_text += f"Current destination: '<b>{chat_info.title}</b>'."
            keyboard.append([InlineKeyboardButton("🗑️ Remove Destination", callback_data="remove_destination")])
        except Exception:
            message_text += "Your destination is set, but I can't access it."
            keyboard.append([InlineKeyboardButton("🗑️ Remove Destination", callback_data="remove_destination")])
    else:
        message_text += "You have not set a destination chat yet."
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_start")])
    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)


async def manage_filters_menu(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE, target_id: int):
    # ... (Sin cambios)
    filters = db_utils.get_filters_for_target(target_id)
    
    message_text = "<b>Managing Filters:</b>\n\n"
    if not filters:
        message_text += "<i>No filters set yet.</i>"
    else:
        for f in filters:
            message_text += f"• <code>{f['filter_type']}: {f['filter_value']}</code>\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Filter", callback_data=f"add_filter:{target_id}")],
        [InlineKeyboardButton("➖ Remove Filter", callback_data=f"remove_filter_menu:{target_id}")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="show_list")]
    ]
    await query.edit_message_text(
        text=message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    
    action, _, value = query.data.partition(':')

    if action == "show_list":
        await list_targets(update, context, is_callback=True)
    
    elif action == "manage_destination":
        await destination_menu(update, context)

    elif action == "remove_destination":
        db_utils.remove_user_destination(update.effective_user.id)
        await query.edit_message_text("✅ Your destination has been removed.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_start")]]))

    elif action == "back_to_start":
        user = update.effective_user
        bot_username = context.bot.username
        add_to_group_url = f"https://t.me/{bot_username}?startgroup=true"
        keyboard = [
            [InlineKeyboardButton("➕ Add Bot to a Group", url=add_to_group_url)],
            [InlineKeyboardButton("🎯 View My Watchlist", callback_data="show_list")],
            [InlineKeyboardButton("⚙️ Manage Destination", callback_data="manage_destination")]
        ]
        await query.edit_message_text(
            f"👋 Welcome back, {user.mention_html()}!\n\nUse the buttons below to manage your bot.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

    elif action == "stop":
        db_utils.remove_watched_target_by_id(int(value))
        await list_targets(update, context, is_callback=True)

    elif action == "manage":
        await manage_filters_menu(query, context, int(value))
    
    elif action == "stop_watch":
        if db_utils.remove_watched_target_by_id(int(value)):
            await query.edit_message_text(f"{query.message.text}\n\n<b>✅ Watch removed.</b>", parse_mode=ParseMode.HTML, reply_markup=None)
        else:
            await query.edit_message_text(f"{query.message.text}\n\n<b>⚠️ Watch already removed.</b>", parse_mode=ParseMode.HTML, reply_markup=None)


async def add_filter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    target_id = query.data.split(':')[1]
    context.user_data['current_target_id'] = target_id
    keyboard = [
        [InlineKeyboardButton("✅ Keywords (Require)", callback_data=f"ftype:keyword_include")],
        [InlineKeyboardButton("❌ Keywords (Exclude)", callback_data=f"ftype:keyword_exclude")],
        [InlineKeyboardButton("🖼️ Content Type", callback_data=f"ftype:content_type")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"manage:{target_id}")]
    ]
    await query.edit_message_text("Choose the type of filter to add:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_FILTER_TYPE


async def add_filter_keyword_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    filter_type = query.data.split(':')[1]
    context.user_data['current_filter_type'] = filter_type
    await query.edit_message_text("Please send the keywords, separated by spaces (e.g., `btc eth announcement`).")
    return AWAITING_KEYWORD_INCLUDE if filter_type == 'keyword_include' else AWAITING_KEYWORD_EXCLUDE


async def add_filter_content_type_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    target_id = context.user_data['current_target_id']
    keyboard = [
        [InlineKeyboardButton("Image 🖼️", callback_data="ctype:image"), InlineKeyboardButton("Video 🎬", callback_data="ctype:video")],
        [InlineKeyboardButton("Link 🔗", callback_data="ctype:link"), InlineKeyboardButton("Text Only ✍️", callback_data="ctype:text_only")],
        [InlineKeyboardButton("Only CA's (Solana) ☀️", callback_data="ctype:solana_ca")],
        [InlineKeyboardButton("Any Crypto Address 🪙", callback_data="ctype:contract_address")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"add_filter:{target_id}")]
    ]
    await query.edit_message_text("Select the content type to filter by:", reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAITING_CONTENT_TYPE


async def save_keyword_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    target_id = context.user_data['current_target_id']
    filter_type = context.user_data['current_filter_type']
    for keyword in update.message.text.lower().split():
        db_utils.add_filter(target_id, filter_type, keyword)
    await update.message.reply_text("✅ Filter(s) added successfully! Your watchlist is being updated...")
    context.user_data.clear()
    await list_targets(update, context)
    return ConversationHandler.END


async def save_content_type_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    content_type = query.data.split(':')[1]
    db_utils.add_filter(context.user_data['current_target_id'], 'content_type', content_type)
    await query.edit_message_text(f"✅ Filter '{content_type}' added! Refreshing list...")
    context.user_data.clear()
    await list_targets(update, context, is_callback=True)
    return ConversationHandler.END


async def remove_filter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(':')[1])
    filters = db_utils.get_filters_for_target(target_id)
    if not filters:
        await query.answer(text="No filters to remove.", show_alert=True)
        return
    keyboard = []
    for f in filters:
        label = f"🗑️ {f['filter_type']}: {f['filter_value']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"delete_filter:{f['id']}:{target_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"manage:{target_id}")])
    await query.edit_message_text("Select a filter to remove:", reply_markup=InlineKeyboardMarkup(keyboard))


async def delete_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    query = update.callback_query
    await query.answer()
    _, filter_id, target_id_str = query.data.split(':')
    target_id = int(target_id_str)
    db_utils.remove_filter_by_id(int(filter_id))
    await manage_filters_menu(query, context, target_id)


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Sin cambios)
    context.user_data.clear()
    query = update.callback_query
    if query:
      await query.answer()
      await list_targets(update, context, is_callback=True)
    else:
      await update.message.reply_text("Action cancelled.")
    return ConversationHandler.END


# --- Core Logic ---

async def send_formatted_message(context: ContextTypes.DEFAULT_TYPE, message: Update.message, destination_chat_id: str, target_id: int):
    # ... (Sin cambios)
    author = message.from_user.mention_html()
    source_group_name = message.chat.title
    
    if message.chat.username:
        message_link = f"https://t.me/{message.chat.username}/{message.message_id}"
    else:
        chat_id_for_link = str(message.chat.id)[4:]
        message_link = f"https://t.me/c/{chat_id_for_link}/{message.message_id}"
    
    footer = (
        f"\n\n🎯 — — — — — — — — 🎯\n"
        f"🔔 <b>Notification from:</b> {author}\n"
        f"🌐 <b>Source:</b> {source_group_name}"
    )
    keyboard = [[
        InlineKeyboardButton("🚀 Jump to Message", url=message_link),
        InlineKeyboardButton("🗑️ Stop Tracking", callback_data=f"stop_watch:{target_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    original_text = message.text or message.caption or ""
    if original_text:
        final_content = original_text + footer
        if not message.text:
            await message.copy(chat_id=destination_chat_id, caption=final_content, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=destination_chat_id, text=final_content, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
    else:
        caption_only_footer = (
            f"🎯 — — — — — — — — 🎯\n"
            f"🔔 <b>Notification from:</b> {author}\n"
            f"🌐 <b>Source:</b> {source_group_name}"
        )
        await message.copy(chat_id=destination_chat_id, caption=caption_only_footer, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler with a simplified, robust analysis call."""
    message = update.effective_message
    if not (message and message.from_user and message.chat):
        return

    watchers = db_utils.find_watchers_for_target(str(message.chat.id), message.from_user.id)
    if not watchers: return

    text_content = message.text or message.caption or ""

    for watch in watchers:
        target_id, watcher_id = watch['id'], watch['watcher_user_id']
        filters = db_utils.get_filters_for_target(target_id)
        
        should_send, found_solana_ca = evaluate_filters(message, text_content, filters)
        
        if not should_send:
            continue
        
        destination_chat_id = db_utils.get_user_destination(watcher_id)
        if not destination_chat_id: continue

        try:
            await send_formatted_message(context, message, destination_chat_id, target_id)

            if found_solana_ca:
                status_message = None
                try:
                    status_message = await context.bot.send_message(
                        chat_id=destination_chat_id,
                        text="🔍 <i>Analyzing Solana Token...</i>",
                        parse_mode=ParseMode.HTML
                    )
                    
                    # --- LLAMADA SIMPLIFICADA Y CORREGIDA ---
                    analysis_result = api_client.get_token_analysis(found_solana_ca)
                    analysis_text = api_client.format_token_analysis(analysis_result)
                    
                    await context.bot.edit_message_text(
                        chat_id=destination_chat_id,
                        message_id=status_message.message_id,
                        text=analysis_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as analysis_error:
                    logger.error(f"CRITICAL: Token analysis process failed for CA {found_solana_ca}. Error: {analysis_error}")
                    if status_message:
                        await context.bot.edit_message_text(
                            chat_id=destination_chat_id,
                            message_id=status_message.message_id,
                            text="⚠️ **Analysis Failed:**\n<i>An unexpected error occurred.</i>",
                            parse_mode=ParseMode.HTML
                        )
        
        except Exception as e:
            logger.error(f"Generic error on forwarding for watcher {watcher_id}: {e}")

def evaluate_filters(message: Update.message, text_content: str, filters: list) -> (bool, str | None):
    """
    Evalúa un mensaje contra una lista de filtros.
    Retorna (True, ca_encontrada) si el mensaje debe ser enviado, o (False, None) si no.
    """
    if not filters:
        # Si no hay filtros, siempre se envía.
        # Comprobamos si hay CA de Solana para el análisis.
        solana_ca = find_solana_ca(text_content)
        return True, solana_ca

    # Organizar filtros por tipo para una lógica más clara
    include_keywords = [f['filter_value'] for f in filters if f['filter_type'] == 'keyword_include']
    exclude_keywords = [f['filter_value'] for f in filters if f['filter_type'] == 'keyword_exclude']
    content_types = [f['filter_value'] for f in filters if f['filter_type'] == 'content_type']

    text_lower = text_content.lower()

    # 1. Comprobación de palabras clave a excluir
    if any(keyword in text_lower for keyword in exclude_keywords):
        return False, None

    # 2. Comprobación de palabras clave a incluir
    # Si existen filtros de inclusión, al menos uno debe cumplirse.
    if include_keywords and not any(keyword in text_lower for keyword in include_keywords):
        return False, None

    # 3. Comprobación de tipo de contenido
    found_solana_ca = None
    if content_types:
        content_match = False
        for ctype in content_types:
            if ctype == 'image' and message.photo: content_match = True; break
            if ctype == 'video' and message.video: content_match = True; break
            if ctype == 'link' and message.entities and any(e.type in ['url', 'text_link'] for e in message.entities): content_match = True; break
            if ctype == 'text_only' and message.text and not message.photo and not message.video and not message.document: content_match = True; break
            
            # Lógica para CA
            ca = find_solana_ca(text_content)
            if ctype == 'solana_ca' and ca:
                found_solana_ca = ca
                content_match = True
                break
            
            # Puedes añadir más lógicas de CA aquí si quieres
            if ctype == 'contract_address' and (ca or find_eth_ca(text_content)):
                found_solana_ca = ca # Priorizamos Solana para el análisis
                content_match = True
                break
        
        # Si hay filtros de contenido y ninguno coincide, no se envía.
        if not content_match:
            return False, None

    # Si pasa todos los filtros, comprobamos si hay una CA de Solana para el análisis
    if not found_solana_ca:
        found_solana_ca = find_solana_ca(text_content)
        
    return True, found_solana_ca


def find_solana_ca(text: str) -> str | None:
    """Encuentra una dirección de contrato de Solana válida en un texto."""
    # Expresión regular para encontrar strings alfanuméricos de 32 a 44 caracteres
    # que son típicos de las direcciones de Solana.
    solana_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    matches = re.findall(solana_pattern, text)
    for match in matches:
        try:
            # Intenta decodificar en base58. Si funciona, es una CA válida.
            base58.b58decode(match)
            # Evita falsos positivos comunes
            if len(match) > 30 and not match.lower().startswith("http"):
                return match
        except Exception:
            continue
    return None

def find_eth_ca(text: str) -> str | None:
    """Encuentra una dirección de contrato de Ethereum/EVM."""
    eth_pattern = r'\b0x[a-fA-F0-9]{40}\b'
    match = re.search(eth_pattern, text)
    return match.group(0) if match else None


def main() -> None:
    """Run the bot."""
    if not config.TELEGRAM_TOKEN:
        raise ValueError("Please add your BOT_TOKEN to the .env file or environment variables.")
    
    db_utils.create_tables()
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    add_filter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_filter_start, pattern='^add_filter:.*$')],
        states={
            SELECTING_FILTER_TYPE: [
                CallbackQueryHandler(add_filter_keyword_prompt, pattern='^ftype:keyword.*$'),
                CallbackQueryHandler(add_filter_content_type_prompt, pattern='^ftype:content_type$'),
                CallbackQueryHandler(button_handler, pattern='^manage:.*$')
            ],
            AWAITING_KEYWORD_INCLUDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_keyword_filter)],
            AWAITING_KEYWORD_EXCLUDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_keyword_filter)],
            AWAITING_CONTENT_TYPE: [CallbackQueryHandler(save_content_type_filter, pattern='^ctype:.*$')]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern='^cancel_conv$'),
            CallbackQueryHandler(button_handler, pattern='^show_list$')
        ],
        per_message=False,
        map_to_parent={ ConversationHandler.END: ConversationHandler.END }
    )

    application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("watch", watch, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("list", list_targets, filters=filters.ChatType.PRIVATE))
    
    application.add_handler(add_filter_conv)
    application.add_handler(CallbackQueryHandler(remove_filter_menu, pattern='^remove_filter_menu:.*$'))
    application.add_handler(CallbackQueryHandler(delete_filter, pattern='^delete_filter:.*$'))
    application.add_handler(CallbackQueryHandler(button_handler))

    group_filter = filters.ChatType.GROUP | filters.ChatType.SUPERGROUP
    application.add_handler(CommandHandler("get_id", get_id, filters=group_filter))
    application.add_handler(CommandHandler("set_destination", set_destination, filters=group_filter | filters.ChatType.CHANNEL))
    application.add_handler(MessageHandler(group_filter & ~filters.COMMAND, group_message_handler))

    print("Bot started (v6.0 - Final with Token Analysis)...")
    application.run_polling()

if __name__ == "__main__":
    main()