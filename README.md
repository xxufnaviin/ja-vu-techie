# dependencies:
```
pip install fastapi uvicorn[standard] boto3 python-dotenv pydantic requests_aws4auth
```
# !important
Add .env inside /backend (will shared)

# start backend service
```
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

#start frontend service
```
cd frontend/healthspan-chat
npm run dev
```
