"""
Twilio WhatsApp Service
Handles sending WhatsApp notifications for appointment confirmations.
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
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# TEST MODE - Set to True to simulate WhatsApp without actually sending
# Useful for development and when Twilio sandbox daily limit is exceeded
WHATSAPP_TEST_MODE = os.getenv("WHATSAPP_TEST_MODE", "false").lower() == "true"

# Initialize Twilio Client
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print(f"✅ Twilio WhatsApp client initialized successfully")
    print(f"📱 WhatsApp Sandbox Number: {TWILIO_WHATSAPP_NUMBER}")
except Exception as e:
    print(f"⚠️ Failed to initialize Twilio client: {e}")
    twilio_client = None


def clean_phone_number(phone: str) -> str:
    """
    Clean and format phone number for WhatsApp.
    
    Removes spaces, dashes, parentheses, and ensures proper format.
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Cleaned phone number with country code (without whatsapp: prefix)
        
    Examples:
        "9876543210" -> "+919876543210"
        "+92 332 082 5825" -> "+923320825825"
        "332-082-5825" -> "+923320825825"
    """
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # If number doesn't start with +, add country code
    if not cleaned.startswith('+'):
        # Pakistani number (10 digits starting with 3)
        if len(cleaned) == 10 and cleaned.startswith('3'):
            cleaned = f"+92{cleaned}"
        # Pakistani number (12 digits starting with 92)
        elif len(cleaned) == 12 and cleaned.startswith('92'):
            cleaned = f"+{cleaned}"
        # Indian number (10 digits)
        elif len(cleaned) == 10:
            cleaned = f"+91{cleaned}"
        # Default to adding +92 for Pakistan
        else:
            cleaned = f"+92{cleaned}"
    
    return cleaned


def send_whatsapp(to_number: str, body: str) -> dict:
    """
    Send WhatsApp message using Twilio.
    
    This function sends WhatsApp messages in a fail-safe manner:
    - Cleans the phone number
    - Adds 'whatsapp:' prefix to both from and to numbers
    - Handles all errors gracefully
    - Returns status with detailed information
    
    Args:
        to_number: Recipient phone number (can be any format)
        body: WhatsApp message content
        
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
        print(f"❌ WhatsApp Error: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "error": "CLIENT_NOT_INITIALIZED"
        }
    
    # Validate inputs
    if not to_number or not body:
        error_msg = "Phone number and message body are required"
        print(f"❌ WhatsApp Error: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "error": "INVALID_INPUT"
        }
    
    # Clean the phone number
    cleaned_number = clean_phone_number(to_number)
    
    # TEST MODE - Simulate sending without hitting Twilio API
    if WHATSAPP_TEST_MODE:
        print(f"🧪 [TEST MODE] WhatsApp message simulation")
        print(f"   To: {cleaned_number}")
        print(f"   Message: {body[:100]}...")
        print(f"✅ [TEST MODE] WhatsApp message logged (not actually sent)")
        
        return {
            "success": True,
            "message": "WhatsApp message simulated (TEST MODE)",
            "sid": f"TEST_{cleaned_number}",
            "status": "simulated",
            "to": cleaned_number,
            "from": TWILIO_WHATSAPP_NUMBER,
            "test_mode": True
        }
    
    try:
        # Add WhatsApp prefix
        whatsapp_from = f"whatsapp:{TWILIO_WHATSAPP_NUMBER}"
        whatsapp_to = f"whatsapp:{cleaned_number}"
        
        print(f"💬 Sending WhatsApp message")
        print(f"   From: {whatsapp_from}")
        print(f"   To: {whatsapp_to}")
        print(f"   Message: {body[:50]}...")
        
        # Send WhatsApp message via Twilio
        message = twilio_client.messages.create(
            body=body,
            from_=whatsapp_from,
            to=whatsapp_to
        )
        
        print(f"✅ WhatsApp sent successfully! SID: {message.sid}")
        print(f"📊 Initial Status: {message.status}")
        
        return {
            "success": True,
            "message": "WhatsApp message sent successfully",
            "sid": message.sid,
            "status": message.status,
            "to": cleaned_number,
            "from": TWILIO_WHATSAPP_NUMBER
        }
    
    except TwilioRestException as e:
        # Twilio-specific errors
        error_msg = f"Twilio API Error: {e.msg}"
        print(f"❌ {error_msg}")
        print(f"   Error Code: {e.code}")
        
        # Auto-enable test mode for daily limit errors
        if e.code == 63038:  # Daily message limit exceeded
            print(f"\n⚠️ DAILY LIMIT EXCEEDED!")
            print(f"   💡 TIP: Set WHATSAPP_TEST_MODE=true in .env to continue testing")
            print(f"   📝 Message would have been sent to: {cleaned_number}")
            print(f"   📩 Message content: {body[:100]}...")
        
        # Common error codes
        if e.code == 63007:
            print("   💡 Hint: User has not joined the WhatsApp sandbox. Ask them to send 'join <code>' to the sandbox number.")
        elif e.code == 21211:
            print("   💡 Hint: Invalid 'To' phone number.")
        elif e.code == 63016:
            print("   💡 Hint: Message failed to send. User may have opted out or number is invalid.")
        
        return {
            "success": False,
            "message": error_msg,
            "error": f"TWILIO_ERROR_{e.code}",
            "error_code": e.code
        }
    
    except Exception as e:
        # Any other unexpected errors
        error_msg = f"Unexpected error sending WhatsApp: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "success": False,
            "message": error_msg,
            "error": "UNEXPECTED_ERROR"
        }


def send_appointment_confirmation_whatsapp(
    patient_name: str,
    phone_number: str,
    appointment_time: str,
    reason: str,
    appointment_id: int
) -> dict:
    """
    Send appointment confirmation via WhatsApp with formatted message.
    
    Args:
        patient_name: Patient's name
        phone_number: Patient's WhatsApp number
        appointment_time: Appointment date/time string
        reason: Reason for appointment
        appointment_id: Appointment ID from database
        
    Returns:
        Dictionary with status and details
    """
    # Create formatted message (WhatsApp supports emojis and formatting)
    message_body = f"""
🏥 *Smart Care Medical Center*

Dear *{patient_name}*,

Your appointment has been confirmed! ✅

📅 *Date/Time:* {appointment_time}
🩺 *Reason:* {reason}
🆔 *Booking ID:* #{appointment_id}

📍 *Location:* Smart Care Medical Center
📞 *Contact:* +91-11-4567-8900

To cancel, reply *CANCEL* or call us.

Thank you for choosing Smart Care! 🙏
    """.strip()
    
    return send_whatsapp(phone_number, message_body)


def send_appointment_cancellation_whatsapp(
    patient_name: str,
    phone_number: str,
    appointment_time: str,
    appointment_id: int
) -> dict:
    """
    Send appointment cancellation via WhatsApp.
    
    Args:
        patient_name: Patient's name
        phone_number: Patient's WhatsApp number
        appointment_time: Appointment date/time that was canceled
        appointment_id: Appointment ID
        
    Returns:
        Dictionary with status and details
    """
    message_body = f"""
🏥 *Smart Care Medical Center*

Dear *{patient_name}*,

Your appointment has been *CANCELED* ❌

📅 *Canceled:* {appointment_time}
🆔 *Booking ID:* #{appointment_id}

To reschedule, please call us at:
📞 +91-11-4567-8900

Thank you! 🙏
    """.strip()
    
    return send_whatsapp(phone_number, message_body)


# Backward compatibility aliases (so old code still works)
send_sms = send_whatsapp
send_appointment_confirmation = send_appointment_confirmation_whatsapp
send_appointment_cancellation = send_appointment_cancellation_whatsapp


# Test function
if __name__ == "__main__":
    print("🧪 Testing Twilio WhatsApp Service")
    print("-" * 50)
    
    # Test phone number cleaning
    test_numbers = [
        "3320825825",
        "+92 332 082 5825",
        "332-082-5825",
        "+923320825825"
    ]
    
    print("\n📱 Testing phone number cleaning:")
    for num in test_numbers:
        cleaned = clean_phone_number(num)
        print(f"   {num} -> {cleaned}")
    
    # Test WhatsApp sending (replace with your actual number)
    print("\n💬 Testing WhatsApp sending:")
    print("   (Replace test number in code to actually send)")
    
    # Uncomment and replace with your number to test:
    # Make sure you've joined the WhatsApp sandbox first!
    # result = send_whatsapp("+923320825825", "Test message from Smart Care!")
    # print(f"   Result: {result}")