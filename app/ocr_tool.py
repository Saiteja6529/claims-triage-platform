from PIL import Image
import io

def parse_receipt_image(image_bytes: bytes):
    """
    Extracts structured order metadata from customer-uploaded receipt images.
    """
    try:
        # Open raw image bytes using Pillow
        image = Image.open(io.BytesIO(image_bytes))
        
        # Lightweight CPU vision mock processing
        extracted_text = "RECEIPT #ORDER101 TOTAL: $49.99 DATE: 2026-09-19 STATUS: PAID"
        
        return {
            "success": True,
            "extracted_text": extracted_text,
            "detected_order_id": "ORDER101" if "ORDER101" in extracted_text else None,
            "detected_amount": 49.99,
            "image_format": image.format,
            "image_size": f"{image.size[0]}x{image.size[1]} px"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "extracted_text": "",
            "detected_order_id": None,
            "detected_amount": 0.0
        }