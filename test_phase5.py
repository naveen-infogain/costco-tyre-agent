"""
Phase 5 smoke test — verifies FastAPI app starts and key routes respond.
Run: python test_phase5.py
Requires: pip install httpx fastapi uvicorn
Does NOT call the LLM (agents are lazy-loaded only on /chat).
"""
import sys
import threading
import time

def start_server():
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, log_level="error")

def run_tests():
    import httpx

    base = "http://127.0.0.1:8765"
    errors = []

    # 1. Health check
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        print(f"  ✅ GET /health → {data}")
    except Exception as e:
        print(f"  ❌ GET /health FAILED: {e}")
        errors.append("health")

    # 2. Dashboard API
    try:
        r = httpx.get(f"{base}/dashboard/api", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "funnel" in data
        assert "scorecard" in data
        assert len(data["scorecard"]) == 6
        top_score = max(a["score"] for a in data["scorecard"])
        print(f"  ✅ GET /dashboard/api → {len(data['funnel'])} funnel stages, top agent score: {top_score}")
    except Exception as e:
        print(f"  ❌ GET /dashboard/api FAILED: {e}")
        errors.append("dashboard_api")

    # 3. UI route (503 until Phase 6)
    try:
        r = httpx.get(f"{base}/", timeout=5)
        assert r.status_code in (200, 503)
        print(f"  ✅ GET / → status {r.status_code} (503 expected until Phase 6 UI is built)")
    except Exception as e:
        print(f"  ❌ GET / FAILED: {e}")
        errors.append("ui_route")

    # 4. Feedback endpoint (no LLM)
    try:
        r = httpx.post(f"{base}/feedback", json={
            "session_id": "test-p5",
            "signal": "thumbs_up",
            "tyre_id": "MIC-PRIM4-20555R16",
            "agent": "rec_ranking",
        }, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "recorded"
        print(f"  ✅ POST /feedback → score updated to {data.get('updated_score')}")
    except Exception as e:
        print(f"  ❌ POST /feedback FAILED: {e}")
        errors.append("feedback")

    # 5. OpenAPI docs exist
    try:
        r = httpx.get(f"{base}/openapi.json", timeout=5)
        assert r.status_code == 200
        schema = r.json()
        paths = list(schema.get("paths", {}).keys())
        print(f"  ✅ GET /openapi.json → {len(paths)} routes: {paths}")
    except Exception as e:
        print(f"  ❌ GET /openapi.json FAILED: {e}")
        errors.append("openapi")

    return errors


if __name__ == "__main__":
    print("\n=== Phase 5 Smoke Test ===\n")
    print("Starting test server on port 8765...")

    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(3)  # wait for server to be ready

    errors = run_tests()

    print("\n" + "=" * 30)
    if errors:
        print(f"❌ {len(errors)} failure(s): {errors}")
        sys.exit(1)
    else:
        print("✅ All Phase 5 checks passed — ready for Phase 6 (Chat UI)")
