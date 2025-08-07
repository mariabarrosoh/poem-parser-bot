# main.py
import os
import io
import uuid
import shutil
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)

from process import process
from utils.logging_config import configure_logger

load_dotenv()

logger = configure_logger("PoemParserBot")

# Load environment variables
DATA_DIR = os.getenv("DATA_DIR")
if not DATA_DIR:
    raise RuntimeError("DATA_DIR environment variable is not set.")

MAX_IMAGES = int(os.getenv("MAX_IMAGES", "5"))

# Dictionary to manage user sessions (user_id -> request_id)
user_sessions = {}

def cleanup_data_dir():
    """
    Clean up the entire data directory by removing all session folders.
    """
    for name in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

def create_session(user_id: int) -> str:
    """
    Create a new session for a user and prepare a temporary folder for image input.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        str: Generated request ID associated with the session.
    """
    request_id = uuid.uuid4().hex[:16]
    request_dir = os.path.join(DATA_DIR, request_id)

    if user_id in user_sessions:
        delete_user_session(user_id)

    os.makedirs(request_dir, exist_ok=True)
    user_sessions[user_id] = request_id
    logger.info(f"{user_id} | {request_id} | Created session")
    return request_id

def get_user_input_dir(user_id: int) -> str | None:
    """
    Get the input folder path for the given user.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        str | None: Path to input directory or None if session doesn't exist.
    """
    request_id = user_sessions.get(user_id)
    if not request_id:
        return None
    return os.path.join(DATA_DIR, request_id)

def delete_user_session(user_id: int):
    """
    Delete a user's session and remove associated temporary files.

    Args:
        user_id (int): Telegram user ID.
    """
    request_id = user_sessions.pop(user_id, None)
    if request_id:
        logger.info(f"{user_id} | {request_id} | Deleted session")
        shutil.rmtree(os.path.join(DATA_DIR, request_id), ignore_errors=True)

# --- Bot Handlers ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help command handler. Sends a list of available commands to the user.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Telegram context.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /help requested")

    help_text = (
        "Here are the available commands:\n\n"
        "/start - Start a new session\n"
        "/reset - Reset your current session\n"
        "/done - Finish and process the uploaded images\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command handler. Initializes a new user session.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Telegram context.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /start requested")

    was_existing = user_id in user_sessions
    create_session(user_id)

    if was_existing:
        await update.message.reply_text("Previous session cleared. You can now send new images.")
    else:
        await update.message.reply_text("Send one or more images of the poem. Use /done when finished.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reset command handler. Resets current session and starts a new one.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Telegram context.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /reset requested")

    delete_user_session(user_id)
    create_session(user_id)
    await update.message.reply_text("Session reset. You can send new images.")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /done command handler. Processes all uploaded images and sends back an HTML file.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /done requested")

    request_id = user_sessions.get(user_id)
    input_dir = get_user_input_dir(user_id)

    # No sesión iniciada
    if not input_dir or not os.path.exists(input_dir):
        logger.warning(f"{user_id} | No session or input directory found.")
        await update.message.reply_text("You haven't sent any images yet.")
        return

    image_paths = sorted([
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if not image_paths:
        logger.warning(f"{user_id} | {request_id} | No valid images found.")
        await update.message.reply_text("No valid images found. Accepted formats: JPG, JPEG, PNG.")
        return

    if len(image_paths) >= MAX_IMAGES:
        await update.message.reply_text(f"You've reached the maximum of {MAX_IMAGES} images. Use /done to process them.")
        return

    try:
        logger.info(f"{user_id} | {request_id} | Starting processing of {len(image_paths)} images")

        title, poem_html, poem_text = process(image_paths=image_paths, request_id=request_id)

        if not poem_html:
            logger.warning(f"{user_id} | {request_id} | No valid HTML extracted from images.")
            await update.message.reply_text("The images you sent do not contain a valid poem or could not be processed.")
            return
        logger.info(f"{user_id} | {request_id} | HTML extracted successfully")

        display_title = title if title else "(Unknown Poem)"

        if not title and not poem_text:
            logger.warning(f"{user_id} | {request_id} | Missing both title and poem text")
            await update.message.reply_text("Could not extract poem title or text.", parse_mode="Markdown")
        elif not title:
            logger.warning(f"{user_id} | {request_id} | Missing poem title")
            await update.message.reply_text("Could not extract the poem title.", parse_mode="Markdown")
            if poem_text:
                logger.info(f"{user_id} | {request_id} | Sending poem text without title")
                await update.message.reply_text(poem_text, parse_mode="Markdown")
        elif not poem_text:
            logger.warning(f"{user_id} | {request_id} | Missing poem text")
            await update.message.reply_text(f"Poem *{display_title}* processed, but no text could be extracted.", parse_mode="Markdown")
        else:
            logger.info(f"{user_id} | {request_id} | Poem title and text extracted successfully")
            await update.message.reply_text(f"Poem *{display_title}* processed successfully.", parse_mode="Markdown")
            await update.message.reply_text(poem_text, parse_mode="Markdown")

        # Send HTML
        html_bytes_io = io.BytesIO(poem_html.encode("utf-8"))
        html_bytes_io.name = f"{(request_id or 'output')}.html"
        await update.message.reply_document(document=html_bytes_io)
        logger.info(f"{user_id} | {request_id} | HTML file sent to user")

    except Exception as e:
        logger.error(f"{user_id} | {request_id} | Failed to process poem: {e}", exc_info=True)
        await update.message.reply_text("Something went wrong while processing the poem. Please try again later.")
    finally:
        delete_user_session(user_id)
        logger.info(f"{user_id} | {request_id} | User session deleted")


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming image uploads and saves them to the user's session folder.
    Ensures images are saved in order of arrival.
    """
    user_id = update.effective_user.id
    request_id = user_sessions.get(user_id)
    input_dir = get_user_input_dir(user_id)

    if not input_dir:
        logger.info(f"{user_id} | No session found. Creating new session.")
        request_id = create_session(user_id)
        input_dir = get_user_input_dir(user_id)

    # Contar cuántas imágenes hay ya
    existing_files = [
        f for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    image_index = len(existing_files) + 1

    # Obtener imagen y guardarla con orden numérico
    photo_file = await update.message.photo[-1].get_file()
    logger.info(f"{user_id} | {request_id} | Image received")

    file_path = os.path.join(input_dir, f"{image_index:03d}.jpg")
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Image received. Use /done when finished.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for unknown commands. Redirects the user to the /help message.

    Args:
        update (Update): Telegram update object.
        context (ContextTypes.DEFAULT_TYPE): Telegram context.
    """
    user_id = update.effective_user.id
    unknown = update.message.text
    logger.info(f"user_id={user_id} | Unknown command received: {unknown}")

    await help_command(update, context)


async def set_bot_commands(application):
    """
    Set the list of available bot commands with their descriptions.

    This function defines the commands that users can see in the Telegram UI
    when they type "/" in the chat. It helps users understand how to interact with the bot.

    Args:
        application: The Telegram bot application instance from which the bot object is accessed.
    """
    await application.bot.set_my_commands([
        BotCommand("start", "Start a new session"),
        BotCommand("reset", "Reset your current session"),
        BotCommand("done", "Finish and process the uploaded images"),
        BotCommand("help", "Show available commands and usage"),
    ])


# --- Entry point ---

if __name__ == "__main__":
    """
    Entry point for running the Telegram bot.
    Initializes handlers and starts polling.
    """

    # Clean data dir
    cleanup_data_dir()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment variables.")

    application = ApplicationBuilder().token(token).build()
    application.post_init = set_bot_commands

    # Register bot commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot is running...")
    application.run_polling()
