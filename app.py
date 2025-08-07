import os
import uuid
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS
from flasgger import Swagger, swag_from

from process import process
from utils.logging_config import configure_logger

load_dotenv()

# Load environment variables
DATA_DIR = os.getenv("DATA_DIR")
if not DATA_DIR:
    raise RuntimeError("DATA_DIR environment variable is not set.")

MAX_IMAGES = int(os.getenv("MAX_IMAGES", "5"))

# --- Configuration ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- App Setup ---
app = Flask(__name__)
CORS(app)  # Enable CORS
Swagger(app)  # Enable Swagger UI at /apidocs
logger = configure_logger("PoemParserAPI")

# --- Utils ---
def allowed_file(filename: str):
    """Check if the file has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_request_id():
    """Generate a short unique ID for each request."""
    return uuid.uuid4().hex[:16]

# --- Routes ---
@app.route('/')
def home():
    return "", 302, {"Location": "/apidocs"}

@app.route('/api/parse', methods=['POST'])
@swag_from({
    'tags': ['Poem Parsing'],
    'consumes': ['multipart/form-data'],
    'parameters': [
        {
            'name': 'images',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'One or more image files',
            'collectionFormat': 'multi'
        }
    ],
    'responses': {
        200: {
            'description': 'Poem extracted successfully',
            'examples': {
                'application/json': {
                    "request_id": "abc123",
                    "title": "My Poem",
                    "html": "<html>...</html>",
                    "markdown": "# Poem text",
                }
            }
        },
        400: {'description': 'Invalid request (missing or wrong files)'},
        500: {'description': 'Internal server error'}
    }
})
def parse_poem():
    """
    Endpoint to extract poem content from uploaded image(s).
    ---
    """
    request_id = generate_request_id()
    logger.info(f"{request_id} | Received parse request")

    if 'images' not in request.files:
        logger.warning(f"{request_id} | No 'images' field in request")
        return jsonify({"error": "No images part in the request"}), 400

    images = request.files.getlist("images")
    if not images or not all(allowed_file(img.filename) for img in images):
        logger.warning(f"{request_id} | Invalid or missing image files.")
        return jsonify({"error": "Invalid or missing image files. Accepted formats: JPG, JPEG, PNG."}), 400

    image_paths = []
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        if len(images) >= MAX_IMAGES:
            logger.warning(f"{request_id} | Maximum number of images exceeded: {len(images)} provided, limit is {MAX_IMAGES}.")
            return jsonify({f"error": f"Maximum number of images exceeded: {len(images)} provided, limit is {MAX_IMAGES}."}), 400

        for img in images:
            filename = secure_filename(img.filename)
            save_path = os.path.join(DATA_DIR, f"{request_id}_{filename}")
            img.save(save_path)
            image_paths.append(save_path)

        title, html, markdown = process(image_paths, request_id)

        if not any([title, html, markdown]):
            return jsonify({"error": "No poem extracted from images."}), 400

        return jsonify({
            "request_id": request_id,
            "title": title,
            "markdown": markdown,
            "html": html
        })

    except Exception as e:
        logger.exception(f"{request_id} | Exception during processing: {e}")
        return jsonify({"error": "Internal server error. Please try again later."}), 500

    finally:
        for path in image_paths:
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"{request_id} | Failed to delete {path}: {e}")

# --- Health Check ---
@app.route('/ping', methods=['GET'])
@swag_from({
    'tags': ['Health Check'],
    'responses': {
        200: {
            'description': 'API is healthy',
            'examples': {
                'application/json': {
                    'status': 'ok'
                }
            }
        }
    }
})
def ping():
    """Health check endpoint"""
    return jsonify(status="ok"), 200

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found errors"""
    if request.accept_mimetypes.accept_json:
        return jsonify(error="Not Found"), 404
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 Internal Server Error"""
    if request.accept_mimetypes.accept_json:
        return jsonify(error="Internal Server Error"), 500
    return render_template("500.html"), 500

@app.errorhandler(503)
def service_unavailable(error):
    """Handle 503 Service Unavailable"""
    if request.accept_mimetypes.accept_json:
        return jsonify(
            error="Service Unavailable"), 503
    return render_template("503.html"), 503

# --- Entry Point ---
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=False)
