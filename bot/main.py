"""
Telegram Bot for Parsing Poems from Images

This bot allows users to upload images of poems, extract poem metadata,
and manage poem data through various commands.
"""

import os
import uuid
import shutil
import imghdr
from functools import wraps
from typing import Optional
import threading
import json

from flask import Flask
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import requests
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


# Load environment variables from .env file
load_dotenv()

MSG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msg.json")
with open(MSG_PATH, "r", encoding="utf-8") as f:
    MESSAGES = json.load(f)

# Configuration from environment variables
TEMP_DIR: str = os.getenv("TEMP_DIR")
MAX_IMAGES: int = int(os.getenv("MAX_IMAGES"))
ALLOWED_USER_ID: str = os.getenv("ALLOWED_USER_ID")
API_DOMAIN: str = os.getenv("API_DOMAIN")
BOT_NAME: str = os.getenv("BOT_NAME")
BOT_DOMAIN: str = os.getenv("BOT_DOMAIN")


if (
    not API_DOMAIN or not ALLOWED_USER_ID or not TEMP_DIR
    or not MAX_IMAGES or not BOT_NAME or not BOT_DOMAIN
):
    raise RuntimeError(
        "API_DOMAIN, ALLOWED_USER_ID, TEMP_DIR, MAX_IMAGES, BOT_NAME "
        "or BOT_DOMAIN environment variables are not set."
    )

# Configure logger for the bot
logger = configure_logger(BOT_NAME)


# --- In-memory session states ---
user_sessions = {}  # Maps user_id -> request_id
user_data = {}  # Maps user_id -> dict with author, title, text


# --- Decorators ---

def restricted_command(handler_func):
    """
    Decorator to restrict access to allowed user IDs only.

    Sends a warning message and denies access to unauthorized users.
    """
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      *args, **kwargs):
        user_id = update.effective_user.id
        user_lang = update.effective_user.language_code
        if str(user_id) not in ALLOWED_USER_ID.split(","):
            logger.warning("%s | Unauthorized access attempt.", user_id)
            await update.message.reply_text(
                get_message("not_authorized", lang=user_lang)
            )
            return
        return await handler_func(update, context, *args, **kwargs)
    return wrapper


# --- Utility functions ---

def get_message(key: str, lang: str = "en", **kwargs) -> str:
    """
    Returns the message corresponding to the language.
    The default is English if the language doesn't exist.
    """
    if key not in MESSAGES:
        return ""
    msg = MESSAGES[key].get(lang, MESSAGES[key].get("en", ""))
    return msg.format(**kwargs)


def cleanup_temp_dir():
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

    logger.info("%s | %s | Session created", user_id, request_id)
    return request_id


def get_user_input_dir(user_id: int) -> Optional[str]:
    """
    Get the directory path for the current user's session input files.

    Args:
        user_id (int): Telegram user ID.

    Returns:
        Optional[str]: Path to the user's session directory,
        or None if no session exists.
    """
    request_id = user_sessions.get(user_id)
    if not request_id:
        return None
    return os.path.join(TEMP_DIR, request_id)


def delete_user_session(user_id: int):
    """
    Delete the user's current session, including all associated files
    and in-memory data.

    Args:
        user_id (int): Telegram user ID.
    """
    request_id = user_sessions.pop(user_id, None)
    user_data.pop(user_id, None)
    if request_id:
        shutil.rmtree(os.path.join(TEMP_DIR, request_id), ignore_errors=True)
        logger.info("%s | %s | Session deleted", user_id, request_id)


# --- Bot Command Handlers ---

@restricted_command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /start command.

    Creates a new user session with an author's name.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /start command invoked", user_id)

    try:
        request_id = create_session(user_id)

        author = " ".join(context.args)
        if not author:
            logger.warning("%s | %s | No author provided in /start",
                           user_id, request_id)

            await update.message.reply_text(
                get_message("start_incompleted", lang=user_lang)
            )
            return

        user_data[user_id]["author"] = author
        logger.info("%s | Author set to: %s", user_id, author)
        await update.message.reply_text(
            get_message("start_ok", lang=user_lang, author=author),
            parse_mode="Markdown")
    except Exception as e:
        logger.error("%s | Error: %s", user_id, e, exc_info=True)
        await update.message.reply_text(get_message("error", lang=user_lang))


@restricted_command
async def process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /process command.

    Processes all uploaded images, extracts poem data, and shows results.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    request_id = user_sessions.get(user_id)
    input_dir = get_user_input_dir(user_id)
    logger.info("%s | /process command invoked", user_id)

    if not input_dir or not os.path.exists(input_dir):
        logger.warning(
            "%s | No active session or input directory found", user_id
            )
        await update.message.reply_text(
            get_message("process_noimage", user_lang)
            )
        return

    image_paths = sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )

    if not image_paths:
        logger.warning("%s | %s | No valid images found in %s",
                       user_id, request_id, input_dir)
        await update.message.reply_text(
            get_message("process_imageerror", lang=user_lang))
        return

    try:
        result = process_poem(image_paths=image_paths)
        user_data[user_id]["title"] = result.get("poem_title") or "Untitled"
        user_data[user_id]["text"] = result.get("poem_text") or "Empty"

        await update.message.reply_text(
            get_message("process_author",
                        lang=user_lang, author=user_data[user_id]['author']),
            parse_mode="Markdown")

        await update.message.reply_text(
            get_message("process_title",
                        lang=user_lang, title=user_data[user_id]['title']),
            parse_mode="Markdown")

        await update.message.reply_text(
            get_message("process_poem",
                        lang=user_lang, poem=user_data[user_id]['text']),
            parse_mode="Markdown")

        await update.message.reply_text(
            get_message("process_continue", lang=user_lang))

        logger.info("%s | %s | Poem processed successfully",
                    user_id, request_id)
    except Exception as e:
        logger.error("%s | %s | Error processing poem: %s",
                     user_id, request_id, e, exc_info=True)
        await update.message.reply_text(
            get_message("process_error", lang=user_lang))


@restricted_command
async def getinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /getinfo command.

    Shows the current poem data (author, title, text) to the user.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    request_id = user_sessions.get(user_id)
    logger.info("%s | /getinfo command invoked", user_id)

    try:

        data = user_data.get(user_id)
        if not data:
            logger.info("%s | No active session found for /getinfo", user_id)
            await update.message.reply_text(get_message("nosession",
                                                        lang=user_lang))
            return

        author = data.get("author")
        title = data.get("title") or "Untitled"
        text = data.get("text") or "Empty"

        await update.message.reply_text(
            get_message("process_author", lang=user_lang, author=author),
            parse_mode="Markdown")

        await update.message.reply_text(
            get_message("process_title", lang=user_lang, title=title),
            parse_mode="Markdown")

        await update.message.reply_text(
            get_message("process_poem", lang=user_lang, poem=text),
            parse_mode="Markdown")

        await update.message.reply_text(
            get_message("process_continue", lang=user_lang))

        logger.info("%s | %s | Poem info displayed", user_id, request_id)

    except Exception as e:
        logger.error("%s | Error: %s", user_id, e, exc_info=True)
        await update.message.reply_text(get_message("error", lang=user_lang))


@restricted_command
async def edittitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /edittitle command.

    Allows user to manually update the poem's title.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /edittitle command invoked", user_id)

    try:
        request_id = user_sessions.get(user_id)
        if not request_id:
            request_id = create_session(user_id)

        title = " ".join(context.args)
        if not title:
            logger.warning("%s | %s | No title provided in /edittitle",
                           user_id, request_id)
            await update.message.reply_text(
                get_message("edittitle_incompleted", lang=user_lang))
            return

        user_data[user_id]["title"] = title
        await update.message.reply_text(
            get_message("edittitle_ok", lang=user_lang, title=title),
            parse_mode="Markdown"
        )
        logger.info("%s | %s | Poem title updated", user_id, request_id)
    except Exception as e:
        logger.error("%s | Error: %s", user_id, e, exc_info=True)
        await update.message.reply_text(get_message("error", lang=user_lang))


@restricted_command
async def editpoem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /editpoem command.

    Allows user to manually update the poem's text.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /editpoem command invoked", user_id)
    try:
        request_id = user_sessions.get(user_id)
        if not request_id:
            request_id = create_session(user_id)

        # Extract text after command
        text = update.message.text.partition(" ")[2].strip()
        if not text:
            logger.warning("%s | %s | No poem text provided in /editpoem",
                           user_id, request_id)
            await update.message.reply_text(
                get_message("editpoem_incompleted", lang=user_lang))
            return

        user_data[user_id]["text"] = text
        await update.message.reply_text(
            get_message("editpoem_ok", lang=user_lang)
        )
        logger.info("%s | %s | Poem text updated", user_id, request_id)
    except Exception as e:
        logger.error("%s | Error: %s", user_id, e, exc_info=True)
        await update.message.reply_text(get_message("error", lang=user_lang))


@restricted_command
async def editauthor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /editauthor command.

    Allows user to manually update the author's name.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /editauthor command invoked", user_id)

    try:
        request_id = user_sessions.get(user_id)
        if not request_id:
            request_id = create_session(user_id)

        author = " ".join(context.args).strip()
        if not author:
            logger.warning("%s | %s | No author name provided in /editauthor",
                           user_id, request_id)
            await update.message.reply_text(
                get_message("editauthor_incompleted", lang=user_lang))
            return

        user_data[user_id]["author"] = author
        await update.message.reply_text(
            get_message("editauthor_ok", lang=user_lang, author=author),
            parse_mode="Markdown"
        )
        logger.info("%s | %s | Poem author updated", user_id, request_id)
    except Exception as e:
        logger.error("%s | Error: %s", user_id, e, exc_info=True)
        await update.message.reply_text(get_message("error", lang=user_lang))


@restricted_command
async def deleteall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /deleteall command.

    Allows user to delete all poems uploaded.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /deleteall", user_id)
    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    poem_payload = {"user_id": str(user_id)}
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_DOMAIN}/api/delete_all",
                                    json=poem_payload,
                                    headers=headers) as resp:
                if resp.status == 200:
                    await update.message.reply_text(
                        get_message("deleteall_ok", lang=user_lang)
                    )
                    logger.info("%s | %s | All poems deleted",
                                user_id, request_id)
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error("%s | %s | Failed to delete all poems via "
                                 "API. Status: %s - %s",
                                 user_id, request_id, resp.status, error_text)
                    await update.message.reply_text(
                        get_message("deleteall_error", lang=user_lang)
                    )
    except aiohttp.ClientError as e:
        logger.exception("%s | %s | Network error: %s", user_id, request_id, e)
        await update.message.reply_text(
                        get_message("deleteall_error", lang=user_lang)
                    )


@restricted_command
async def deleteauthor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /deleteauthor command.

    Allows user to delete all author poems uploaded.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /deleteauthor", user_id)
    request_id = user_sessions.get(user_id)
    if not request_id:
        request_id = create_session(user_id)

    author = " ".join(context.args).strip()
    if not author:
        logger.warning("%s | %s | No author provided.", user_id, request_id)
        await update.message.reply_text(
            get_message("deleteauthor_incompleted", lang=user_lang))
        return

    poem_payload = {
        "user_id": str(user_id),
        "author": author
    }

    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_DOMAIN}/api/delete_author",
                                    json=poem_payload,
                                    headers=headers) as resp:
                if resp.status == 200:
                    await update.message.reply_text(
                        get_message("deleteauthor_ok", lang=user_lang)
                    )
                    logger.info("%s | %s | Author poems deleted",
                                user_id, request_id)
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error("Failed to delete author poems via API. "
                                 "Status: %s - %s",
                                 resp.status, error_text)
                    await update.message.reply_text(
                        get_message("deleteauthor_error", lang=user_lang)
                    )
    except aiohttp.ClientError as e:
        logger.exception("%s | %s | Network error: %s", user_id, request_id, e)
        await update.message.reply_text(
                        get_message("deleteauthor_error", lang=user_lang)
                    )


@restricted_command
async def deletepoem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /deletepoem command.

    Allows user to delete a poem uploaded.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /deletepoem", user_id)

    request_id = user_sessions.get(user_id) or create_session(user_id)

    raw_text = " ".join(context.args).strip()
    if not raw_text:
        logger.warning("%s | %s | No input provided.", user_id, request_id)
        await update.message.reply_text(
            get_message("deletepoem_incompleted", lang=user_lang))
        return

    try:
        title, author = map(str.strip, raw_text.split("&", 1))
        if not title or not author:
            raise ValueError("Missing title or author")
    except ValueError:
        logger.warning("%s | %s | Invalid format: '%s'",
                       user_id, request_id, raw_text)
        await update.message.reply_text(
            get_message("deletepoem_format", lang=user_lang))
        return

    poem_payload = {
        "user_id": str(user_id),
        "author": author,
        "title": title
    }
    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_DOMAIN}/api/delete_poem",
                                    json=poem_payload,
                                    headers=headers) as resp:
                if resp.status == 200:
                    await update.message.reply_text(
                        get_message("deletepoem_ok", lang=user_lang))
                    logger.info("%s | %s | Poem deleted", user_id, request_id)
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error(
                        "%s | %s | Failed to delete poem via API. "
                        "Status: %s - %s",
                        user_id, request_id, resp.status, error_text
                    )
                    await update.message.reply_text(
                        get_message("deletepoem_error", lang=user_lang))

    except aiohttp.ClientError as e:
        logger.exception("%s | %s | Network error: %s", user_id, request_id, e)
        await update.message.reply_text(
                        get_message("deletepoem_error", lang=user_lang))


@restricted_command
async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /upload command.

    Allows uploading poem info to the database.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /upload", user_id)
    data = user_data.get(user_id)
    request_id = user_sessions.get(user_id)

    if (
        not data or not request_id or not all([data.get("author"),
                                               data.get("title"),
                                               data.get("text")])
    ):
        logger.warning("%s | Upload failed due to incomplete data.", user_id)
        await update.message.reply_text(
            get_message("upload_incompleted", lang=user_lang)
        )
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
            async with session.post(f"{API_DOMAIN}/api/upload_poem",
                                    json=poem_payload,
                                    headers=headers) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    poem_url = data["poem_url"]
                    poem_url = f"{API_DOMAIN}/{poem_url}"
                    await update.message.reply_text(
                        get_message("upload_ok",
                                    lang=user_lang, poem_url=poem_url))
                    delete_user_session(user_id)
                else:
                    error_text = await resp.text()
                    logger.error("%s | %s | Failed to upload poem via API. "
                                 "Status: %s - %s",
                                 user_id, request_id, resp.status, error_text)
                    await update.message.reply_text(
                        get_message("upload_error", lang=user_lang))
    except aiohttp.ClientError as e:
        logger.exception("%s | %s | Network error: %s", user_id, request_id, e)
        await update.message.reply_text(
                        get_message("upload_error", lang=user_lang))


@restricted_command
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /reset command.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /reset", user_id)
    delete_user_session(user_id)
    await update.message.reply_text(get_message("reset", lang=user_lang))


@restricted_command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | /help", user_id)
    await update.message.reply_text(get_message("help", lang=user_lang))


@restricted_command
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for unknown commands. Redirects the user to the /help message.
    """
    user_id = update.effective_user.id
    unknown = update.message.text
    logger.info("%s | Unknown command received: %s", user_id, unknown)

    await help_command(update, context)


@restricted_command
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming image uploads.
    Uploades images in user session folder, preserving the order.
    Enforces max number of images.
    """
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code
    logger.info("%s | Image handled.", user_id)
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
        logger.warning("%s | %s | The image was not uploaded because "
                       "the maximum number of images was reached",
                       user_id, request_id)
        await update.message.reply_text(
            get_message("image_max", lang=user_lang, max_images=MAX_IMAGES))
        return

    image_index = len(image_paths) + 1

    photo_file = await update.message.photo[-1].get_file()

    # Download image temporarily
    temp_path = os.path.join(input_dir, f"{image_index:03d}.tmp")
    await photo_file.download_to_drive(temp_path)

    # Detect actual image extension
    detected_type = imghdr.what(temp_path)
    if detected_type not in ['jpeg', 'png']:
        logger.warning("%s | %s | Unsupported image type: %s",
                       user_id, request_id, detected_type)
        os.remove(temp_path)
        await update.message.reply_text(
            get_message("image_invalid", lang=user_lang))
        return

    # Map detected type to correct extension
    extension = 'jpg' if detected_type == 'jpeg' else 'png'
    final_path = os.path.join(input_dir, f"{image_index:03d}.{extension}")

    os.rename(temp_path, final_path)

    # Notify user if this image hits the max count exactly
    if image_index == MAX_IMAGES:
        await update.message.reply_text(
            get_message("image_limit", lang=user_lang))
        return

    await update.message.reply_text(get_message("image_ok", lang=user_lang))
    logger.info("%s | %s | Image uploaded at %s",
                user_id, request_id, final_path)


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
    """
    Root route of the web application.

    Returns a simple message indicating that the bot is running.

    Returns:
        str: Message confirming the bot is operational.
    """
    return "Bot is running 🚀"


def run_webserver():
    """
    Starts the web server for the application.

    Runs the Flask app on all network interfaces (0.0.0.0) at port 4000
    with debug mode disabled.
    """
    app.run(host="0.0.0.0", port=4000, debug=False)


def keep_alive():
    """
    Function that pings the /ping endpoint to keep the app awake.
    """
    try:
        url = f"{BOT_DOMAIN}/"
        logger.info("Pinging: %s", url)
        requests.get(url, timeout=60)
    except Exception as e:
        logger.error("Ping error: %s", e, exc_info=True)


# --- Configure the scheduler ---

scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, 'interval', minutes=2)
scheduler.start()


# --- Entry point ---

if __name__ == "__main__":

    threading.Thread(target=run_webserver, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()

    # Clean data dir
    cleanup_temp_dir()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set in environment variables."
            )

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
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Starting bot polling...")
    application.run_polling()
