import os
import io
import json
from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def inspect_receipt_image(image_bytes: bytes) -> dict:
    """
    Analyzes an uploaded receipt/damage image (JPEG/PNG) using Gemini Vision AI.
    Extracts structured data and verifies image authenticity for potential forgery/tampering.
    """
    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY missing from environment or .env file."
        }

    try:
        # Validate image format and integrity using Pillow
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        image = Image.open(io.BytesIO(image_bytes))  # Reopen after verification

        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = """
        You are an automated claims auditor. Inspect this image for return/refund validation.
        Extract key details and evaluate whether the receipt or damaged item photo shows signs of digital manipulation, Photoshop editing, or font inconsistencies.

        Return ONLY a JSON object with this exact schema:
        {
            "is_valid_receipt": true,
            "vendor_name": "string or null",
            "extracted_order_id": "string or null",
            "total_amount": 0.00,
            "tampering_detected": false,
            "tampering_notes": "description of edits or 'None'"
        }
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        structured_output = json.loads(response.text)

        return {
            "success": True,
            "vision_analysis": structured_output
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Vision processing failed: {str(e)}"
        }