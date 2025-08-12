"""
Telegram Bot for Parsing Poems from Images

This bot allows users to upload images of poems, extract poem metadata (title, author, text),
and manage poem data through various commands.
"""

import os
import uuid
import shutil
import imghdr
from functools import wraps
from typing import Optional

from flask import Flask
from flask_cors import CORS
import threading
import aiohttp
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from process import process_poem
from utils.logging_config import configure_logger
from utils.utils import escape_markdown


# Load environment variables from .env file
load_dotenv()

# Configure logger for the bot
logger = configure_logger("PoemParserBot")

# Configuration from environment variables
TEMP_DIR: str = os.getenv("TEMP_DIR")
MAX_IMAGES: int = int(os.getenv("MAX_IMAGES"))
ALLOWED_USER_ID: str = os.getenv("ALLOWED_USER_ID")
POEM_DOMAIN: str = os.getenv("POEM_DOMAIN")

if not POEM_DOMAIN or not ALLOWED_USER_ID or not TEMP_DIR or not MAX_IMAGES:
    raise RuntimeError("POEM_DOMAIN, ALLOWED_USER_ID, TEMP_DIR or MAX_IMAGES environment variables are not set.")

# --- In-memory session states ---
user_sessions: dict[int, str] = {}  # Maps user_id -> request_id
user_data: dict[int, dict[str, Optional[str]]] = {}  # Maps user_id -> dict with author, title, text


# --- Decorators ---

def restricted_command(handler_func):
    """
    Decorator to restrict access to allowed user IDs only.

    Sends a warning message and denies access to unauthorized users.
    """
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if str(user_id) not in ALLOWED_USER_ID.split(","):
            logger.warning(f"{user_id} | Unauthorized access attempt.")
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return
        return await handler_func(update, context, *args, **kwargs)
    return wrapper


# --- Utility functions ---

def cleanup_TEMP_DIR() -> None:
    """
    Clean up the temporary directory by deleting all contents.

    Creates the TEMP_DIR if it does not exist.
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    for name in os.listdir(TEMP_DIR):
        path = os.path.join(TEMP_DIR, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


def create_session(user_id: int) -> str:
    """
    Create a new session for the user by generating a unique request ID
    and setting up the required directory and in-memory session data.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        str: The newly created request ID.
    """
    request_id = uuid.uuid4().hex[:16]
    request_dir = os.path.join(TEMP_DIR, request_id)

    # Delete any existing session for this user
    delete_user_session(user_id)

    # Create the directory for this session
    os.makedirs(request_dir, exist_ok=True)

    # Initialize session mappings
    user_sessions[user_id] = request_id
    user_data[user_id] = {"author": "Unknown", "title": None, "text": None}

    logger.info(f"{user_id} | {request_id} | Session created")
    return request_id


def get_user_input_dir(user_id: int) -> Optional[str]:
    """
    Get the directory path for the current user's session input files.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        Optional[str]: Path to the user's session directory, or None if no session exists.
    """
    request_id = user_sessions.get(user_id)
    if not request_id:
        return None
    return os.path.join(TEMP_DIR, request_id)


def delete_user_session(user_id: int) -> None:
    """
    Delete the user's current session, including all associated files and in-memory data.

    Args:
        user_id (int): Telegram user ID.
    """
    request_id = user_sessions.pop(user_id, None)
    user_data.pop(user_id, None)
    if request_id:
        shutil.rmtree(os.path.join(TEMP_DIR, request_id), ignore_errors=True)
        logger.info(f"{user_id} | {request_id} | Session deleted")


# --- Bot Command Handlers ---

@restricted_command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the /start command.

    Creates a new user session with an author's name.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /start command invoked")

    request_id = create_session(user_id)

    author = escape_markdown(" ".join(context.args))
    if not author:
        logger.warning(f"{user_id} | {request_id} | No author provided in /start")
        await update.message.reply_text("Please provide an author name, or type 'Unknown' or 'Anonymous'. Usage: /start Author")
        return

    user_data[user_id]["author"] = author
    logger.info(f"{user_id} | Author set to: {author}")
    await update.message.reply_text(
        f"Author set to: {author}.\n"
        "You can change it anytime using /editauthor.\n\n"
        "Now, please send one or more images of the poem.\n"
        "When you're done, use /process to process them."
    )


@restricted_command
async def process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /process command.

    Processes all uploaded images, extracts poem data, and shows results.
    """
    user_id = update.effective_user.id
    request_id = user_sessions.get(user_id)
    input_dir = get_user_input_dir(user_id)
    logger.info(f"{user_id} | /process command invoked")

    if not input_dir or not os.path.exists(input_dir):
        logger.warning(f"{user_id} | No active session or input directory found")
        await update.message.reply_text("You haven't sent any images yet. Please upload images before using /process.")
        return

    image_paths = sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )

    if not image_paths:
        logger.warning(f"{user_id} | {request_id} | No valid images found in {input_dir}")
        await update.message.reply_text("No valid images found. Accepted formats: JPG, JPEG, PNG.")
        return

    try:
        result = process_poem(image_paths=image_paths, request_id=request_id)
        user_data[user_id]["title"] = escape_markdown(result.get("poem_title")) or "Untitled"
        user_data[user_id]["text"] = escape_markdown(result.get("poem_text")) or "Empty"

        await update.message.reply_text(f"*Author:* {user_data[user_id]['author']}", parse_mode="Markdown")
        await update.message.reply_text(f"*Title:* {user_data[user_id]['title']}", parse_mode="Markdown")
        await update.message.reply_text(f"*Poem:*\n\n{user_data[user_id]['text']}", parse_mode="Markdown")
        await update.message.reply_text(
            "If something is incorrect, use /edittitle, /editpoem, or /editauthor. When you're ready, use /upload to upload it."
        )

        logger.info(f"{user_id} | {request_id} | Poem processed successfully")
    except Exception as e:
        logger.error(f"{user_id} | {request_id} | Error processing poem: {e}", exc_info=True)
        await update.message.reply_text(
            "An error occurred while processing the poem. Please try /process, /start, or /reset again."
        )


@restricted_command
async def getinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /getinfo command.

    Shows the current poem data (author, title, text) to the user.
    """
    user_id = update.effective_user.id
    request_id = user_sessions.get(user_id)
    logger.info(f"{user_id} | /getinfo command invoked")

    data = user_data.get(user_id)
    if not data:
        logger.info(f"{user_id} | No active session found for /getinfo")
        await update.message.reply_text("No active session found. Use /start to begin.")
        return

    author = data.get("author")
    title = data.get("title") or "Untitled"
    text = data.get("text") or "Empty"

    await update.message.reply_text(f"*Author:* {author}", parse_mode="Markdown")
    await update.message.reply_text(f"*Title:* {title}", parse_mode="Markdown")
    await update.message.reply_text(f"*Poem:*\n\n{text}", parse_mode="Markdown")
    await update.message.reply_text(
        "If something is incorrect, use /edittitle, /editpoem, or /editauthor.\n"
        "When you're ready, use /upload to upload it."
    )
    logger.info(f"{user_id} | {request_id} | Poem info displayed")


@restricted_command
async def edittitle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /edittitle command.

    Allows user to manually update the poem's title.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /edittitle command invoked")

    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    title = escape_markdown(" ".join(context.args))
    if not title:
        logger.warning(f"{user_id} | {request_id} | No title provided in /edittitle")
        await update.message.reply_text("Please provide a new title. Usage: /edittitle New Title")
        return

    user_data[user_id]["title"] = title
    await update.message.reply_text(
        f"Title updated to: {title}\n\n"
        "You can use /getinfo to review the current poem data, or /upload to upload all the poem information."
    )
    logger.info(f"{user_id} | {request_id} | Poem title updated")


@restricted_command
async def editpoem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /editpoem command.

    Allows user to manually update the poem's text.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /editpoem command invoked")

    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    # Extract text after command
    text = escape_markdown(update.message.text.partition(" ")[2].strip())
    if not text:
        logger.warning(f"{user_id} | {request_id} | No poem text provided in /editpoem")
        await update.message.reply_text("Please provide new text. Usage: /editpoem New text")
        return

    user_data[user_id]["text"] = text
    await update.message.reply_text(
        "Poem text updated.\n\n"
        "You can use /getinfo to review the current poem data, or /upload to upload all the poem information."
    )
    logger.info(f"{user_id} | {request_id} | Poem text updated")


@restricted_command
async def editauthor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /editauthor command.

    Allows user to manually update the author's name.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /editauthor command invoked")

    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    author = escape_markdown(" ".join(context.args).strip())
    if not author:
        logger.warning(f"{user_id} | {request_id} | No author name provided in /editauthor")
        await update.message.reply_text("Please provide the author's name. Usage: /editauthor Name")
        return

    user_data[user_id]["author"] = author
    await update.message.reply_text(
        f"Author updated to: {author}\n\n"
        "You can use /getinfo to review the current poem data, or /upload to upload all the poem information."
    )
    logger.info(f"{user_id} | {request_id} | Poem author updated")


@restricted_command
async def deleteall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /deleteall command.

    Allows user to delete all poems uploaded.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /deleteall")
    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    poem_payload = {"user_id": str(user_id)}
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{POEM_DOMAIN}/api/delete_all", json=poem_payload, headers=headers) as resp:
                if resp.status == 200:
                    await update.message.reply_text(
                        "All poems delete successfully! ✅"
                    )
                    logger.info(f"{user_id} | {request_id} | All poems deleted")
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to delete all poems via API. Status: {resp.status} - {error_text}")
                    await update.message.reply_text(
                        "Failed to delete all poems. Please try again later."
                    )
    except aiohttp.ClientError as e:
        logger.exception(f"{user_id} | {request_id} | Network error: {e}")
        await update.message.reply_text("Network error while deleting all poems. Please try again later.")


@restricted_command
async def deleteauthor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /deleteauthor command.

    Allows user to delete all author poems uploaded.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /deleteauthor")
    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    author = escape_markdown(" ".join(context.args).strip())
    if not author:
        logger.warning(f"{user_id} | {request_id} | No author provided.")
        await update.message.reply_text("Please provide the author's name. Usage: /deleteauthor Name")
        return

    poem_payload = {
        "user_id": str(user_id),
        "author": author
    }

    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{POEM_DOMAIN}/api/delete_author", json=poem_payload, headers=headers) as resp:
                if resp.status == 200:
                    await update.message.reply_text(
                        "Author poems delete successfully! ✅"
                    )
                    logger.info(f"{user_id} | {request_id} | Author poems deleted")
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to delete author poems via API. Status: {resp.status} - {error_text}")
                    await update.message.reply_text(
                        "Failed to delete author poems. Please try again later."
                    )
    except aiohttp.ClientError as e:
        logger.exception(f"{user_id} | {request_id} | Network error: {e}")
        await update.message.reply_text("Network error while deleting author poems. Please try again later.")


@restricted_command
async def deletepoem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /deletepoem command.

    Allows user to delete a poem uploaded.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /deletepoem")

    request_id = user_sessions.get(user_id) or create_session(user_id)

    usage_msg = "Usage: /deletepoem Title & Author"

    raw_text = " ".join(context.args).strip()
    if not raw_text:
        logger.warning(f"{user_id} | {request_id} | No input provided.")
        await update.message.reply_text(f"Please provide the title and author. {usage_msg}")
        return

    try:
        title, author = map(str.strip, raw_text.split("&", 1))
        if not title or not author:
            raise ValueError("Missing title or author")
    except ValueError:
        logger.warning(f"{user_id} | {request_id} | Invalid format: '{raw_text}'")
        await update.message.reply_text(f"Invalid format. {usage_msg}")
        return

    poem_payload = {
        "user_id": str(user_id),
        "author": author,
        "title": title
    }
    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{POEM_DOMAIN}/api/delete_poem", json=poem_payload, headers=headers) as resp:
                if resp.status == 200:
                    await update.message.reply_text("Poem deleted successfully! ✅")
                    logger.info(f"{user_id} | {request_id} | Poem deleted")
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error(
                        f"{user_id} | {request_id} | Failed to delete poem via API. "
                        f"Status: {resp.status} - {error_text}"
                    )
                    await update.message.reply_text(
                        "Failed to delete author poems. Please try again later."
                    )
    except aiohttp.ClientError as e:
        logger.exception(f"{user_id} | {request_id} | Network error: {e}")
        await update.message.reply_text("Network error while deleting poems. Please try again later.")


@restricted_command
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /upload command.

    Allows uploading poem info to the database.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /upload")
    data = user_data.get(user_id)
    request_id = user_sessions.get(user_id)

    if not data or not request_id or not all([data.get("author"), data.get("title"), data.get("text")]):
        logger.warning(f"{user_id} | Upload failed due to incomplete data.")
        await update.message.reply_text("Incomplete data. Please make sure author, title, and text are set.")
        return

    poem_payload = {
        "user_id": str(user_id),
        "request_id": request_id,
        "author": data["author"],
        "title": data["title"],
        "text": data["text"]
    }

    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{POEM_DOMAIN}/api/upload_poem", json=poem_payload, headers=headers) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    poem_url = data["poem_url"]
                    poem_url = f"{POEM_DOMAIN}/{poem_url}"
                    await update.message.reply_text(
                        f"Poem uploaded successfully! ✅\nYou can view it here: {poem_url}"
                    )
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to upload poem via API. Status: {resp.status} - {error_text}")
                    await update.message.reply_text(
                        "Failed to upload poem. Please try again later."
                    )
    except aiohttp.ClientError as e:
        logger.exception(f"{user_id} | {request_id} | Network error: {e}")
        await update.message.reply_text("Network error while uploading poem. Please try again later.")


@restricted_command
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /reset command.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /reset")
    delete_user_session(user_id)
    await update.message.reply_text("Session reset. Use /start to begin a new one.")


@restricted_command
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | /help")
    help_text = (
        "Available commands:\n"
        "/start <author> - Start a new session entering the author's name\n"
        "/process - Process uploaded images and extract poem\n"
        "/edittitle <title> - Edit the poem's title\n"
        "/editpoem <text> - Edit the poem's content\n"
        "/editauthor <author> - Edit the author's name\n"
        "/upload - Upload the poem data to the database\n"
        "/getinfo: Show poem information\n"
        "/deleteall: Delete all poems uploaded\n"
        "/deleteauthor <author>: Delete all author poems uploaded\n"
        "/deletepoem <title> & <author>: Delete a poem uploaded\n"
        "/reset - Clear the current session\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)


@restricted_command
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for unknown commands. Redirects the user to the /help message.
    """
    user_id = update.effective_user.id
    unknown = update.message.text
    logger.info(f"{user_id} | Unknown command received: {unknown}")

    await help(update, context)


@restricted_command
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming image uploads.
    Uploades images in user session folder, preserving the order.
    Enforces max number of images.
    """
    user_id = update.effective_user.id
    logger.info(f"{user_id} | Image handled.")
    request_id = user_sessions.get(user_id)
    input_dir = get_user_input_dir(user_id)

    # Create session if it doesn't exist
    if not input_dir:
        request_id = create_session(user_id)
        input_dir = get_user_input_dir(user_id)

    # List existing image files with valid extensions
    image_paths = [
        f for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    # If user already exceeded max images, discard new image and notify
    if len(image_paths) >= MAX_IMAGES:
        logger.warning(f"{user_id} | {request_id} | The image was not uploaded because the maximum number of images was reached")
        await update.message.reply_text(
            f"You've reached the maximum of {MAX_IMAGES} images. This image was not uploaded. Please use /process to process the rest."
        )
        return

    image_index = len(image_paths) + 1

    photo_file = await update.message.photo[-1].get_file()

    # Download image temporarily
    temp_path = os.path.join(input_dir, f"{image_index:03d}.tmp")
    await photo_file.download_to_drive(temp_path)

    # Detect actual image extension
    detected_type = imghdr.what(temp_path)
    if detected_type not in ['jpeg', 'png']:
        logger.warning(f"{user_id} | {request_id} | Unsupported image type: {detected_type}")
        os.remove(temp_path)
        await update.message.reply_text("Unsupported image format. Please send JPG or PNG images.")
        return

    # Map detected type to correct extension
    extension = 'jpg' if detected_type == 'jpeg' else 'png'
    final_path = os.path.join(input_dir, f"{image_index:03d}.{extension}")

    os.rename(temp_path, final_path)

    # Notify user if this image hits the max count exactly
    if image_index == MAX_IMAGES:
        await update.message.reply_text(f"You've reached the maximum of {MAX_IMAGES} images. Use /process to process them.")
        return

    await update.message.reply_text(
        "Image received and uploaded.\n"
        "You can send more images, or use /process when you're ready.",
        parse_mode="Markdown"
    )
    logger.info(f"{user_id} | {request_id} | Image uploaded at {final_path}")


# --- Register Bot Commands (Menu) ---

async def set_bot_commands(application):
    """
    Handles set bot commands.
    """
    commands = [
        BotCommand("start", "Start a new session"),
        BotCommand("process", "Process uploaded images"),
        BotCommand("edittitle", "Edit the poem's title"),
        BotCommand("editpoem", "Edit the poem's content"),
        BotCommand("editauthor", "Edit the author's name"),
        BotCommand("upload", "Upload poem to the database"),
        BotCommand("deleteall", "Delete all poems uploaded"),
        BotCommand("deleteauthor", "Delete all author poems uploaded"),
        BotCommand("deletepoem", "Delete a poem uploaded"),
        BotCommand("getinfo", "Show poem info"),
        BotCommand("reset", "Reset current session"),
        BotCommand("help", "Show help message")
    ]
    await application.bot.set_my_commands(commands)


# --- Flask App Initialization ---

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing


@app.route('/')
def home():
    return "Bot running"

def run_webserver():
    app.run(host="0.0.0.0", port=8080, debug=False)


# --- Entry point ---

if __name__ == "__main__":
    """
    Entry point for running the Telegram bot.
    Initializes handlers and starts polling.
    """

    threading.Thread(target=run_webserver, daemon=True).start()


    # Clean data dir
    cleanup_TEMP_DIR()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment variables.")

    application = ApplicationBuilder().token(token).build()
    application.post_init = set_bot_commands

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("process", process))
    application.add_handler(CommandHandler("edittitle", edittitle))
    application.add_handler(CommandHandler("editpoem", editpoem))
    application.add_handler(CommandHandler("editauthor", editauthor))
    application.add_handler(CommandHandler("getinfo", getinfo))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("deleteall", deleteall))
    application.add_handler(CommandHandler("deleteauthor", deleteauthor))
    application.add_handler(CommandHandler("deletepoem", deletepoem))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Starting bot polling...")
    application.run_polling()
