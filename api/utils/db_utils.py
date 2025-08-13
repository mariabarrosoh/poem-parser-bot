"""
Poem Database Module

Handles loading, saving, and managing poems stored in a PostgreSQL database.
Each poem is linked to a user, an author, and a title.
"""

import os
from datetime import datetime
from contextlib import contextmanager
from slugify import slugify
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


@contextmanager
def get_db_cursor():
    """
    Context manager to get a PostgreSQL cursor with automatic commit/rollback.
    """
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in environment variables.")

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """
    Initialize database tables if they do not already exist.
    """
    with get_db_cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) UNIQUE NOT NULL
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            author VARCHAR(255) NOT NULL,
            author_slug VARCHAR(255) NOT NULL
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS poems (
            id SERIAL PRIMARY KEY,
            author_id INT NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            title_slug VARCHAR(255) NOT NULL,
            poem TEXT NOT NULL,
            poem_url VARCHAR(511),
            request_id VARCHAR(255),
            upload_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (author_id, title_slug)  -- <-- Aquí la restricción UNIQUE
        );
        """)


def ensure_user(user_id: str) -> int:
    """
    Ensure a user exists in the database, creating it if necessary.

    Args:
        user_id (str): Unique identifier for the user.

    Returns:
        int: Database ID of the user.
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if user:
            return user['id']
        cur.execute(
            "INSERT INTO users (user_id) VALUES (%s) RETURNING id",
            (user_id,)
        )
        return cur.fetchone()['id']


def ensure_author(user_db_id: int, author_name: str) -> int:
    """
    Ensure an author exists for a given user, creating it if necessary.

    Args:
        user_db_id (int): ID of the user in the database.
        author_name (str): Name of the author.

    Returns:
        int: Database ID of the author.
    """
    author_slug = slugify(author_name)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id FROM authors WHERE user_id = %s AND author_slug = %s",
            (user_db_id, author_slug)
        )
        author = cur.fetchone()
        if author:
            # Optional: update author_name if changed
            cur.execute(
                "UPDATE authors SET author = %s WHERE id = %s",
                (author_name, author['id'])
            )
            return author['id']
        cur.execute(
            (
                "INSERT INTO authors (user_id, author_slug, author) "
                "VALUES (%s, %s, %s) RETURNING id"
            ),
            (user_db_id, author_slug, author_name)
        )
        return cur.fetchone()['id']


def upload_to_db(poem_dict: dict) -> str:
    """
    Insert or update a poem in the database.

    Args:
        poem_dict (dict): Dictionary with poem keys

    Returns:
        str: The generated poem URL slug (author_slug/title_slug).
    """

    MAIN_USER_ID = os.getenv("MAIN_USER_ID")
    if not MAIN_USER_ID:
        raise RuntimeError("MAIN_USER_ID is not set in environment variables.")

    user_id = str(poem_dict.get("user_id"))
    if not user_id:
        raise ValueError("Missing required field: user_id")

    author = poem_dict.get("author", "Unknown").strip()
    title = poem_dict.get("title", "Unknown").strip()
    text = poem_dict.get("text", "").strip()
    request_id = poem_dict.get("request_id", "").strip()

    user_db_id = ensure_user(user_id)
    author_db_id = ensure_author(user_db_id, author)

    title_slug = slugify(title)
    author_slug = slugify(author)
    if user_id == MAIN_USER_ID:
        poem_url = f"{author_slug}/{title_slug}"
    else:
        poem_url = f"id/{user_id}/{author_slug}/{title_slug}"

    upload_at = datetime.now().replace(microsecond=0)

    with get_db_cursor() as cur:
        cur.execute(
        (
            "INSERT INTO poems (author_id, title_slug, title, poem, poem_url, "
            "request_id, upload_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            "ON CONFLICT (author_id, title_slug) DO UPDATE SET "
            "title = EXCLUDED.title, "
            "poem = EXCLUDED.poem, "
            "poem_url = EXCLUDED.poem_url, "
            "request_id = EXCLUDED.request_id, "
            "upload_at = EXCLUDED.upload_at"
        ),
        (author_db_id, title_slug, title, text, poem_url, request_id,
         upload_at)
    )

    return poem_url


def get_poems_by_user(user_id: str) -> dict:
    """
    Retrieve all poems for a specific user.

    Args:
        user_id (str): Unique user identifier.

    Returns:
        dict: Nested dictionary with authors and their poems.
    """
    user_db_id = None
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return {}
        user_db_id = user['id']

        cur.execute("""
            SELECT a.author_slug, a.author, p.title_slug, p.title, p.poem,
                    p.request_id, p.upload_at, p.poem_url
            FROM authors a
            JOIN poems p ON p.author_id = a.id
            WHERE a.user_id = %s
            ORDER BY a.author, p.upload_at DESC
        """, (user_db_id,))

        rows = cur.fetchall()

    poems_dict = {}
    for row in rows:
        author_id = row['author_slug']
        if author_id not in poems_dict:
            poems_dict[author_id] = {
                "author": row["author"],
                "poems": {}
            }
        poems_dict[author_id]["poems"][row["title_slug"]] = {
            "title": row["title"],
            "poem": row["poem"],
            "request_id": row["request_id"],
            "upload_at": row["upload_at"].isoformat(),
            "poem_url": row["poem_url"]
        }
    return poems_dict


def get_poems_by_author(user_id: str, author_slug: str) -> dict | None:
    """
    Retrieve all poems by a specific author for a given user.

    Args:
        user_id (str): Unique user identifier.
        author_slug (str): Slug of the author's name.

    Returns:
        dict | None: Nested dictionary with author and poems data,
                     or None if the author does not exist.
    """
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, author
            FROM authors
            WHERE user_id = (SELECT id FROM users WHERE user_id = %s)
              AND author_slug = %s
        """, (user_id, author_slug))
        author_row = cur.fetchone()
        if not author_row:
            return None

        author_id = author_row['id']
        author = author_row['author']

        cur.execute("""
            SELECT title, title_slug, poem, poem_url, request_id, upload_at
            FROM poems
            WHERE author_id = %s
            ORDER BY upload_at DESC
        """, (author_id,))
        poems = cur.fetchall()

        return {
            author_slug: {
                "author": author,
                "poems": {
                    row['title_slug']: {
                        "title": row['title'],
                        "poem": row['poem'],
                        "poem_url": row['poem_url'],
                        "request_id": row['request_id'],
                        "upload_at": row['upload_at'].isoformat(),
                    }
                    for row in poems
                }
            }
        }



def get_poem(user_id: str, author_slug: str, title_slug: str) -> dict | None:
    """
    Retrieve a specific poem by author and title for a given user.

    Args:
        user_id (str): Unique user identifier.
        author_slug (str): Slug of the author's name.
        title_slug (str): Slug of the poem's title.

    Returns:
        dict | None: Poem data (author, title, text, request_id, upload_at)
                     or None if not found.
    """
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT a.author, p.title, p.poem, p.poem_url, p.request_id,
                    p.upload_at
            FROM poems p
            JOIN authors a ON p.author_id = a.id
            JOIN users u ON a.user_id = u.id
            WHERE u.user_id = %s
              AND a.author_slug = %s
              AND p.title_slug = %s
        """, (user_id, author_slug, title_slug))
        row = cur.fetchone()
        if not row:
            return None

        return {
            "author": row['author'],
            "title": row['title'],
            "poem": row['poem'],
            "poem_url": row['poem_url'],
            "request_id": row['request_id'],
            "upload_at": row['upload_at'].isoformat(),
        }


def delete_user_db(user_id: str) -> None:
    """
    Delete a user and all their related authors and poems.

    Args:
        user_id (str): Unique user identifier.

    Returns:
        None
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return
        cur.execute("DELETE FROM users WHERE id = %s", (user['id'],))


def delete_author_db(user_id: str, author: str) -> None:
    """
    Delete a specific author and all their poems for a given user.

    Args:
        user_id (str): Unique user identifier.
        author (str): Author name.

    Returns:
        None
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return
        user_db_id = user['id']

        author_slug = slugify(author)
        cur.execute(
            "SELECT id FROM authors WHERE user_id = %s AND author_slug = %s",
            (user_db_id, author_slug)
        )
        author_row = cur.fetchone()
        if not author_row:
            return

        cur.execute("DELETE FROM authors WHERE id = %s", (author_row['id'],))


def delete_poem_db(user_id: str, author: str, title: str) -> None:
    """
    Delete a specific poem by author and title for a given user.

    Args:
        user_id (str): Unique user identifier.
        author (str): Author name.
        title (str): Poem title.

    Returns:
        None
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return
        user_db_id = user['id']

        author_slug = slugify(author)
        title_slug = slugify(title)

        cur.execute(
            "SELECT id FROM authors WHERE user_id = %s AND author_slug = %s",
            (user_db_id, author_slug)
        )
        author_row = cur.fetchone()
        if not author_row:
            return

        cur.execute(
            "DELETE FROM poems WHERE author_id = %s AND title_slug = %s",
            (author_row['id'], title_slug)
        )
