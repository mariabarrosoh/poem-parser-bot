"""
Poem Database Module

Handles loading, saving, and managing poems stored in a JSON database.
Each poem is linked to a user, an author, and a title.
"""

import os
import json
from datetime import datetime
from slugify import slugify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Constants ===
DB_DIR = os.getenv("DB_DIR")
if not DB_DIR:
    raise RuntimeError("DB_DIR environment variable is not set.")

DB_PATH = os.path.join(DB_DIR, "poems.json")

# === Core Functions ===

def upload_to_db(poem_dict: dict) -> str:
    """
    Update a poem in the database.

    Args:
        poem_dict (dict): Poem information containing:
            - user_id (str or int)
            - author (str)
            - title (str)
            - text (str)
            - request_id (str)

    Returns:
        str: Poem URL slug (author/title).
    """
    poems = load_poems()
    user_id = str(poem_dict.get("user_id"))

    if not user_id:
        raise ValueError("Missing required field: user_id")

    # Ensure user exists in database
    poems.setdefault(user_id, {})

    author = poem_dict.get("author", "Unknown").strip()
    author_id = slugify(author)

    # Create or update author entry
    poems[user_id].setdefault(author_id, {"author": author, "poems": {}})

    author_dict = poems[user_id][author_id]

    # Update stored author name if it has changed
    if author != author_dict["author"]:
        author_dict["author"] = author

    title = poem_dict.get("title", "Unknown").strip()
    title_id = slugify(title)
    poem_url = f"{author_id}/{title_id}"  # TODO: add user_id in the future

    poem_info = {
        "title": title,
        "poem": poem_dict.get("text", "").strip(),
        "request_id": poem_dict.get("request_id", "").strip(),
        "upload_at": datetime.now().replace(microsecond=0).isoformat(),
        "poem_url": poem_url
    }

    # Create or update poem entry
    author_dict["poems"][title_id] = poem_info

    # Upload changes to file
    upload_poems(poems)

    return poem_url


def upload_poems(poems: dict) -> None:
    """
    Upload the entire poems dictionary to the JSON database file.

    Args:
        poems (dict): Full poems database structure to be uploaded.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)


def load_poems() -> dict:
    """
    Load and return the poems database.

    Returns:
        dict: Poems database structure. If the file doesn't exist
              or is invalid JSON, returns an empty dictionary.
    """
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def get_poems_by_user(user_id: str) -> dict:
    """
    Retrieve all poems for a given user.

    Args:
        user_id (str): User identifier.

    Returns:
        dict: Author and poem data for the user.
    """
    poems = load_poems()
    return poems.get(user_id, {})


def delete_user_db(user_id: str) -> None:
    """
    Delete all poems for a specific user.
    """
    poems = load_poems()
    if poems.pop(user_id, None) is not None:
        upload_poems(poems)


def delete_author_db(user_id: str, author: str) -> None:
    """
    Delete all poems for a specific author under a user.
    """
    poems = load_poems()
    author_id = slugify(author)
    if user_id in poems and author_id in poems[user_id]:
        poems[user_id].pop(author_id, None)
        upload_poems(poems)


def delete_poem_db(user_id: str, author: str, title: str) -> None:
    """
    Delete a specific poem for a given user and author.
    """
    poems = load_poems()
    author_id = slugify(author)
    title_id = slugify(title)

    if user_id in poems and author_id in poems[user_id]:
        poems_dict = poems[user_id][author_id]["poems"]
        if poems_dict.pop(title_id, None) is not None:
            upload_poems(poems)
