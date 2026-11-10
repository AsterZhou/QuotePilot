from pathlib import Path

from fastapi.testclient import TestClient

import server

SAMPLES = Path(__file__).resolve().parents[1] / "web" / "guide" / "samples"


def test_guide_files_at_their_upload_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB", tmp_path / "upload.sqlite")
    monkeypatch.setattr(server, "seed_official", lambda *_: None)
    monkeypatch.setenv("QUOTEPILOT_ENV", "development")
    monkeypatch.delenv("QUOTEPILOT_RELEASE_DEMO", raising=False)
    with TestClient(server.app) as client:
        name = "01_customer_inquiry.eml"
        sample = client.get("/guide/samples/" + name)
        assert sample.is_success and sample.content == (SAMPLES / name).read_bytes()
        file = {"file": (name, sample.content)}
        preview = client.post("/api/emails/preview", files=file).json()
        assert preview["count"] == 1
        line = preview["sample_lines"][0]
        assert (line["part_number"], line["quantity"], line["unit"], line["condition"]) == ("PN-0001", 3, "EA", "FN")
        first = client.post("/api/emails/import", files=file).json()
        repeat = client.post("/api/emails/import", files=file).json()
        assert first["new_lines"] == 1 and not first["already_imported"]
        assert repeat["new_lines"] == 0 and repeat["already_imported"]
        assert first["email_id"] == repeat["email_id"]
        natural = {"file": ("inquiry.eml", (SAMPLES / "inquiry.eml").read_bytes())}
        assert client.post("/api/emails/preview", files=natural).json()["count"] == 0
        assert client.post("/api/emails/import", files=natural).json()["ok"]
        pdf = client.get("/guide/samples/suppliers.pdf").content
        supplier = {"file": ("renamed.pdf", pdf)}
        for endpoint in ("preview", "import"):
            response = client.post("/api/emails/" + endpoint, files=supplier)
            assert response.status_code == 422 and "第三步" in response.json()["detail"]
        source = client.post("/api/supplier-offers/sources", files=supplier).json()["source_id"]
        candidates = client.post(f"/api/supplier-offers/sources/{source}/extract").json()["candidates"]
        assert [row["values"]["supplier"] for row in candidates] == ["SYN-Cheap", "SYN-Fast", "SYN-Balanced"]
