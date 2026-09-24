import pytest
from app.payment_tool import execute_stripe_refund
from app.ocr_tool import parse_receipt_image

def test_stripe_payment_tool():
    """Verify automated Stripe refund tool execution."""
    result = execute_stripe_refund(order_id="ORDER101", amount=49.99, customer_id="CUST_991")
    assert result["success"] is True
    assert result["amount_refunded"] == 49.99
    assert result["refund_id"].startswith("re_")

def test_ocr_receipt_tool():
    """Verify image processing and order ID extraction tool."""
    # Create a 100x100 blank red test image in memory
    from PIL import Image
    import io
    
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    
    ocr_result = parse_receipt_image(img_bytes.getvalue())
    assert ocr_result["success"] is True
    assert ocr_result["detected_order_id"] == "ORDER101"