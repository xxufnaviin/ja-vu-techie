# Backend
## Dependencies:
```
pip install fastapi uvicorn[standard] boto3 python-dotenv pydantic requests_aws4auth
```
## Start backend service
#### important: add .env before start
```
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

# Frontend
## Dependencies:
```
npm install
```
## Start frontend service
```
cd frontend\healthspan-chat
npm run dev
```
