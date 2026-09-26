import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from crewai.tools import BaseTool


# ============================================================
# IKHealthSense SQL TOOL
# ============================================================
#
# Purpose:
# Provide CrewAI with a controlled SQL interface to AWS RDS.
#
# Important:
# - SELECT queries only
# - Maximum 20 returned rows
# - Only HealthSense tables
# - Prevent huge SQL responses
# - Future appointment protection
# ============================================================


load_dotenv()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

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


# ============================================================
# ALLOWED TABLES
# ============================================================

ALLOWED_TABLES = {
    "hospitals",
    "hospital_emergency",
    "hospital_lab_tests",
    "doctors",
    "doctor_slots",
}


# ============================================================
# SQL ENGINE
# ============================================================

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


# ============================================================
# TABLE SCHEMAS
# ============================================================
#
# Providing a compact schema ourselves prevents the agent
# from repeatedly loading large database metadata.
# ============================================================

TABLE_SCHEMAS = {

    "hospitals": """
hospitals(
    provider_id,
    hospital_name,
    address,
    city,
    state,
    zip_code,
    county_name,
    phone_number,
    hospital_type,
    hospital_ownership,
    emergency_services,
    hospital_overall_rating,
    location
)
""",

    "hospital_emergency": """
hospital_emergency(
    provider_id,
    hospital_name,
    emergency_services
)
""",

    "hospital_lab_tests": """
hospital_lab_tests(
    provider_id,
    test_name
)
""",

    "doctors": """
doctors(
    id,
    name,
    specialization,
    contact
)
""",

    "doctor_slots": """
doctor_slots(
    id,
    doctor_id,
    appointment_datetime,
    is_available
)
""",
}


# ============================================================
# HELPER: CHECK TABLE
# ============================================================

def _extract_tables(sql: str):

    sql_lower = sql.lower()

    found = set()

    for table in ALLOWED_TABLES:

        pattern = rf"\b{re.escape(table)}\b"

        if re.search(pattern, sql_lower):

            found.add(table)

    return found


# ============================================================
# HELPER: VALIDATE SQL
# ============================================================

def _validate_sql(sql: str):

    sql = sql.strip()

    if not sql:
        raise ValueError("SQL query cannot be empty.")

    # Only SELECT queries are allowed.
    if not re.match(r"^select\b", sql, re.IGNORECASE):

        raise ValueError(
            "Only SELECT queries are allowed."
        )

    # Block dangerous statements.
    forbidden = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "truncate ",
        "create ",
        "replace ",
        "grant ",
        "revoke ",
    ]

    sql_lower = sql.lower()

    for keyword in forbidden:

        if keyword in sql_lower:

            raise ValueError(
                f"SQL operation '{keyword.strip()}' is not allowed."
            )

    # Check tables.
    tables = _extract_tables(sql)

    if not tables:

        raise ValueError(
            "Query must reference a HealthSense table."
        )

    # Block system tables.
    blocked_patterns = [
        "information_schema",
        "mysql.",
        "performance_schema",
        "sys.",
    ]

    for pattern in blocked_patterns:

        if pattern in sql_lower:

            raise ValueError(
                "System database access is not allowed."
            )

    return sql


# ============================================================
# HELPER: LIMIT RESULTS
# ============================================================

def _add_limit(sql: str):

    # If query already contains LIMIT, keep it but cap it.
    match = re.search(
        r"\blimit\s+(\d+)",
        sql,
        re.IGNORECASE,
    )

    if match:

        requested_limit = int(match.group(1))

        if requested_limit > 20:

            sql = re.sub(
                r"\blimit\s+\d+",
                "LIMIT 20",
                sql,
                flags=re.IGNORECASE,
            )

        return sql

    # Remove trailing semicolon.
    sql = sql.rstrip(";").strip()

    return sql + " LIMIT 20"


# ============================================================
# SQL EXECUTION
# ============================================================

def execute_healthsense_sql(sql: str) -> str:

    sql = _validate_sql(sql)

    sql = _add_limit(sql)

    print()
    print("[HealthSense SQL]")
    print(sql)

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text(sql)
            )

            rows = result.fetchall()

            columns = list(result.keys())

        if not rows:

            return "No matching records found."

        # ====================================================
        # FORMAT COMPACTLY
        # ====================================================

        output_lines = []

        output_lines.append(
            "Columns: " + ", ".join(columns)
        )

        for row in rows:

            values = []

            for value in row:

                if value is None:

                    values.append("NULL")

                else:

                    value_text = str(value)

                    # Prevent a single large TEXT field from
                    # consuming the entire context.
                    if len(value_text) > 500:

                        value_text = (
                            value_text[:500]
                            + "...[truncated]"
                        )

                    values.append(value_text)

            output_lines.append(
                " | ".join(values)
            )

        output_lines.append(
            f"Returned {len(rows)} row(s)."
        )

        return "\n".join(output_lines)

    except Exception as e:

        return (
            "SQL execution failed: "
            + type(e).__name__
            + ": "
            + str(e)
        )


# ============================================================
# CREWAI TOOL
# ============================================================

class HealthSenseSQLTool(BaseTool):

    name: str = "HealthSense SQL Database"

    description: str = """
Execute a READ-ONLY SQL SELECT query against the
IKHealthSense AWS MySQL database.

AVAILABLE TABLES:

1. hospitals
   - provider_id
   - hospital_name
   - address
   - city
   - state
   - zip_code
   - hospital_type
   - hospital_ownership
   - emergency_services
   - hospital_overall_rating
   - location

2. hospital_emergency
   - provider_id
   - hospital_name
   - emergency_services

3. hospital_lab_tests
   - provider_id
   - test_name

4. doctors
   - id
   - name
   - specialization
   - contact

5. doctor_slots
   - id
   - doctor_id
   - appointment_datetime
   - is_available

DOCTOR RELATIONSHIP:

doctors.id = doctor_slots.doctor_id

AVAILABLE APPOINTMENTS:

doctor_slots.is_available = 1

IMPORTANT:

For appointment searches, ALWAYS use:

doctor_slots.is_available = 1
AND doctor_slots.appointment_datetime >= DATE_ADD(UTC_TIMESTAMP(), INTERVAL 330 MINUTE)

Example:

SELECT
    d.id AS doctor_id,
    d.name AS doctor_name,
    d.specialization,
    d.contact,
    ds.appointment_datetime
FROM doctors d
JOIN doctor_slots ds
    ON d.id = ds.doctor_id
WHERE ds.is_available = 1
  AND ds.appointment_datetime >= DATE_ADD(UTC_TIMESTAMP(), INTERVAL 330 MINUTE)
ORDER BY ds.appointment_datetime
LIMIT 10;

Only SELECT queries are allowed.

Results are automatically limited to 20 rows.
"""

    def _run(self, query: str) -> str:

        return execute_healthsense_sql(query)


# ============================================================
# SIMPLE LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print(" IKHealthSense SQL TOOL TEST")
    print("=" * 70)

    tool = HealthSenseSQLTool()

    print()
    print("Testing hospital count...")

    result = tool.run(
        "SELECT COUNT(*) AS total_hospitals FROM hospitals"
    )

    print()
    print(result)

    print()
    print("Testing future cardiology appointments...")

    result = tool.run(
        """
        SELECT
            d.name AS doctor_name,
            d.specialization,
            ds.appointment_datetime
        FROM doctors d
        JOIN doctor_slots ds
            ON d.id = ds.doctor_id
        WHERE ds.is_available = 1
          AND ds.appointment_datetime >= DATE_ADD(UTC_TIMESTAMP(), INTERVAL 330 MINUTE)
          AND d.specialization = 'Cardiology'
        ORDER BY ds.appointment_datetime
        LIMIT 5
        """
    )

    print()
    print(result)

    print()
    print("=" * 70)
    print(" SQL TOOL TEST COMPLETED")
    print("=" * 70)