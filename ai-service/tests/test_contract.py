from app.main import app

def test_master_contract_paths_exist():
    actual={(method.upper(),path) for path,methods in app.openapi()["paths"].items() for method in methods}
    expected={
        ("POST","/api/v1/auth/refresh"),("POST","/api/v1/auth/logout"),("PATCH","/api/v1/users/me"),("GET","/api/v1/users/{uid}"),
        ("GET","/api/v1/projects/{pid}"),("DELETE","/api/v1/projects/{pid}"),("GET","/api/v1/projects/{pid}/members"),("DELETE","/api/v1/projects/{pid}/members/{uid}"),
        ("GET","/api/v1/requirements/{rid}"),("PATCH","/api/v1/requirements/{rid}"),("POST","/api/v1/requirements/{rid}/analyze"),("POST","/api/v1/projects/{pid}/requirements/check-understanding"),("POST","/api/v1/projects/{pid}/requirements/compare"),
        ("GET","/api/v1/documents/{did}"),("GET","/api/v1/documents/{did}/status"),("DELETE","/api/v1/documents/{did}"),("POST","/api/v1/documents/{did}/reindex"),
        ("GET","/api/v1/questions/{qid}"),("POST","/api/v1/questions/{qid}/continue"),("POST","/api/v1/questions/{qid}/attempts"),("POST","/api/v1/questions/{qid}/feedback"),("POST","/api/v1/questions/{qid}/escalate"),("GET","/api/v1/questions/{qid}/similar"),
        ("GET","/api/v1/decisions/{did}"),("PATCH","/api/v1/decisions/{did}"),("POST","/api/v1/decisions/{did}/conflicts/check"),
        ("GET","/api/v1/escalations/{eid}"),("PATCH","/api/v1/escalations/{eid}"),("POST","/api/v1/escalations/{eid}/submit"),("POST","/api/v1/escalations/{eid}/withdraw"),
        ("GET","/api/v1/core/queue/{eid}"),("POST","/api/v1/core/escalations/{eid}/request-info"),
        ("GET","/api/v1/knowledge/{kid}"),("POST","/api/v1/knowledge/{kid}/feedback"),("POST","/api/v1/projects/{pid}/knowledge/search"),
        ("GET","/api/v1/projects/{pid}/issues/clusters"),("GET","/api/v1/issue-clusters/{cid}"),("POST","/api/v1/projects/{pid}/issues/recluster"),("GET","/api/v1/projects/{pid}/issues/recurring"),
        ("GET","/api/v1/tasks/{tid}"),("PATCH","/api/v1/tasks/{tid}"),("POST","/api/v1/tasks/{tid}/dependencies"),("GET","/api/v1/tasks/{tid}/blockers"),("GET","/api/v1/projects/{pid}/continue-options"),
        ("GET","/api/v1/jobs/{jid}"),("POST","/api/v1/projects/{pid}/rebuild-context"),("POST","/api/v1/projects/{pid}/reindex"),
        ("GET","/api/v1/projects/{pid}/analytics/overview"),("GET","/api/v1/projects/{pid}/analytics/issues"),("GET","/api/v1/core/analytics/recurring-issues"),("GET","/api/v1/core/analytics/escalations"),("GET","/api/v1/core/analytics/knowledge-reuse"),
    }
    assert not (expected-actual), sorted(expected-actual)
