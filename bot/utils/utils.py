"""
Utility Functions Module
"""

import base64


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode an image file to Base64 format.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: Base64-encoded string of the image content.

    Raises:
        ValueError: If the file extension is not supported.
        RuntimeError: If the file is missing or cannot be read.
    """
    if not image_path.lower().endswith((".jpg", ".jpeg", ".png")):
        raise ValueError(
            "Only .jpg, .jpeg, or .png images are supported.")

    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            return base64.b64encode(image_bytes).decode("utf-8")
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Image file not found: {image_path}") from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to encode image: {e}") from e
