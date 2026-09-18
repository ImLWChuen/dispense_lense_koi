import cv2
import numpy as np

def analyze_deposit(image_bytes: bytes) -> dict:
    """
    Analyze the deposit size from an image and return observation info.
    """
    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Failed to decode image.")
        
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Thresholding (using Otsu's method for robustness)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return {"observation_type": "deposit_size", "value": "UNKNOWN", "area": 0}
        
    # Get largest contour (assume it's the deposit)
    largest_contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest_contour)
    
    # We will use simple heuristics.
    # In a real scenario, this would be calibrated.
    # We assume standard size is between 1000 and 5000 pixels.
    if area < 1000:
        deposit_size = "TOO_SMALL"
    elif area > 5000:
        deposit_size = "TOO_LARGE"
    else:
        deposit_size = "NORMAL"
        
    return {
        "observation_type": "deposit_size", 
        "value": deposit_size, 
        "area": area
    }
