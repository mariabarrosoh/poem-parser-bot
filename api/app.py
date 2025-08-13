"""
Poem Management Flask Application

Provides web views and API endpoints to upload, view, and delete poems.
"""

import os
import threading

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flasgger import Swagger
from apscheduler.schedulers.background import BackgroundScheduler
import requests

from utils.db_utils import (
    init_db,
    upload_to_db,
    get_poem,
    get_poems_by_author,
    get_poems_by_user,
    delete_poem_db,
    delete_author_db,
    delete_user_db,
)
from utils.utils import markdown_to_html
from utils.logging_config import configure_logger


# --- Load Environment Variables ---
load_dotenv()

ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
MAIN_USER_ID = os.getenv("MAIN_USER_ID")
APP_NAME = os.getenv("APP_NAME")
API_DOMAIN = os.getenv("API_DOMAIN")

if not ALLOWED_USER_ID or not APP_NAME or not MAIN_USER_ID:
    raise RuntimeError("ALLOWED_USER_ID, APP_NAME, MAIN_USER_ID or API_DOMAIN "
                       "environment variable is not set.")

ALLOWED_USERS = {user_id.strip() for user_id in ALLOWED_USER_ID.split(",")}


# --- Create DB tables if not exist ---
init_db()


# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing
swagger = Swagger(app, template={
    "swagger": "2.0",
    "info": {
        "title": f"{APP_NAME} API",
        "description": "API for uploading, deleting, and managing poems.",
        "version": "1.0.0"
    }
})
logger = configure_logger(APP_NAME)


# --- Helper Functions ---

def keep_alive():
    """
    Function that pings the /ping endpoint to keep the app awake.
    """
    try:
        url = f"{API_DOMAIN}/ping"
        logger.info("Pinging: %s", url)
        requests.get(url, timeout=60)
    except Exception as e:
        logger.error("Ping error: %s", e, exc_info=True)


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
    return render_template("poem.html", author=author, title=title,
                           poem=poem, app_name=APP_NAME)


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
@app.route("/")
def view_poems():
    """
    View all poems by the authorized user.
    """
    user_id = MAIN_USER_ID
    if is_authorized(user_id):
        user_poems = get_poems_by_user(MAIN_USER_ID)
        return render_template("poems_list.html", poems_data=user_poems,
                               app_name=APP_NAME)
    return not_found_poem()


@app.route("/id/<user_id>")
def view_poems_other(user_id):
    """
    View all poems by the authorized user.
    """
    if is_authorized(user_id):
        user_poems = get_poems_by_user(user_id)
        return render_template("poems_list.html", poems_data=user_poems,
                               app_name=APP_NAME)
    return not_found_poem()


@app.route("/<author_key>", strict_slashes=False)
def view_author_poems(author_key):
    """
    View all poems by a specific author.
    """
    user_id = MAIN_USER_ID
    if is_authorized(user_id):
        author_data = get_poems_by_author(user_id, author_key)
        if author_data:
            return render_template(
                "poems_author_list.html", author_slug=author_key,
                author_data=author_data[author_key], app_name=APP_NAME
            )
    return not_found_poem()


@app.route("/id/<user_id>/<author_key>", strict_slashes=False)
def view_author_poems_others(user_id, author_key):
    """
    View all poems by a specific author.
    """
    if is_authorized(user_id):
        author_data = get_poems_by_author(user_id, author_key)
        if author_data:
            return render_template(
                "poems_author_list.html", author_slug=author_key,
                author_data=author_data[author_key], app_name=APP_NAME
            )
    return not_found_poem()


@app.route("/<author_key>/<title_key>", strict_slashes=False)
def view_poem(author_key, title_key):
    """
    View a specific poem by author and title.
    """
    user_id = MAIN_USER_ID
    if is_authorized(user_id):
        poem = get_poem(user_id, author_key, title_key)
        if poem:
            poem_html = markdown_to_html(poem["poem"])
            return render_template("poem.html", author=poem["author"],
                                   title=poem["title"], poem=poem_html,
                                   app_name=APP_NAME)
    return not_found_poem()


@app.route("/id/<user_id>/<author_key>/<title_key>", strict_slashes=False)
def view_poem_others(user_id, author_key, title_key):
    """
    View a specific poem by author and title.
    """
    if is_authorized(user_id):
        poem = get_poem(user_id, author_key, title_key)
        if poem:
            poem_html = markdown_to_html(poem["poem"])
            return render_template("poem.html", author=poem["author"],
                                   title=poem["title"], poem=poem_html,
                                   app_name=APP_NAME)
        return not_found_poem()


@app.errorhandler(404)
def page_not_found(_):
    """
    Custom 404 error handler to display the 'No, no, no' poem template.
    """
    return not_found_poem()


@app.errorhandler(500)
def internal_server_error(_):
    """
    Custom 500 error handler to display the 'No, no, no' poem template.
    """
    return not_found_poem()


# --- API DB Endpoints ---

@app.route("/api/upload_poem", methods=["POST"])
def api_upload_poem():
    """
    Upload a poem to the database.
    ---
    tags:
      - Poems
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            user_id:
              type: string
            request_id:
              type: string
            author:
              type: string
            title:
              type: string
            text:
              type: string
    responses:
      201:
        description: Poem uploaded successfully
      400:
        description: Invalid request
      401:
        description: Unauthorized
      500:
        description: Server error
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
        poem_url = upload_to_db(data)
    except Exception as e:
        logger.error("Error uploading poem: %s", e, exc_info=True)
        return jsonify({"error": "Failed to upload poem"}), 500

    return jsonify({"status": "success", "poem_url": poem_url}), 201


@app.route("/api/delete_poem", methods=["POST"])
def api_delete_poem():
    """
    Delete a specific poem by user_id, author, and title.
    ---
    tags:
      - Poems
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            user_id:
              type: string
            author:
              type: string
            title:
              type: string
    responses:
      200:
        description: Poem deleted successfully
      400:
        description: Invalid request
      401:
        description: Unauthorized
      500:
        description: Server error
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
        logger.error("Error deleting poem: %s", e, exc_info=True)
        return jsonify({"error": "Failed to delete poem"}), 500

    return jsonify({"status": "success"}), 200


@app.route("/api/delete_author", methods=["POST"])
def api_delete_author():
    """
    Delete all poems by a specific author for a user.
    ---
    tags:
      - Poems
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            user_id:
              type: string
              example: "12345"
            author:
              type: string
              example: "Emily Dickinson"
    responses:
      200:
        description: All poems by the author deleted successfully
      400:
        description: Invalid request or missing fields
      401:
        description: Unauthorized
      500:
        description: Server error
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
        logger.error("Error deleting author: %s", e, exc_info=True)
        return jsonify({"error": "Failed to delete author"}), 500

    return jsonify({"status": "success"}), 200


@app.route("/api/delete_all", methods=["POST"])
def api_delete_all():
    """
    Delete all poems for a user.
    ---
    tags:
      - Poems
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            user_id:
              type: string
              example: "12345"
    responses:
      200:
        description: All poems deleted successfully
      400:
        description: Invalid request or missing fields
      401:
        description: Unauthorized
      500:
        description: Server error
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
        logger.error("Error deleting all poems: %s", e, exc_info=True)
        return jsonify({"error": "Failed to delete poems"}), 500

    return jsonify({"status": "success"}), 200


# --- Health Check Endpoint ---

@app.route("/ping", methods=["GET"])
def ping():
    """
    Health check endpoint.
    ---
    tags:
      - Health
    responses:
      200:
        description: App is running
    """
    return "App is running 🚀"


# --- Configure the scheduler ---

scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, 'interval', hours=1)  # Every hour
scheduler.start()

# --- Main Entry Point ---
if __name__ == "__main__":

    # Ping immediately on startup in a separate thread
    threading.Thread(target=keep_alive, daemon=True).start()

    try:
        app.run(host="0.0.0.0", port=8080, debug=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
