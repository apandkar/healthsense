from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

from app.healthsense_crew import run_healthsense
from app.services.database import (
    get_available_appointment,
    book_appointment,
)


app = FastAPI(
    title="IKHealthSense API",
    version="1.0.0",
    description="AI-powered healthcare navigation API"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SESSION MEMORY
# ============================================================

# Temporary application-level conversation memory.
# Each session stores the latest conversation exchanges.
SESSION_MEMORY = {}

MAX_HISTORY = 10


def get_session_history(session_id: str):
    return SESSION_MEMORY.setdefault(session_id, [])


def build_context(history):
    if not history:
        return ""

    context_lines = [
        "Previous conversation context:",
    ]

    for item in history:
        context_lines.append(
            f"User: {item['user']}"
        )
        context_lines.append(
            f"IKHealthSense: {item['assistant']}"
        )

    return "\n".join(context_lines)


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    symptoms: str
    location: str = ""
    session_id: Optional[str] = Field(
        default=None,
        description="Conversation session identifier"
    )


class BookAppointmentRequest(BaseModel):
    slot_id: int


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "application": "IKHealthSense",
        "status": "online",
        "version": "1.0.0",
        "message": "IKHealthSense API is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
def chat(request: ChatRequest):

    try:

        # Create a session when the frontend does not provide one.
        session_id = request.session_id or str(uuid4())

        history = get_session_history(session_id)

        user_query = request.symptoms

        if request.location:
            user_query += f" I am in {request.location}."

        # Add previous conversation context.
        previous_context = build_context(history)

        if previous_context:
            user_query = (
                f"{previous_context}\n\n"
                f"Current user request:\n{user_query}"
            )

        result = run_healthsense(user_query)

        # Store the current exchange.
        history.append({
            "user": request.symptoms,
            "assistant": str(result)
        })

        # Keep only the latest exchanges.
        if len(history) > MAX_HISTORY:
            del history[:-MAX_HISTORY]

        return {
            "success": True,
            "session_id": session_id,
            "symptoms": request.symptoms,
            "location": request.location,
            "response": result
        }

    except Exception as e:

        print(f"ERROR /chat: {e}")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# GET APPOINTMENT
# ============================================================

@app.get("/appointments/{slot_id}")
def get_appointment(slot_id: int):

    try:

        appointment = get_available_appointment(slot_id)

        if appointment is None:
            raise HTTPException(
                status_code=404,
                detail="Appointment slot not found."
            )

        appointment["appointment_datetime"] = str(
            appointment["appointment_datetime"]
        )

        appointment["is_available"] = bool(
            appointment["is_available"]
        )

        return {
            "success": True,
            "appointment": appointment
        }

    except HTTPException:
        raise

    except Exception as e:

        print(f"ERROR /appointments/{slot_id}: {e}")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# BOOK APPOINTMENT
# ============================================================

@app.post("/appointments/book")
def book(request: BookAppointmentRequest):

    try:

        if request.slot_id < 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid appointment slot ID."
            )

        result = book_appointment(request.slot_id)

        if not result["success"]:

            raise HTTPException(
                status_code=409,
                detail=result["message"]
            )

        return result

    except HTTPException:
        raise

    except Exception as e:

        print(f"ERROR /appointments/book: {e}")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

from fastapi.staticfiles import StaticFiles
app.mount('/', StaticFiles(directory='frontend', html=True), name='frontend')
