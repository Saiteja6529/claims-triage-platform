import io
import json
import os
from PIL import Image
from PIL.ExifTags import TAGS
from google import genai

def extract_exif_metadata(image_bytes: bytes) -> dict:
    """Extracts EXIF metadata to detect screenshots, editing tools, and original photo dates."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        exif_data = image._getexif()
        
        if not exif_data:
            return {
                "has_exif": False,
                "is_likely_screenshot_or_edited": True,
                "date_taken": None,
                "camera_model": None
            }

        parsed_exif = {}
        for tag, value in exif_data.items():
            tag_name = TAGS.get(tag, tag)
            parsed_exif[tag_name] = value

        date_taken = parsed_exif.get("DateTimeOriginal") or parsed_exif.get("DateTime")
        camera_model = f"{parsed_exif.get('Make', '')} {parsed_exif.get('Model', '')}".strip()

        return {
            "has_exif": True,
            "is_likely_screenshot_or_edited": False,
            "date_taken": str(date_taken) if date_taken else None,
            "camera_model": camera_model if camera_model else "Unknown"
        }
    except Exception as e:
        return {"has_exif": False, "is_likely_screenshot_or_edited": True, "error": str(e)}

def assess_physical_damage(image_bytes: bytes, claim_reason: str) -> dict:
    """Analyzes damage severity and cross-checks with claim reason using google-genai."""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"success": False, "error": "GEMINI_API_KEY environment variable is not set."}

        client = genai.Client(api_key=api_key)
        image = Image.open(io.BytesIO(image_bytes))
        
        prompt = f"""
        You are an expert insurance and e-commerce damage inspection AI.
        Analyze this claim photo provided by a customer who filed a claim for: "{claim_reason}".

        Return ONLY a JSON object with this exact structure:
        {{
            "defect_detected": "string (description of damage seen)",
            "matches_claim_reason": true/false,
            "damage_severity_score": float (between 0.0 and 1.0),
            "severity_category": "COSMETIC" | "MODERATE" | "CRITICAL",
            "fraud_risk_notes": "string or None"
        }}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image]
        )
        
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        analysis = json.loads(clean_text)

        return {"success": True, "damage_analysis": analysis}
    except Exception as e:
        return {"success": False, "error": str(e)}