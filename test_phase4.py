"""
Phase 4 smoke test — verifies all agents import correctly and instantiate.
Run: python test_phase4.py
Does NOT call the LLM (no API key needed for this test).
"""
import sys

def test_imports():
    errors = []
    agents = [
        ("BaseAgent", "app.agents.base_agent", "BaseAgent"),
        ("GuardrailAgent", "app.agents.guardrail_agent", "GuardrailAgent"),
        ("OrchestratorAgent", "app.agents.orchestrator", "OrchestratorAgent"),
        ("RecRankingAgent", "app.agents.rec_ranking_agent", "RecRankingAgent"),
        ("ContentAgent", "app.agents.content_agent", "ContentAgent"),
        ("CompareAgent", "app.agents.compare_agent", "CompareAgent"),
        ("AppointmentAgent", "app.agents.appointment_agent", "AppointmentAgent"),
    ]
    for label, module_path, class_name in agents:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            print(f"  ✅ {label} imported from {module_path}")
        except Exception as e:
            print(f"  ❌ {label} FAILED: {e}")
            errors.append(label)
    return errors

def test_tools():
    errors = []
    tools = [
        ("search_tyres", "app.tools.recommendation_tools", "search_tyres"),
        ("generate_personalised_msg", "app.tools.content_tools", "generate_personalised_msg"),
        ("generate_comparison_card", "app.tools.compare_tools", "generate_comparison_card"),
        ("book_appointment", "app.tools.appointment_tools", "book_appointment"),
        ("check_hallucination", "app.tools.guardrail_tools", "check_hallucination"),
        ("load_member_session", "app.tools.profile_tools", "load_member_session"),
    ]
    for label, module_path, fn_name in tools:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            print(f"  ✅ {label} loaded")
        except Exception as e:
            print(f"  ❌ {label} FAILED: {e}")
            errors.append(label)
    return errors

def test_services():
    errors = []
    try:
        from app.services.stock_service import search_tyres
        results = search_tyres(size="205/55R16", season="all-season")
        assert len(results) > 0, "No results returned"
        print(f"  ✅ stock_service.search_tyres → {len(results)} tyres found")
    except Exception as e:
        print(f"  ❌ stock_service FAILED: {e}")
        errors.append("stock_service")

    try:
        from app.services.profile_service import get_member
        user = get_member("M10042")
        assert user is not None
        assert user.name == "Sarah Chen"
        print(f"  ✅ profile_service.get_member → {user.name} ({user.membership_tier})")
    except Exception as e:
        print(f"  ❌ profile_service FAILED: {e}")
        errors.append("profile_service")

    try:
        from app.services.eval_service import get_scorecard
        sc = get_scorecard()
        assert len(sc) == 6
        print(f"  ✅ eval_service.get_scorecard → {len(sc)} agents, top score: {max(a['score'] for a in sc)}")
    except Exception as e:
        print(f"  ❌ eval_service FAILED: {e}")
        errors.append("eval_service")

    return errors

def test_guardrail_direct():
    errors = []
    try:
        from app.agents.guardrail_agent import GuardrailAgent
        g = GuardrailAgent()
        result = g.check(
            response="The Michelin Primacy 4 is a great tyre at $169.99 member price.",
            session_id="test-session",
            tyre_ids=["MIC-PRIM4-20555R16"],
            vehicle={"make": "Toyota", "model": "Camry", "year": 2020},
        )
        assert result is not None, "Guardrail rejected a valid response"
        print(f"  ✅ GuardrailAgent.check → response passed all 5 checks")
    except Exception as e:
        print(f"  ❌ GuardrailAgent.check FAILED: {e}")
        errors.append("guardrail")
    return errors


if __name__ == "__main__":
    print("\n=== Phase 4 Smoke Test ===\n")

    print("1. Agent imports:")
    e1 = test_imports()

    print("\n2. Tool imports:")
    e2 = test_tools()

    print("\n3. Service layer:")
    e3 = test_services()

    print("\n4. Guardrail (no LLM):")
    e4 = test_guardrail_direct()

    all_errors = e1 + e2 + e3 + e4
    print("\n" + "="*30)
    if all_errors:
        print(f"❌ {len(all_errors)} failure(s): {all_errors}")
        sys.exit(1)
    else:
        print("✅ All Phase 4 checks passed — ready for Phase 5")
