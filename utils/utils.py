# utils/utils.py
import base64

def encode_image_to_base64(image_path: str, request_id: str) -> str:
    """
    Encodes an image to Base64 format.

    Args:
        image_path (str): Path to the image file.
        request_id (str): Unique request identifier (used for error logging).

    Returns:
        str: Base64-encoded string of the image content.
    """
    if not image_path.lower().endswith((".jpg", ".jpeg", ".png")):
        raise ValueError(f"{request_id} | Only .jpg, .jpeg, or .png images are supported.")

    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            return base64.b64encode(image_bytes).decode("utf-8")
    except FileNotFoundError:
        raise RuntimeError(f"{request_id} | Image file not found: {image_path}")
    except Exception as e:
        raise RuntimeError(f"{request_id} | Failed to encode image: {e}")
