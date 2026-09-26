# IKHealthSense Backend

FastAPI + CrewAI + LangChain + AWS RDS MySQL.

## Start virtual environment

.\.venv\Scripts\Activate.ps1

## Configure .env

Set:

MYSQL_PASSWORD=YOUR_PASSWORD
OPENAI_API_KEY=YOUR_OPENAI_API_KEY

## Run API

uvicorn main:app --reload

## Swagger

http://127.0.0.1:8000/docs
