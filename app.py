"""
Poem Management Flask Application

Provides web views and API endpoints to save, view, and delete poems by author and title.
"""

import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from utils.db_utils import (
    save_to_db,
    get_poems_by_user,
    delete_poem_db,
    delete_author_db,
    delete_user_db,
)
from utils.utils import markdown_to_html
from utils.logging_config import configure_logger

# --- Load Environment Variables ---
load_dotenv()
DB_DIR = os.getenv("DB_DIR")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

if not DB_DIR or not ALLOWED_USER_ID:
    raise RuntimeError("DB_DIR or ALLOWED_USER_ID environment variable is not set.")

ALLOWED_USERS = {user_id.strip() for user_id in ALLOWED_USER_ID.split(",")}

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing
logger = configure_logger("PoemInterface")


# --- Helper Functions ---
def not_found_poem():
    """
    Render a default poem page when no poem or author is found.
    """
    author = "El Programador."
    title = "No, no, no"
    poem = (
        "O el parámetro está mal</br>"
        "o el poema no lo tengo </br>"
        "o la web no funciona.</br>"
    )
    return render_template("poem.html", author=author, title=title, poem=poem)


def is_authorized(user_id: str) -> bool:
    """
    Check if the user_id is authorized.
    """
    return user_id in ALLOWED_USERS


def validate_json_fields(json_data: dict, required_fields: list):
    """
    Validate that the JSON data contains all required fields.
    Returns (True, "") if valid; otherwise (False, error message).
    """
    missing = [field for field in required_fields if field not in json_data]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, ""


# --- Web View Routes ---
@app.route("/", strict_slashes=False)
def view_poems():
    """
    View all poems by the authorized user.
    """
    user_poems = get_poems_by_user(ALLOWED_USER_ID)
    return render_template("poems_list.html", poems_data=user_poems)


@app.route("/<author_key>", strict_slashes=False)
def view_author_poems(author_key):
    """
    View all poems by a specific author.
    """
    user_poems = get_poems_by_user(ALLOWED_USER_ID)
    if author_key in user_poems:
        return render_template(
            "poems_author_list.html",
            author_slug=author_key,
            author_data=user_poems[author_key],
        )
    return not_found_poem()


@app.route("/<author_key>/<title_key>", strict_slashes=False)
def view_poem(author_key, title_key):
    """
    View a specific poem by author and title.
    """
    user_poems = get_poems_by_user(ALLOWED_USER_ID)
    if author_key in user_poems:
        author = user_poems[author_key]["author"]
        poems = user_poems[author_key]["poems"]
        if title_key in poems:
            title = poems[title_key]["title"]
            poem_html = markdown_to_html(poems[title_key]["poem"])
            return render_template("poem.html", author=author, title=title, poem=poem_html)
    return not_found_poem()


@app.errorhandler(404)
def page_not_found(e):
    """
    Custom 404 error handler to display the 'No, no, no' poem template.
    """
    return not_found_poem()


@app.errorhandler(500)
def internal_server_error(e):
    """
    Custom 500 error handler to display the 'No, no, no' poem template.
    """
    return not_found_poem()


# --- API Endpoints ---

@app.route("/api/save_poem", methods=["POST"])
def api_save_poem():
    """
    Save a poem to the database.
    Expects JSON with: user_id, request_id, author, title, text.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    required_fields = ["user_id", "request_id", "author", "title", "text"]
    valid, err_msg = validate_json_fields(data, required_fields)
    if not valid:
        return jsonify({"error": err_msg}), 400

    user_id = data["user_id"]
    if not is_authorized(user_id):
        return jsonify({"error": "Unauthorized: Invalid User ID"}), 401

    try:
        poem_url = save_to_db(data)
    except Exception as e:
        logger.error(f"Error saving poem: {e}", exc_info=True)
        return jsonify({"error": "Failed to save poem"}), 500

    return jsonify({"status": "success", "poem_url": poem_url}), 201


@app.route("/api/delete_poem", methods=["POST"])
def api_delete_poem():
    """
    Delete a specific poem by user_id, author, and title.
    Expects JSON with: user_id, author, title.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    required_fields = ["user_id", "author", "title"]
    valid, err_msg = validate_json_fields(data, required_fields)
    if not valid:
        return jsonify({"error": err_msg}), 400

    user_id = data["user_id"]
    if not is_authorized(user_id):
        return jsonify({"error": "Unauthorized: Invalid User ID"}), 401

    try:
        delete_poem_db(user_id, data["author"], data["title"])
    except Exception as e:
        logger.error(f"Error deleting poem: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete poem"}), 500

    return jsonify({"status": "success"}), 200


@app.route("/api/delete_author", methods=["POST"])
def api_delete_author():
    """
    Delete all poems by a specific author for a user.
    Expects JSON with: user_id, author.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    required_fields = ["user_id", "author"]
    valid, err_msg = validate_json_fields(data, required_fields)
    if not valid:
        return jsonify({"error": err_msg}), 400

    user_id = data["user_id"]
    if not is_authorized(user_id):
        return jsonify({"error": "Unauthorized: Invalid User ID"}), 401

    try:
        delete_author_db(user_id, data["author"])
    except Exception as e:
        logger.error(f"Error deleting author: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete author"}), 500

    return jsonify({"status": "success"}), 200


@app.route("/api/delete_all", methods=["POST"])
def api_delete_all():
    """
    Delete all poems for a user.
    Expects JSON with: user_id.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    required_fields = ["user_id"]
    valid, err_msg = validate_json_fields(data, required_fields)
    if not valid:
        return jsonify({"error": err_msg}), 400

    user_id = data["user_id"]
    if not is_authorized(user_id):
        return jsonify({"error": "Unauthorized: Invalid User ID"}), 401

    try:
        delete_user_db(user_id)
    except Exception as e:
        logger.error(f"Error deleting all poems: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete poems"}), 500

    return jsonify({"status": "success"}), 200


# --- Health Check Endpoint ---
@app.route("/ping", methods=["GET"])
def ping():
    """
    Health check endpoint.
    """
    return jsonify(status="ok"), 200


# --- Main Entry Point ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
