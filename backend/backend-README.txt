# dependencies:
pip install fastapi uvicorn[standard] boto3 python-dotenv pydantic

# !important
Add .env inside /backend (will shared)

# start backend service
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# test use the api
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"question": "Hello"}'