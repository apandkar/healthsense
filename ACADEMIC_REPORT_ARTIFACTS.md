# IKHealthSense: Academic Architecture & Report Artifacts

## System Architecture
FastAPI -> CrewAI Multi-Agent Coordinator -> SQL Safety Filter -> AWS RDS MySQL

## Database Tables
- doctors (id, name, specialization, contact)
- doctor_slots (id, doctor_id, appointment_datetime, is_available)
- hospitals (provider_id, hospital_name, city, emergency_services)

## Concurrency Control
Row-level lock using SELECT ... FOR UPDATE ensures race-condition-free slot booking.
