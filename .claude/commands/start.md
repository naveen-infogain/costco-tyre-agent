# Start the Costco Tyre Agent server

Install dependencies (if needed) and start the FastAPI development server.

```bash
cd c:\Users\satti.naveen\costco-tyre-agent
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The server will be available at:
- Chat UI: http://localhost:8000
- Dashboard: http://localhost:8000/dashboard
- API docs: http://localhost:8000/docs
