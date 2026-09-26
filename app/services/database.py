import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

if not MYSQL_HOST:
    raise RuntimeError("MYSQL_HOST is missing from .env")

if not MYSQL_DATABASE:
    raise RuntimeError("MYSQL_DATABASE is missing from .env")

if not MYSQL_USER:
    raise RuntimeError("MYSQL_USER is missing from .env")

if not MYSQL_PASSWORD:
    raise RuntimeError("MYSQL_PASSWORD is missing from .env")


database_url = URL.create(
    "mysql+pymysql",
    username=MYSQL_USER,
    password=MYSQL_PASSWORD,
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    database=MYSQL_DATABASE,
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
)


def get_connection():
    return engine.connect()


def get_transaction():
    return engine.begin()


def get_available_appointment(slot_id):
    query = text("""
        SELECT
            ds.id,
            ds.doctor_id,
            d.name AS doctor_name,
            d.specialization,
            d.contact,
            ds.appointment_datetime,
            ds.is_available
        FROM doctor_slots ds
        JOIN doctors d
            ON d.id = ds.doctor_id
        WHERE ds.id = :slot_id
        LIMIT 1
    """)

    with engine.connect() as connection:
        result = connection.execute(
            query,
            {"slot_id": slot_id}
        ).mappings().first()

        if result is None:
            return None

        return dict(result)


def book_appointment(slot_id):
    """
    Atomically reserve an available appointment slot.
    """

    with engine.begin() as connection:

        check_query = text("""
            SELECT
                ds.id,
                ds.doctor_id,
                d.name AS doctor_name,
                d.specialization,
                d.contact,
                ds.appointment_datetime,
                ds.is_available
            FROM doctor_slots ds
            JOIN doctors d
                ON d.id = ds.doctor_id
            WHERE ds.id = :slot_id
            FOR UPDATE
        """)

        appointment = connection.execute(
            check_query,
            {"slot_id": slot_id}
        ).mappings().first()

        if appointment is None:
            return {
                "success": False,
                "message": "Appointment slot not found."
            }

        if int(appointment["is_available"]) != 1:
            return {
                "success": False,
                "message": "This appointment is no longer available."
            }

        # MySQL/RDS uses UTC, while appointment_datetime stores
        # clinic-local India time (IST, UTC+5:30).
        current_db_time = connection.execute(
            text("SELECT DATE_ADD(UTC_TIMESTAMP(), INTERVAL 330 MINUTE)")
        ).scalar()

        appointment_datetime = appointment["appointment_datetime"]

        if (
            appointment_datetime is not None
            and appointment_datetime <= current_db_time
        ):
            return {
                "success": False,
                "message": "This appointment slot has already passed. Please select a future appointment."
            }

        update_query = text("""
            UPDATE doctor_slots
            SET is_available = 0
            WHERE id = :slot_id
              AND is_available = 1
        """)

        result = connection.execute(
            update_query,
            {"slot_id": slot_id}
        )

        if result.rowcount != 1:
            return {
                "success": False,
                "message": "Unable to book this appointment. It may already be booked."
            }

        return {
            "success": True,
            "message": "Appointment booked successfully.",
            "appointment": {
                "slot_id": appointment["id"],
                "doctor_id": appointment["doctor_id"],
                "doctor_name": appointment["doctor_name"],
                "specialization": appointment["specialization"],
                "contact": appointment["contact"],
                "appointment_datetime": str(
                    appointment["appointment_datetime"]
                ),
                "available": False
            }
        }
