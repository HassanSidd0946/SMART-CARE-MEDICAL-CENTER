import streamlit as st
import requests
import datetime as dt
from typing import Optional

# Backend URL
BACKEND_URL = "http://127.0.0.1:4444"

st.set_page_config(
    page_title="Smart Care Medical Center",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Smart Care Medical Center")
st.subheader("Appointment Management System")

# ==================== HELPER FUNCTIONS ====================

def test_connection() -> dict:
    """Test connection to backend API."""
    try:
        # Increase timeout to 15 seconds
        response = requests.get(
            f"{BACKEND_URL}/", 
            timeout=15  # ← INCREASED FROM 5 to 15
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "message": "✅ Connected to backend successfully!",
                "status_code": response.status_code
            }
        else:
            return {
                "success": False,
                "message": f"⚠️ Backend returned status {response.status_code}",
                "status_code": response.status_code
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "❌ Connection timeout. Is the backend running?",
            "error": "TIMEOUT"
        }
    
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "message": "❌ Cannot connect to backend. Make sure backend.py is running on port 4444.",
            "error": "CONNECTION_ERROR"
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}",
            "error": str(e)
        }


def schedule_appointment(
    patient_name: str,
    reason: str,
    start_time: dt.datetime,
    phone_number: Optional[str] = None
) -> dict:
    """Schedule a new appointment."""
    try:
        payload = {
            "patient_name": patient_name,
            "reason": reason,
            "start_time": start_time.isoformat(),
            "phone_number": phone_number
        }
        
        response = requests.post(
            f"{BACKEND_URL}/schedule_appointments/",
            json=payload,
            timeout=15  # ← INCREASED TIMEOUT
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "message": f"Error {response.status_code}: {response.text}"
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "Request timeout. Please try again."
        }
    
    except Exception as e:
        return {"success": False, "message": str(e)}


def list_appointments(date: dt.date) -> dict:
    """List appointments for a specific date."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/list_appointments/",
            params={"date": date.isoformat()},
            timeout=15  # ← INCREASED TIMEOUT
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "message": f"Error {response.status_code}: {response.text}"
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "Request timeout. Please try again."
        }
    
    except Exception as e:
        return {"success": False, "message": str(e)}


def cancel_appointment(patient_name: str, date: dt.date, phone_number: Optional[str] = None) -> dict:
    """Cancel appointment."""
    try:
        payload = {
            "patient_name": patient_name,
            "date": date.isoformat(),
            "phone_number": phone_number
        }
        
        response = requests.post(
            f"{BACKEND_URL}/cancel_appointments/",
            json=payload,
            timeout=15  # ← INCREASED TIMEOUT
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "message": f"Error {response.status_code}: {response.text}"
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "Request timeout. Please try again."
        }
    
    except Exception as e:
        return {"success": False, "message": str(e)}


# ==================== SIDEBAR ====================

with st.sidebar:
    st.header("🔧 System Status")
    
    if st.button("🔌 Test Connection", use_container_width=True):
        with st.spinner("Testing connection..."):
            result = test_connection()
            
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])
                
                # Show helpful hints
                if result.get("error") == "CONNECTION_ERROR":
                    st.info("💡 **How to fix:**\n1. Open Terminal\n2. Run: `python backend.py`\n3. Wait for 'Uvicorn running' message\n4. Try connecting again")
                elif result.get("error") == "TIMEOUT":
                    st.info("💡 **How to fix:**\n1. Check if backend is running\n2. Check if port 4444 is available\n3. Restart backend if needed")
    
    st.divider()
    
    st.markdown("""
    ### 📖 Quick Links
    - [API Docs](http://127.0.0.1:4444/docs)
    - [Real-Time Dashboard](http://127.0.0.1:4444/dashboard)
    - [Health Check](http://127.0.0.1:4444/)
    """)
    
    st.divider()
    
    st.caption("Smart Care Medical Center v3.0")


# ==================== MAIN TABS ====================

tab1, tab2, tab3 = st.tabs(["📅 Schedule", "📋 View Appointments", "❌ Cancel"])

# ==================== TAB 1: SCHEDULE ====================

with tab1:
    st.header("📅 Schedule New Appointment")
    
    with st.form("schedule_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            patient_name = st.text_input("Patient Name *", placeholder="John Doe")
            reason = st.text_input("Reason for Visit *", placeholder="General Checkup")
        
        with col2:
            appointment_date = st.date_input(
                "Appointment Date *",
                min_value=dt.date.today()
            )
            appointment_time = st.time_input("Appointment Time *", value=dt.time(10, 0))
        
        phone_number = st.text_input(
            "WhatsApp Phone Number (Optional)",
            placeholder="+923320825825",
            help="Include country code for WhatsApp notifications"
        )
        
        submitted = st.form_submit_button("📅 Schedule Appointment", use_container_width=True)
        
        if submitted:
            if not patient_name or not reason:
                st.error("❌ Please fill in all required fields")
            else:
                # Combine date and time
                start_time = dt.datetime.combine(appointment_date, appointment_time)
                
                with st.spinner("Scheduling appointment..."):
                    result = schedule_appointment(
                        patient_name=patient_name,
                        reason=reason,
                        start_time=start_time,
                        phone_number=phone_number if phone_number else None
                    )
                    
                    if result["success"]:
                        data = result["data"]
                        st.success(f"✅ Appointment scheduled successfully!")
                        st.info(f"""
                        **Appointment Details:**
                        - **ID:** #{data['id']}
                        - **Patient:** {data['patient_name']}
                        - **Date/Time:** {data['start_time']}
                        - **Reason:** {data['reason']}
                        - **WhatsApp:** {"✅ Sent" if data.get('whatsapp_sent') else "❌ Not sent"}
                        """)
                    else:
                        st.error(f"❌ {result.get('message', 'Failed to schedule appointment')}")


# ==================== TAB 2: VIEW ====================

with tab2:
    st.header("📋 View Appointments")
    
    view_date = st.date_input(
        "Select Date",
        value=dt.date.today(),
        key="view_date"
    )
    
    if st.button("🔍 Load Appointments", use_container_width=True):
        with st.spinner("Loading appointments..."):
            result = list_appointments(view_date)
            
            if result["success"]:
                appointments = result["data"]
                
                if not appointments:
                    st.info("📭 No appointments found for this date")
                else:
                    st.success(f"✅ Found {len(appointments)} appointment(s)")
                    
                    for apt in appointments:
                        status = "❌ CANCELED" if apt["canceled"] else "✅ ACTIVE"
                        
                        with st.expander(f"#{apt['id']} - {apt['patient_name']} ({status})"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Patient:** {apt['patient_name']}")
                                st.write(f"**Reason:** {apt['reason']}")
                            
                            with col2:
                                st.write(f"**Time:** {apt['start_time']}")
                                st.write(f"**Status:** {status}")
            else:
                st.error(f"❌ {result.get('message', 'Failed to load appointments')}")


# ==================== TAB 3: CANCEL ====================

with tab3:
    st.header("❌ Cancel Appointment")
    
    with st.form("cancel_form"):
        cancel_name = st.text_input("Patient Name *", placeholder="John Doe")
        cancel_date = st.date_input("Appointment Date *")
        cancel_phone = st.text_input(
            "WhatsApp Phone Number (Optional)",
            placeholder="+923320825825"
        )
        
        cancel_submitted = st.form_submit_button("❌ Cancel Appointment", use_container_width=True)
        
        if cancel_submitted:
            if not cancel_name:
                st.error("❌ Please enter patient name")
            else:
                with st.spinner("Canceling appointment..."):
                    result = cancel_appointment(
                        patient_name=cancel_name,
                        date=cancel_date,
                        phone_number=cancel_phone if cancel_phone else None
                    )
                    
                    if result["success"]:
                        data = result["data"]
                        st.success(f"✅ Canceled {data['canceled_count']} appointment(s)")
                        if data.get('whatsapp_sent'):
                            st.info("📱 Cancellation notification sent via WhatsApp")
                    else:
                        st.error(f"❌ {result.get('message', 'Failed to cancel appointment')}")