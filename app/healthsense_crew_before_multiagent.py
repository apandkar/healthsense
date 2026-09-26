import os
import json

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.llm import LLM
from sqlalchemy import text

from app.tools.sql_tool import HealthSenseSQLTool
from app.services.database import get_connection


# ============================================================
# IKHealthSense Crew
# ============================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from .env")


# ============================================================
# LLM
# ============================================================

llm = LLM(
    model=f"openai/{MODEL_NAME}",
    api_key=OPENAI_API_KEY,
    temperature=0,
)


# ============================================================
# SQL TOOL
# ============================================================

sql_tool = HealthSenseSQLTool()


# ============================================================
# AGENT
# ============================================================

health_agent = Agent(
    role="IKHealthSense Healthcare Coordinator",

    goal=(
        "Provide safe healthcare navigation using the "
        "IKHealthSense database. Determine urgency, identify "
        "appropriate specialization, and retrieve only real "
        "database records."
    ),

    backstory=(
        "You are a healthcare navigation coordinator. "
        "You do not diagnose patients. "
        "You provide information about healthcare facilities, "
        "doctors and appointment availability. "
        "Emergency symptoms must always receive an immediate "
        "emergency-care recommendation."
    ),

    tools=[sql_tool],

    llm=llm,

    verbose=True,

    allow_delegation=False,

    max_iter=5,
)


# ============================================================
# TASK
# ============================================================

health_task = Task(
    description="""

USER REQUEST:

{user_query}


============================================================
1. TRIAGE
============================================================

Determine urgency:

EMERGENCY
URGENT
ROUTINE
INFORMATIONAL

Do NOT diagnose.

If the user reports potentially life-threatening symptoms such as:
- chest pain
- severe shortness of breath
- severe difficulty breathing
- unconsciousness
- stroke-like symptoms
- severe bleeding

classify as EMERGENCY.

For EMERGENCY, clearly tell the user to seek immediate
emergency medical care.

Do NOT tell an emergency patient to wait for a routine appointment.

For emergency symptoms, appointments may be displayed only as
additional healthcare-navigation information.


============================================================
2. SPECIALIZATION
============================================================

Determine the most appropriate medical specialization.

Examples:
- Chest pain -> Cardiology
- Bone/joint -> Orthopedics
- Eye -> Ophthalmology
- Kidney -> Nephrology

Only select a specialization when reasonably supported.


============================================================
3. DATABASE STRUCTURE
============================================================

Available tables:
- hospitals
- hospital_emergency
- hospital_lab_tests
- doctors
- doctor_slots

DOCTORS:
- id
- name
- specialization
- contact

DOCTOR SLOTS:
- id
- doctor_id
- appointment_datetime
- is_available

Relationship:
doctors.id = doctor_slots.doctor_id

HOSPITALS:
- provider_id
- hospital_name
- address
- city
- state
- zip_code
- county_name
- phone_number
- hospital_type
- hospital_ownership
- emergency_services
- hospital_overall_rating
- location


============================================================
4. LOCATION
============================================================

If the user provides a location, use it when searching the hospitals table.

The doctors table does NOT contain location fields.

Therefore:
- Never query doctors.city.
- Never query doctors.state.
- Never invent a doctor location.
- Doctor lookup may be based on specialization and appointment availability.
- Hospital lookup may use the actual hospitals.city and hospitals.state fields.

If no matching hospitals exist for the requested location:
"hospitals": []

Do NOT invent hospitals.


============================================================
5. APPOINTMENTS
============================================================

Only return available FUTURE appointments.

Always use:
ds.is_available = 1

AND:
ds.appointment_datetime >= NOW()

Example:

SELECT
    ds.id AS slot_id,
    d.name AS doctor_name,
    d.specialization,
    d.contact,
    ds.appointment_datetime
FROM doctors d
JOIN doctor_slots ds
    ON d.id = ds.doctor_id
WHERE ds.is_available = 1
  AND ds.appointment_datetime >= NOW()
  AND LOWER(TRIM(d.specialization)) =
      LOWER(TRIM('Cardiology'))
ORDER BY ds.appointment_datetime
LIMIT 5;

Replace Cardiology with the required specialization.

NEVER return past appointments.
NEVER invent doctors.
NEVER invent appointment times.
NEVER invent contact numbers.


============================================================
6. DOCTOR DEDUPLICATION
============================================================

A doctor can have multiple appointment slots.

The "doctors" array must contain each doctor ONLY ONCE.

The "appointments" array should contain individual appointment slots.


============================================================
7. HOSPITALS
============================================================

If the user provides a location, search the hospitals table using
the actual city/state fields.

For emergency-capable hospitals use:
emergency_services = 1

Example:

SELECT
    provider_id,
    hospital_name,
    address,
    city,
    state,
    zip_code,
    phone_number,
    hospital_overall_rating
FROM hospitals
WHERE city = 'Chicago'
  AND emergency_services = 1
LIMIT 5;

Only use a location if it actually exists in the database.

If no matching hospitals exist:
"hospitals": []

Do NOT invent hospitals.


============================================================
8. RESULT LIMITS
============================================================

Maximum:
- 5 hospitals
- 5 unique doctors
- 5 appointments

NEVER retrieve the entire database.

Keep SQL responses small.


============================================================
9. OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Do NOT return Markdown.
Do NOT use ```json.
Do NOT provide text outside the JSON.

Use EXACTLY this structure:

{
    "triage": {
        "urgency": "EMERGENCY",
        "message": "..."
    },
    "specialization": "Cardiology",
    "location": "Chicago",
    "hospitals": [],
    "doctors": [],
    "appointments": [],
    "disclaimer": "IKHealthSense provides healthcare navigation information and does not provide a medical diagnosis."
}


============================================================
10. DOCTOR OUTPUT
============================================================

Each doctor must appear only once:

{
    "name": "...",
    "specialization": "...",
    "contact": "..."
}


============================================================
11. APPOINTMENT OUTPUT
============================================================

Each appointment:

{
    "slot_id": 123,
    "doctor_name": "...",
    "specialization": "...",
    "contact": "...",
    "appointment_datetime": "...",
    "available": true
}


============================================================
12. HOSPITAL OUTPUT
============================================================

Each hospital:

{
    "provider_id": "...",
    "hospital_name": "...",
    "address": "...",
    "city": "...",
    "state": "...",
    "zip_code": "...",
    "phone_number": "...",
    "rating": "..."
}


============================================================
13. DATA INTEGRITY
============================================================

Only return information retrieved from MySQL.

Never invent:
- doctors
- hospitals
- appointment times
- phone numbers
- locations
- ratings


============================================================
14. EMERGENCY SAFETY
============================================================

For chest pain + shortness of breath or other potentially
life-threatening symptoms:

urgency MUST be:
"EMERGENCY"

The triage message MUST recommend immediate emergency medical care.

Do not provide a diagnosis.
Do not say that an appointment is a substitute for emergency care.


============================================================
15. FINAL JSON CHECK
============================================================

Before returning the answer:
1. Make sure the output is valid JSON.
2. Make sure doctors are unique.
3. Make sure appointments are future appointments.
4. Make sure appointments have is_available = 1.
5. Make sure no hospital is invented.
6. Make sure no doctor location is invented.
7. Return no more than 5 hospitals.
8. Return no more than 5 unique doctors.
9. Return no more than 5 appointments.
""",

    expected_output=(
        "A valid JSON object containing triage, specialization, "
        "location, hospitals, unique doctors, appointments and disclaimer."
    ),

    agent=health_agent,
)


# ============================================================
# CREW
# ============================================================

healthsense_crew = Crew(
    agents=[health_agent],

    tasks=[health_task],

    process=Process.sequential,

    verbose=True,

    memory=False,
)


# ============================================================
# RESPONSE CLEANUP
# ============================================================

def clean_response(data):
    if not isinstance(data, dict):
        return data

    hospitals = data.get("hospitals", [])
    if not isinstance(hospitals, list):
        hospitals = []

    specialization = str(
        data.get("specialization") or ""
    ).strip()

    location = str(
        data.get("location") or ""
    ).strip()

    unique_doctors = []
    unique_appointments = []

    # Database is the source of truth.
    try:
        with get_connection() as conn:

            # ------------------------------------------------
            # Retrieve doctors.
            # The doctors table contains no location fields.
            # ------------------------------------------------
            if specialization:
                doctor_result = conn.execute(
                    text("""
                        SELECT DISTINCT
                            d.id,
                            d.name,
                            d.specialization,
                            d.contact
                        FROM doctors d
                        JOIN doctor_slots ds
                            ON d.id = ds.doctor_id
                        WHERE LOWER(TRIM(d.specialization)) =
                              LOWER(TRIM(:specialization))
                          AND ds.is_available = 1
                          AND ds.appointment_datetime >= NOW()
                        ORDER BY d.name ASC
                        LIMIT 5
                    """),
                    {
                        "specialization": specialization
                    }
                )
            else:
                doctor_result = conn.execute(
                    text("""
                        SELECT DISTINCT
                            d.id,
                            d.name,
                            d.specialization,
                            d.contact
                        FROM doctors d
                        JOIN doctor_slots ds
                            ON d.id = ds.doctor_id
                        WHERE ds.is_available = 1
                          AND ds.appointment_datetime >= NOW()
                        ORDER BY d.name ASC
                        LIMIT 5
                    """)
                )

            doctor_rows = doctor_result.mappings().all()

            for row in doctor_rows:
                unique_doctors.append({
                    "name": str(row["name"] or "").strip(),
                    "specialization": str(
                        row["specialization"] or ""
                    ).strip(),
                    "contact": str(row["contact"] or "").strip()
                })

            # ------------------------------------------------
            # Retrieve appointments.
            # Appointments are filtered only by specialization
            # because doctors have no location columns.
            # ------------------------------------------------
            if specialization:
                appointment_result = conn.execute(
                    text("""
                        SELECT
                            ds.id AS slot_id,
                            d.name AS doctor_name,
                            d.specialization AS specialization,
                            d.contact AS contact,
                            ds.appointment_datetime
                                AS appointment_datetime
                        FROM doctor_slots ds
                        JOIN doctors d
                            ON d.id = ds.doctor_id
                        WHERE LOWER(TRIM(d.specialization)) =
                              LOWER(TRIM(:specialization))
                          AND ds.is_available = 1
                          AND ds.appointment_datetime >= NOW()
                        ORDER BY ds.appointment_datetime ASC
                        LIMIT 5
                    """),
                    {
                        "specialization": specialization
                    }
                )
            else:
                appointment_result = conn.execute(
                    text("""
                        SELECT
                            ds.id AS slot_id,
                            d.name AS doctor_name,
                            d.specialization AS specialization,
                            d.contact AS contact,
                            ds.appointment_datetime
                                AS appointment_datetime
                        FROM doctor_slots ds
                        JOIN doctors d
                            ON d.id = ds.doctor_id
                        WHERE ds.is_available = 1
                          AND ds.appointment_datetime >= NOW()
                        ORDER BY ds.appointment_datetime ASC
                        LIMIT 5
                    """)
                )

            appointment_rows = (
                appointment_result.mappings().all()
            )

            for row in appointment_rows:
                unique_appointments.append({
                    "slot_id": int(row["slot_id"]),
                    "doctor_name": str(
                        row["doctor_name"] or ""
                    ).strip(),
                    "specialization": str(
                        row["specialization"] or ""
                    ).strip(),
                    "contact": str(
                        row["contact"] or ""
                    ).strip(),
                    "appointment_datetime": str(
                        row["appointment_datetime"]
                    ).strip(),
                    "available": True
                })

    except Exception as e:
        print(
            "Doctor/appointment retrieval error: "
            f"{type(e).__name__}: {e}"
        )
        unique_doctors = []
        unique_appointments = []

    hospitals = hospitals[:5]

    return {
        "triage": data.get(
            "triage",
            {
                "urgency": "INFORMATIONAL",
                "message": "No triage information available."
            }
        ),
        "specialization": specialization or data.get(
            "specialization"
        ),
        "location": location,
        "hospitals": hospitals,
        "doctors": unique_doctors,
        "appointments": unique_appointments,
        "disclaimer": (
            "IKHealthSense provides healthcare navigation "
            "information and does not provide a medical diagnosis."
        )
    }


# ============================================================
# RUN
# ============================================================

def run_healthsense(user_query: str):

    if not user_query or not user_query.strip():
        raise ValueError("User query cannot be empty.")

    result = healthsense_crew.kickoff(
        inputs={
            "user_query": user_query.strip()
        }
    )

    raw = getattr(result, "raw", result)

    if raw is None:
        return {
            "triage": {
                "urgency": "INFORMATIONAL",
                "message": "No response generated."
            },
            "specialization": None,
            "location": None,
            "hospitals": [],
            "doctors": [],
            "appointments": [],
            "disclaimer": (
                "IKHealthSense provides healthcare navigation "
                "information and does not provide a medical diagnosis."
            )
        }

    if isinstance(raw, dict):
        return clean_response(raw)

    raw = str(raw).strip()

    # --------------------------------------------------------
    # Remove Markdown fences
    # --------------------------------------------------------

    if raw.startswith("```json"):
        raw = raw[7:]

    elif raw.startswith("```"):
        raw = raw[3:]

    if raw.endswith("```"):
        raw = raw[:-3]

    raw = raw.strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        data = json.loads(raw)

        return clean_response(data)

    except json.JSONDecodeError:

        return {
            "triage": {
                "urgency": "INFORMATIONAL",
                "message": raw
            },
            "specialization": None,
            "location": None,
            "hospitals": [],
            "doctors": [],
            "appointments": [],
            "disclaimer": (
                "IKHealthSense provides healthcare navigation "
                "information and does not provide a medical diagnosis."
            )
        }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print(" IKHealthSense - CrewAI Test")
    print("=" * 70)

    question = (
        "I have chest pain and shortness of breath. "
        "I am currently in Chicago. "
        "Please find available cardiology appointments."
    )

    print()
    print("USER:")
    print(question)

    print()
    print("-" * 70)
    print("Running CrewAI...")
    print("-" * 70)

    try:

        response = run_healthsense(question)

        print()
        print("=" * 70)
        print("FINAL RESULT")
        print("=" * 70)

        print(
            json.dumps(
                response,
                indent=2,
                ensure_ascii=False
            )
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)

        print(type(e).__name__)
        print(str(e))

    print()
    print("=" * 70)
    print("CREWAI TEST COMPLETED")
    print("=" * 70)
