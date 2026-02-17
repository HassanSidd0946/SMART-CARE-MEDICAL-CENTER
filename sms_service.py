"""
Twilio SMS Service
Handles sending SMS notifications for appointment confirmations.
"""

import os
import re
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Initialize Twilio Client
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("✅ Twilio client initialized successfully")
except Exception as e:
    print(f"⚠️ Failed to initialize Twilio client: {e}")
    twilio_client = None


def clean_phone_number(phone: str) -> str:
    """
    Clean and format phone number.
    
    Removes spaces, dashes, parentheses, and ensures proper format.
    Adds +91 for Indian numbers if not present.
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Cleaned phone number with country code
        
    Examples:
        "9876543210" -> "+919876543210"
        "+1 (785) 503-9220" -> "+17855039220"
        "987-654-3210" -> "+919876543210"
    """
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # If number doesn't start with +, assume it's Indian and add +91
    if not cleaned.startswith('+'):
        # If it's 10 digits, assume Indian number
        if len(cleaned) == 10:
            cleaned = f"+91{cleaned}"
        # If it's 11 digits starting with 91, add +
        elif len(cleaned) == 12 and cleaned.startswith('91'):
            cleaned = f"+{cleaned}"
        else:
            # Default to adding +91
            cleaned = f"+91{cleaned}"
    
    return cleaned


def send_sms(to_number: str, body: str) -> dict:
    """
    Send SMS using Twilio.
    
    This function sends SMS in a fail-safe manner:
    - Cleans the phone number
    - Handles all errors gracefully
    - Returns status with detailed information
    
    Args:
        to_number: Recipient phone number (can be any format)
        body: SMS message content
        
    Returns:
        Dictionary with status and details:
        {
            "success": bool,
            "message": str,
            "sid": str (if successful),
            "error": str (if failed)
        }
    """
    # Validate Twilio client
    if not twilio_client:
        error_msg = "Twilio client not initialized. Check your credentials."
        print(f"❌ SMS Error: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "error": "CLIENT_NOT_INITIALIZED"
        }
    
    # Validate inputs
    if not to_number or not body:
        error_msg = "Phone number and message body are required"
        print(f"❌ SMS Error: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "error": "INVALID_INPUT"
        }
    
    try:
        # Clean the phone number
        cleaned_number = clean_phone_number(to_number)
        print(f"📱 Sending SMS to: {cleaned_number}")
        print(f"📝 Message: {body[:50]}...")
        
        # Send SMS via Twilio
        message = twilio_client.messages.create(
            body=body,
            from_=TWILIO_PHONE_NUMBER,
            to=cleaned_number
        )
        
        print(f"✅ SMS sent successfully! SID: {message.sid}")
        
        return {
            "success": True,
            "message": "SMS sent successfully",
            "sid": message.sid,
            "to": cleaned_number,
            "from": TWILIO_PHONE_NUMBER
        }
    
    except TwilioRestException as e:
        # Twilio-specific errors (invalid number, insufficient credits, etc.)
        error_msg = f"Twilio API Error: {e.msg}"
        print(f"❌ {error_msg}")
        print(f"   Error Code: {e.code}")
        
        return {
            "success": False,
            "message": error_msg,
            "error": f"TWILIO_ERROR_{e.code}",
            "error_code": e.code
        }
    
    except Exception as e:
        # Any other unexpected errors
        error_msg = f"Unexpected error sending SMS: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "success": False,
            "message": error_msg,
            "error": "UNEXPECTED_ERROR"
        }


def send_appointment_confirmation(
    patient_name: str,
    phone_number: str,
    appointment_time: str,
    reason: str,
    appointment_id: int
) -> dict:
    """
    Send appointment confirmation SMS with formatted message.
    
    This is a specialized function for appointment confirmations
    that creates a well-formatted message.
    
    Args:
        patient_name: Patient's name
        phone_number: Patient's phone number
        appointment_time: Appointment date/time string
        reason: Reason for appointment
        appointment_id: Appointment ID from database
        
    Returns:
        Dictionary with status and details
    """
    # Create formatted message
    message_body = f"""
🏥 Smart Care Medical Center

Dear {patient_name},

Your appointment has been confirmed!

📅 Date/Time: {appointment_time}
🩺 Reason: {reason}
🆔 Booking ID: #{appointment_id}

📍 Location: Smart Care Medical Center
📞 Contact: +91-11-4567-8900

To cancel, reply CANCEL or call us.

Thank you for choosing Smart Care!
    """.strip()
    
    return send_sms(phone_number, message_body)


def send_appointment_cancellation(
    patient_name: str,
    phone_number: str,
    appointment_time: str,
    appointment_id: int
) -> dict:
    """
    Send appointment cancellation SMS.
    
    Args:
        patient_name: Patient's name
        phone_number: Patient's phone number
        appointment_time: Appointment date/time that was canceled
        appointment_id: Appointment ID
        
    Returns:
        Dictionary with status and details
    """
    message_body = f"""
🏥 Smart Care Medical Center

Dear {patient_name},

Your appointment has been CANCELED.

📅 Canceled: {appointment_time}
🆔 Booking ID: #{appointment_id}

To reschedule, please call us at:
📞 +91-11-4567-8900

Thank you!
    """.strip()
    
    return send_sms(phone_number, message_body)


# Test function
if __name__ == "__main__":
    print("🧪 Testing Twilio SMS Service")
    print("-" * 50)
    
    # Test phone number cleaning
    test_numbers = [
        "9876543210",
        "+91 98765 43210",
        "987-654-3210",
        "+1 (785) 503-9220"
    ]
    
    print("\n📱 Testing phone number cleaning:")
    for num in test_numbers:
        cleaned = clean_phone_number(num)
        print(f"   {num} -> {cleaned}")
    
    # Test SMS sending (replace with your actual number for testing)
    print("\n📤 Testing SMS sending:")
    print("   (Replace test number in code to actually send)")
    
    # Uncomment and replace with your number to test:
    # result = send_sms("+919876543210", "Test message from Smart Care!")
    # print(f"   Result: {result}")