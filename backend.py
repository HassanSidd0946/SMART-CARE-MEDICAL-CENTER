from database import init_db, Appointment, get_db
init_db()

from rag_service import get_rag_service
from whatsapp_service import send_appointment_confirmation, send_appointment_cancellation

# NEW: Import WebSocket manager
from websocket_manager import manager as ws_manager

import datetime as dt
from pydantic import BaseModel, field_validator
from typing import Optional
import os

class AppointmentRequest(BaseModel):
    patient_name: str
    reason: str
    start_time: dt.datetime
    phone_number: Optional[str] = None
    
    @field_validator('start_time', mode='before')
    @classmethod
    def parse_datetime(cls, value):
        if isinstance(value, dt.datetime):
            return value
        
        if isinstance(value, str):
            try:
                value = value.replace('Z', '')
                
                if 'T' in value:
                    date_part, time_part = value.split('T', 1)
                    date_parts = date_part.split('-')
                    if len(date_parts) == 3:
                        year = int(date_parts[0])
                        month = int(date_parts[1])
                        day = int(date_parts[2])
                        
                        if '.' in time_part:
                            time_part = time_part.split('.')[0]
                        
                        time_parts = time_part.split(':')
                        if len(time_parts) >= 3:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            second = int(float(time_parts[2]))
                            
                            return dt.datetime(year, month, day, hour, minute, second)
                
                parsed = dt.datetime.fromisoformat(value.replace('+00:00', ''))
                if parsed.tzinfo:
                    parsed = parsed.replace(tzinfo=None)
                return parsed
            
            except Exception:
                raise ValueError(f"Invalid datetime: '{value}'")
        
        return value

class AppointmentResponse(BaseModel):
    id: int
    patient_name: str
    phone_number: str | None = None  # Added phone number field
    reason: str | None
    start_time: dt.datetime
    canceled: bool
    created_at: dt.datetime
    whatsapp_sent: Optional[bool] = None

class CancelAppointmentRequest(BaseModel):
    patient_name: str
    date: dt.date
    phone_number: Optional[str] = None

class CancelAppointmentResponse(BaseModel):
    canceled_count: int
    whatsapp_sent: Optional[bool] = None

class ClinicInfoRequest(BaseModel):
    query: str

class ClinicInfoResponse(BaseModel):
    query: str
    answer: str
    source: str = "Smart Care Medical Center Knowledge Base"

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
import asyncio
import json
from datetime import datetime
import json
from datetime import datetime

app = FastAPI(
    title="Smart Care Medical Center API",
    description="Hospital Appointment Booking with Real-Time Dashboard",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    print(f"❌ Validation Error from {request.client.host if request.client else 'unknown'}:")
    print(f"   URL: {request.url}")
    print(f"   Body: {body.decode() if body else 'empty'}")
    
    errors = []
    for error in exc.errors():
        err = {
            "type": error.get("type"),
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg"),
            "input": str(error.get("input", ""))
        }
        errors.append(err)
    
    print(f"   Errors: {errors}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
            "message": "Invalid request format"
        }
    )

# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    
    Clients connect to this endpoint to receive live updates about:
    - New appointments
    - Cancellations
    - System messages
    """
    await ws_manager.connect(websocket)
    
    try:
        # Keep connection alive and listen for client messages
        while True:
            # Receive messages from client (optional - for heartbeat/ping)
            data = await websocket.receive_text()
            
            # Handle client messages if needed
            if data == "ping":
                await ws_manager.send_personal_message(
                    {"event": "pong", "timestamp": dt.datetime.now().isoformat()},
                    websocket
                )
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        print("🔌 Client disconnected normally")
    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        ws_manager.disconnect(websocket)

# ==================== BACKGROUND TASKS ====================

def send_confirmation_whatsapp_background(
    patient_name: str,
    phone_number: str,
    appointment_time: str,
    reason: str,
    appointment_id: int
):
    """Background task to send WhatsApp confirmation."""
    try:
        print(f"💬 [Background] Sending WhatsApp to {patient_name}...")
        result = send_appointment_confirmation(
            patient_name=patient_name,
            phone_number=phone_number,
            appointment_time=appointment_time,
            reason=reason,
            appointment_id=appointment_id
        )
        
        if result["success"]:
            print(f"✅ [Background] WhatsApp sent! SID: {result.get('sid')}")
        else:
            print(f"⚠️ [Background] WhatsApp failed: {result.get('message')}")
    
    except Exception as e:
        print(f"❌ [Background] Error: {e}")

def send_cancellation_whatsapp_background(
    patient_name: str,
    phone_number: str,
    appointment_time: str,
    appointment_id: int
):
    """Background task to send cancellation WhatsApp."""
    try:
        print(f"💬 [Background] Sending cancellation WhatsApp...")
        result = send_appointment_cancellation(
            patient_name=patient_name,
            phone_number=phone_number,
            appointment_time=appointment_time,
            appointment_id=appointment_id
        )
        
        if result["success"]:
            print(f"✅ [Background] Cancellation sent!")
        else:
            print(f"⚠️ [Background] Failed: {result.get('message')}")
    
    except Exception as e:
        print(f"❌ [Background] Error: {e}")

# ==================== APPOINTMENT ENDPOINTS ====================

# Find this section and update:

@app.post("/schedule_appointments/", response_model=AppointmentResponse)
async def schedule_appointment(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Schedule appointment with real-time dashboard broadcast.
    Accepts both Pydantic model and raw JSON from Vapi.ai
    """
    try:
        # Get raw body to handle Vapi.ai format
        body = await request.json()
        
        print(f"📥 Received request body: {json.dumps(body, indent=2)}")
        
        # Extract data - handle both our format and Vapi format
        patient_name = (
            body.get("patient_name") or 
            body.get("patientName") or 
            body.get("name") or 
            ""
        )
        
        phone_number = (
            body.get("phone_number") or 
            body.get("phoneNumber") or 
            body.get("phone") or 
            None
        )
        
        reason = (
            body.get("reason") or 
            body.get("visitReason") or 
            "General Consultation"
        )
        
        start_time_str = (
            body.get("start_time") or 
            body.get("startTime") or 
            body.get("dateTime") or 
            body.get("appointment_time") or
            ""
        )
        
        print(f"📋 Parsed data:")
        print(f"   Patient: {patient_name}")
        print(f"   Phone: {phone_number}")
        print(f"   Reason: {reason}")
        print(f"   Time (raw): {start_time_str}")
        
        # Validate required fields
        if not patient_name:
            raise HTTPException(status_code=400, detail="patient_name is required")
        
        if not start_time_str:
            raise HTTPException(status_code=400, detail="start_time is required")
        
        # Parse datetime - handle multiple formats
        start_time = None
        datetime_formats = [
            "%Y-%m-%dT%H:%M:%S",           # 2026-03-20T14:30:00
            "%Y-%m-%d %H:%M:%S",           # 2026-03-20 14:30:00
            "%Y-%m-%dT%H:%M",              # 2026-03-20T14:30
            "%Y-%m-%d %H:%M",              # 2026-03-20 14:30
            "%d/%m/%Y %H:%M",              # 20/03/2026 14:30
            "%m/%d/%Y %H:%M",              # 03/20/2026 14:30
            "%d-%m-%Y %H:%M",              # 20-03-2026 14:30
            "%Y-%m-%dT%H:%M:%S.%f",        # 2026-03-20T14:30:00.000
            "%Y-%m-%dT%H:%M:%S%z",         # 2026-03-20T14:30:00+00:00
        ]
        
        for fmt in datetime_formats:
            try:
                start_time = datetime.strptime(start_time_str, fmt)
                print(f"✅ Parsed datetime using format: {fmt}")
                break
            except ValueError:
                continue
        
        # If still not parsed, try dateutil parser
        if not start_time:
            try:
                from dateutil import parser as date_parser
                start_time = date_parser.parse(start_time_str)
                print(f"✅ Parsed datetime using dateutil parser")
            except Exception as e:
                print(f"❌ Failed to parse datetime: {e}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid datetime format: {start_time_str}. Expected ISO format like '2026-03-20T14:30:00'"
                )
        
        print(f"📅 Final datetime: {start_time}")
        print(f"📅 Scheduling appointment for {patient_name}")
        
        # Create appointment
        new_appointment = Appointment(
            patient_name=patient_name,
            phone_number=phone_number,  # Save phone number to database
            reason=reason,
            start_time=start_time
        )
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)
        
        print(f"✅ Appointment scheduled: ID {new_appointment.id}")
        
        # Format time for display
        formatted_time = new_appointment.start_time.strftime("%B %d, %Y at %I:%M %p")
        
        # Broadcast to dashboard
        await ws_manager.broadcast_new_booking(
            patient_name=new_appointment.patient_name,
            appointment_time=formatted_time,
            reason=new_appointment.reason,
            appointment_id=new_appointment.id,
            phone_number=phone_number
        )
        
        # Schedule WhatsApp in background - WITH BETTER LOGGING
        whatsapp_scheduled = False
        
        if phone_number and phone_number.strip():
            phone_clean = phone_number.strip()
            
            # Ensure phone has country code
            if not phone_clean.startswith('+'):
                print(f"⚠️ Phone number missing '+', adding it: {phone_clean}")
                phone_clean = '+' + phone_clean
            
            print(f"💬 Scheduling WhatsApp to: {phone_clean}")
            
            try:
                background_tasks.add_task(
                    send_confirmation_whatsapp_background,
                    patient_name=new_appointment.patient_name,
                    phone_number=phone_clean,
                    appointment_time=formatted_time,
                    reason=new_appointment.reason,
                    appointment_id=new_appointment.id
                )
                whatsapp_scheduled = True
                print(f"✅ WhatsApp background task queued for {phone_clean}")
            except Exception as wa_error:
                print(f"❌ Failed to queue WhatsApp task: {wa_error}")
        else:
            print(f"⚠️ No valid phone number provided. Received: '{phone_number}'")
        
        # Return response
        response_data = {
            "id": new_appointment.id,
            "patient_name": new_appointment.patient_name,
            "phone_number": new_appointment.phone_number,  # Include phone number
            "reason": new_appointment.reason,
            "start_time": new_appointment.start_time.isoformat(),
            "canceled": new_appointment.canceled,
            "created_at": new_appointment.created_at.isoformat(),
            "whatsapp_sent": whatsapp_scheduled,
            "formatted_time": formatted_time
        }
        
        print(f"📤 Sending response: {json.dumps(response_data, indent=2)}")
        
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error scheduling appointment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cancel_appointments/", response_model=CancelAppointmentResponse)
async def cancel_appointment(
    request: CancelAppointmentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Cancel appointment with real-time dashboard broadcast."""
    try:
        print(f"🚫 Canceling appointments for {request.patient_name}")
        start_dt = dt.datetime.combine(request.date, dt.time.min)
        end_dt = start_dt + dt.timedelta(days=1)
        
        result = db.execute(
            select(Appointment)
            .where(Appointment.patient_name == request.patient_name)
            .where(Appointment.start_time >= start_dt)
            .where(Appointment.start_time < end_dt)
            .where(Appointment.canceled == False)
        )

        appointments = result.scalars().all()
        if not appointments:
            raise HTTPException(status_code=404, detail="No appointment found")
        
        whatsapp_scheduled = False
        for appointment in appointments:
            appointment.canceled = True
            
            # 🔴 BROADCAST CANCELLATION
            formatted_time = appointment.start_time.strftime("%B %d, %Y at %I:%M %p")
            await ws_manager.broadcast_cancellation(
                patient_name=appointment.patient_name,
                appointment_time=formatted_time,
                appointment_id=appointment.id,
                canceled_count=len(appointments)
            )
            
            if request.phone_number and not whatsapp_scheduled:
                try:
                    background_tasks.add_task(
                        send_cancellation_whatsapp_background,
                        patient_name=appointment.patient_name,
                        phone_number=request.phone_number,
                        appointment_time=formatted_time,
                        appointment_id=appointment.id
                    )
                    whatsapp_scheduled = True
                except Exception as wa_error:
                    print(f"⚠️ WhatsApp scheduling failed: {wa_error}")

        db.commit()
        print(f"✅ Canceled {len(appointments)} appointment(s)")
        
        return CancelAppointmentResponse(
            canceled_count=len(appointments),
            whatsapp_sent=whatsapp_scheduled
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LIST APPOINTMENTS (MISSING IN YOUR FILE) ====================

@app.get("/list_appointments/", response_model=list[AppointmentResponse])
def list_appointments(date: str = Query(...), db: Session = Depends(get_db)):
    """
    List all appointments for a specific date.
    """
    try:
        print(f"📋 Listing appointments for {date}")
        date_obj = dt.datetime.fromisoformat(date).date()
        
        start_dt = dt.datetime.combine(date_obj, dt.time.min)
        end_dt = start_dt + dt.timedelta(days=1)

        result = db.execute(
            select(Appointment)
            .where(Appointment.canceled == False)
            .where(Appointment.start_time >= start_dt)
            .where(Appointment.start_time < end_dt)
            .order_by(Appointment.start_time.asc())
        )

        booked_appointments = [
            AppointmentResponse(
                id=apt.id,
                patient_name=apt.patient_name,
                phone_number=apt.phone_number,  # Include phone number
                reason=apt.reason,
                start_time=apt.start_time,
                canceled=apt.canceled,
                created_at=apt.created_at
            )
            for apt in result.scalars().all()
        ]

        print(f"✅ Found {len(booked_appointments)} appointment(s)")
        return booked_appointments
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== RAG ENDPOINTS (MISSING IN YOUR FILE) ====================

@app.post("/ask-clinic-info", response_model=ClinicInfoResponse)
async def ask_clinic_info(request: ClinicInfoRequest):
    """
    Ask questions about clinic information using RAG.
    """
    try:
        print(f"🔍 Query: {request.query}")
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Empty query")
        
        rag_service = get_rag_service()
        answer = rag_service.query_knowledge_base(request.query)
        
        if not answer.strip():
            answer = "Contact reception: +91-11-4567-8900"
        
        return ClinicInfoResponse(query=request.query, answer=answer)
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vapi/ask-clinic-info")
async def vapi_ask_clinic_info(request: Request):
    """
    VAPI-compatible endpoint for clinic information.
    """
    try:
        body = await request.json()
        query = body.get("query") or body.get("message") or body.get("text") or ""
        
        if not query.strip():
            return {"success": False, "answer": "Please ask a question"}
        
        rag_service = get_rag_service()
        answer = rag_service.query_knowledge_base(query)
        
        return {"success": True, "query": query, "answer": answer, "result": answer}
    except Exception as e:
        return {"success": False, "error": str(e), "answer": "Error"}


# ==================== DASHBOARD ENDPOINT (MISSING IN YOUR FILE) ====================

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """
    Serve the real-time dashboard HTML.
    """
    dashboard_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    
    if os.path.exists(dashboard_path):
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
            <html>
                <head><title>Dashboard Not Found</title></head>
                <body>
                    <h1>❌ Dashboard Not Found</h1>
                    <p>The dashboard file is missing. Please create <code>templates/dashboard.html</code></p>
                    <p><a href="/">Go to Home</a></p>
                </body>
            </html>
        """, status_code=404)


# ==================== HEALTH CHECK / HOME ====================

@app.get("/", response_class=HTMLResponse)
def health_check():
    """
    Health check with WebSocket info and navigation.
    """
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Smart Care API</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 30px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .container {{
                    background: white;
                    color: #333;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }}
                h1 {{ color: #667eea; margin-top: 0; }}
                .status {{ 
                    background: #10b981; 
                    color: white; 
                    padding: 8px 16px; 
                    border-radius: 20px;
                    display: inline-block;
                    font-weight: bold;
                }}
                ul {{ list-style: none; padding: 0; }}
                li {{ 
                    background: #f8fafc; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                }}
                a {{ 
                    color: #667eea; 
                    text-decoration: none; 
                    font-weight: bold;
                }}
                a:hover {{ text-decoration: underline; }}
                .stat {{
                    display: inline-block;
                    margin: 10px 20px 10px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏥 Smart Care Medical Center API</h1>
                <p class="status">✅ Healthy</p>
                
                <div style="margin: 30px 0;">
                    <div class="stat"><strong>Version:</strong> 3.0.0</div>
                    <div class="stat"><strong>WebSocket Connections:</strong> {ws_manager.get_connection_count()}</div>
                </div>
                
                <h2>📚 Available Endpoints</h2>
                <ul>
                    <li>📖 <a href="/docs">Interactive API Documentation (Swagger)</a></li>
                    <li>🎛️ <a href="/dashboard">Real-Time Doctor Dashboard</a></li>
                    <li>🧪 <a href="/test-whatsapp?phone=+923320825825">Test WhatsApp (Direct)</a></li>
                    <li>📡 WebSocket: <code>ws://127.0.0.1:4444/ws</code></li>
                </ul>
                
                <h2>🚀 Features</h2>
                <ul>
                    <li>✅ Appointment Scheduling</li>
                    <li>✅ WhatsApp Notifications</li>
                    <li>✅ Real-Time Dashboard Updates</li>
                    <li>✅ RAG-Powered Clinic Information</li>
                    <li>✅ VAPI Integration</li>
                </ul>
            </div>
        </body>
    </html>
    """


# ==================== TEST ENDPOINTS ====================

@app.get("/test-whatsapp")
async def test_whatsapp_endpoint(phone: str = "+923320825825"):
    """
    Direct WhatsApp test endpoint.
    Usage: GET /test-whatsapp?phone=+923320825825
    """
    try:
        print(f"🧪 Testing WhatsApp to: {phone}")
        
        result = send_appointment_confirmation(
            patient_name="Test Patient",
            phone_number=phone,
            appointment_time="March 20, 2026 at 2:30 PM",
            reason="WhatsApp Test",
            appointment_id=9999
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "✅ WhatsApp sent successfully! Check your phone.",
                "phone": phone,
                "sid": result.get("sid"),
                "status": result.get("status")
            }
        else:
            return {
                "success": False,
                "message": "❌ WhatsApp failed",
                "phone": phone,
                "error": result.get("error"),
                "error_code": result.get("error_code"),
                "details": result.get("message")
            }
    
    except Exception as e:
        print(f"❌ WhatsApp test failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/test-websocket-broadcast")
async def test_websocket_broadcast():
    """
    Test WebSocket broadcasting.
    Usage: GET /test-websocket-broadcast
    """
    try:
        print(f"🧪 Testing WebSocket broadcast...")
        
        from datetime import datetime
        test_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        
        await ws_manager.broadcast_new_booking(
            patient_name="Test WebSocket Patient",
            appointment_time=test_time,
            reason="WebSocket Broadcast Test",
            appointment_id=9998,
            phone_number="+923320825825"
        )
        
        return {
            "success": True,
            "message": "✅ WebSocket broadcast sent!",
            "connections": ws_manager.get_connection_count(),
            "note": "Check your dashboard at /dashboard to see the update"
        }
    
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


# ==================== RUN SERVER ====================

import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Smart Care API with Real-Time Dashboard...")
    print("📡 WebSocket endpoint: ws://127.0.0.1:4444/ws")
    print("🎛️ Dashboard: http://127.0.0.1:4444/dashboard")
    print("📖 API Docs: http://127.0.0.1:4444/docs")
    uvicorn.run("backend:app", host="127.0.0.1", port=4444, reload=True)