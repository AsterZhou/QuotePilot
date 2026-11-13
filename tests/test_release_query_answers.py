"""Public judging dataset and query-center regressions."""
from fastapi.testclient import TestClient

import server
from deploy.release_seed import seed_demo_history
from quotepilot.store import open_db


def test_judging_queries(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB", tmp_path / "judging.sqlite")
    monkeypatch.setenv("QUOTEPILOT_ENV", "development")
    monkeypatch.setenv("QUOTEPILOT_RELEASE_DEMO", "1")
    monkeypatch.setenv("QUOTEPILOT_PROVIDER", "mock")
    with TestClient(server.app) as client:
        reference = client.get("/api/query-center/status").json()["historical_reference_date"]
        assert reference == "2026-11-10"
        for question in server.QUESTIONS:
            response = client.post("/api/query-center/quick", json={"question":question, "asof":reference})
            assert response.status_code == 200
            assert response.json()["rows"]

        def ask(date, question="最近三个月哪个客户询问最多"):
            response = client.post("/api/query-center/ask", json={"question":question, "asof":date})
            assert response.status_code == 200
            return response.json()

        result = ask(reference)
        assert [row["询价份数"] for row in result["rows"]] == [3, 2, 1]
        assert result["rows"][0]["客户"] == "合成客户·星河"
        assert "3 份" in result["answer"]
        empty = ask("2027-05-31")
        assert empty["rows"] == []
        assert "无法确定排名" in empty["answer"]
        assert empty["sql_parameters"] == ["2027-02-28", "2027-05-31"]
        tied = ask("2026-09-30", "最近三个月哪些客户询价最多？")
        assert "并列第一" in tied["answer"]
        assert tied["returned_records"] == 2
        history = client.get("/api/query-center/sessions/" + result["session_id"]).json()["turns"]
        assert history[0]["answer"] == result["answer"]


def test_release_history_preserves_existing_data(tmp_path):
    con = open_db(tmp_path / "existing.sqlite")
    try:
        seed_demo_history(con)
        seed_demo_history(con)
        assert con.execute("SELECT COUNT(*) FROM historical").fetchone()[0] == 7
        with con:
            con.execute("DELETE FROM historical")
            con.execute("INSERT INTO historical (airline) VALUES ('已有客户')")
        seed_demo_history(con)
        assert [row[0] for row in con.execute("SELECT airline FROM historical")] == ["已有客户"]
    finally:
        con.close()

def test_sales_price_question_when_planner_is_unavailable(tmp_path):
    from quotepilot.query_center import run
    from quotepilot.store import open_db

    class UnavailableProvider:
        def complete_json(self, *_args, **_kwargs):
            raise TimeoutError

    db = tmp_path / "questions.sqlite"
    open_db(db).close()
    result = run(db, UnavailableProvider(), "数据库里能查到这些零件的实际成交价吗？", "2026-11-10", "demo")
    assert result["status"] == "clarify"
    assert result["failure_type"] == "TimeoutError"
    assert "sql" not in result
    assert result["clarification_options"] == ["查已审批报价", "查供应商报价"]
