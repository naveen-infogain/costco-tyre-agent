# Test the chat endpoint

Send a test message to the Costco Tyre Agent chat API. Tests both Path A (returning buyer M10042) and Path B (new buyer M10044).

## Test Path A — Returning Buyer (Sarah Chen)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-path-a", "message": "M10042"}' | python -m json.tool
```

## Test Path B — New Buyer (Emily Torres)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-path-b", "message": "M10044"}' | python -m json.tool
```

## Quick health check

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

## View dashboard analytics

```bash
curl -s http://localhost:8000/dashboard/api | python -m json.tool
```
