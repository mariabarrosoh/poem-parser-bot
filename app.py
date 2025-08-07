import os
import uuid
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS
from flasgger import Swagger, swag_from

from process import process
from utils.logging_config import configure_logger

# --- Configuration ---
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# --- App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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
        logger.warning(f"{request_id} | Invalid or missing image files")
        return jsonify({"error": "Invalid or missing image files"}), 400

    image_paths = []
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    try:
        for img in images:
            filename = secure_filename(img.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{request_id}_{filename}")
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
        logger.exception(f"{request_id} | Exception during processing")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

    finally:
        for path in image_paths:
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"{request_id} | Failed to delete {path}: {e}")

@app.route('/ping', methods=['GET'])
@swag_from({
    'tags': ['Health Check'],
    'responses': {
        200: {
            'description': 'API is running',
            'examples': {
                'application/json': {
                    'status': 'ok',
                    'message': 'Poem Parser API is up and running!'
                }
            }
        }
    }
})
def ping():
    """
    Simple health check endpoint.
    ---
    """
    return jsonify({
        "status": "ok",
        "message": "Poem Parser API is up and running!"
    }), 200

# --- Entry Point ---
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=False)
