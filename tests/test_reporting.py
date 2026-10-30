import hashlib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.reporting import (
    analyze_report,
    band_integral,
    csv_bytes,
    demo_record,
    parse_csv,
    VERSION,
)

client = TestClient(app)


def csv_signal(seconds=12, fs=160):
    t = np.arange(seconds * fs) / fs
    x = np.array([20 * np.sin(2 * np.pi * 10 * t), 15 * np.sin(2 * np.pi * 6 * t)])
    return csv_bytes(x, fs, ["O1", "O2"]), x


def test_csv_roundtrip_and_real_band_math():
    payload, original = csv_signal()
    x, fs, channels = parse_csv(payload)
    np.testing.assert_array_equal(x, original)
    report = analyze_report(
        x,
        fs,
        channels,
        {"kind": "upload", "condition": "eyes_open"},
        hashlib.sha256(payload).hexdigest(),
    )
    assert report["analysis_version"] == VERSION
    assert report["quality"]["included_windows"] == 3
    assert np.isclose(sum(b["relative"] for b in report["bands"]), 1)
    powers = {b["name"]: b["relative"] for b in report["bands"]}
    assert powers["alpha"] > 0.6 and powers["theta"] > 0.25
    assert "closed_probability" not in report and "disease_score" not in report
    f = np.asarray(report["psd"]["frequencies_hz"])
    p = np.asarray(report["psd"]["power_uv2_hz"]).mean(axis=0)
    assert np.isclose(
        sum(b["power_uv2"] for b in report["bands"]), band_integral(f, p, 0.5, 30)
    )
    np.testing.assert_array_equal(x, original)


def test_mask_and_suspicions_are_separate_from_conditions():
    x, fs, channels, meta = demo_record("synthetic-artifacts")
    original = x.copy()
    first = analyze_report(x, fs, channels, {**meta, "condition": "eyes_open"}, "abc")
    second = analyze_report(
        x, fs, channels, {**meta, "condition": "eyes_closed"}, "abc"
    )
    assert first["windows"] == second["windows"]
    assert (
        first["preprocessing"]["window_mask"] == second["preprocessing"]["window_mask"]
    )
    assert {"Q1", "Q2", "A1", "A2"} <= {e["rule_id"] for e in first["events"]}
    for w in first["windows"]:
        assert w["included"] == (not bool(w["exclude_rules"]))
    np.testing.assert_array_equal(x, original)
    assert first["preprocessing"]["original_modified"] is False


def test_all_rejected_never_fakes_zero_or_diagnosis():
    x = np.zeros((1, 160 * 8))
    report = analyze_report(
        x, 160, ["O1"], {"kind": "synthetic", "condition": "unspecified"}, "zero"
    )
    assert report["quality"]["included_windows"] == 0
    assert report["bands"] == [] and report["psd"]["power_uv2_hz"] is None
    assert len(report["signal"][0]) == 1280
    assert len(report["windows"]) == 2


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not-a-csv",
        b"time_s,O1\n0,1\n",
        b"time_s,O1_uV,O1_uV\n0,1,1\n",
        b"time_s,EOG_uV\n0,1\n",
        b"time_s,O1_uV\n0,nan\n",
        b"time_s,O1_uV\n0,inf\n",
        b"time_s,O1_uV\n0,1\n0,2\n",
        b"time_s,O1_uV\n0,1\n0.00625,=1+1\n",
        b"\xff\xfe\x00",
        b"time_s,O1_uV\n0,1\n1e308,1\n",
    ],
)
def test_upload_validation_errors_are_readable(payload):
    r = client.post(
        "/api/report/upload", content=payload, headers={"Content-Type": "text/csv"}
    )
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert r.headers["cache-control"] == "no-store"


def test_sampling_size_and_duration_limits():
    for fs, seconds in ((64, 12), (1024, 8), (160, 4), (160, 121)):
        payload, _ = csv_signal(seconds, fs)
        with pytest.raises(ValueError):
            parse_csv(payload)
    payload, _ = csv_signal()
    lines = payload.decode().splitlines()
    values = lines[20].split(",")
    values[0] = str(float(values[0]) + 0.001)
    lines[20] = ",".join(values)
    with pytest.raises(ValueError, match="間隔"):
        parse_csv("\n".join(lines).encode())
    r = client.post(
        "/api/report/upload",
        content=b"x" * (8 * 1024 * 1024 + 1),
        headers={"Content-Type": "text/csv"},
    )
    assert r.status_code == 413
    assert (
        client.post(
            "/api/report/upload",
            content=b"EDF",
            headers={"Content-Type": "application/edf"},
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/report/upload?condition=diagnosis",
            content=payload,
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 422
    )


def test_upload_is_stateless_and_has_no_patient_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload, _ = csv_signal()
    first = client.post(
        "/api/report/upload?condition=eyes_closed",
        content=payload,
        headers={"Content-Type": "text/csv"},
    )
    second = client.post(
        "/api/report/upload?condition=eyes_closed",
        content=payload,
        headers={"Content-Type": "text/csv"},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["report_id"] == second.json()["report_id"]
    assert first.json()["raw_sha256"] == hashlib.sha256(payload).hexdigest()
    assert first.json()["source"]["condition"] == "eyes_closed"
    assert not list(tmp_path.iterdir())
    assert "case_background" not in first.json()
    assert client.get("/api/report/upload").status_code == 405


def test_demo_csv_and_public_report_reproducibility():
    synthetic = client.get("/api/report/demo?source=synthetic-artifacts")
    assert (
        synthetic.status_code == 200
        and synthetic.headers["cache-control"] == "no-store"
    )
    csv_response = client.get("/api/report/demo.csv?source=synthetic-artifacts")
    x, fs, channels = parse_csv(csv_response.content)
    np.testing.assert_array_equal(x, np.asarray(synthetic.json()["signal"]))
    assert fs == 160 and channels == ["Fp1", "Fp2", "O1"]
    catalog = client.get("/api/report/catalog").json()
    if catalog["public_available"]:
        a = client.get("/api/report/demo?source=public-open").json()
        b = client.get("/api/report/demo?source=public-open").json()
        assert a == b
        assert (
            a["quality"]["total_windows"] == 15
            and a["quality"]["included_windows"] == 13
        )
        assert a["quality"]["unscored_tail_seconds"] == 1
        assert a["source"]["kind"] == "public"


def test_missing_optional_public_samples_keep_synthetic_reports_available(
    monkeypatch, tmp_path
):
    import app.core as core
    import app.main as main

    monkeypatch.setattr(core, "ROOT", tmp_path)
    monkeypatch.setattr(main, "ROOT", tmp_path)
    catalog = client.get("/api/report/catalog").json()
    assert catalog["public_available"] is False
    for source in ("public-open", "public-closed"):
        entry = next(s for s in catalog["sources"] if s["id"] == source)
        assert entry["available"] is False
        response = client.get(f"/api/report/demo?source={source}")
        assert response.status_code == 409
        assert "公開樣本尚未下載" in response.json()["detail"]
    for source in ("synthetic-clean", "synthetic-artifacts"):
        response = client.get(f"/api/report/demo?source={source}")
        assert response.status_code == 200
        assert response.json()["source"]["kind"] == "synthetic"
    assert not list(tmp_path.iterdir())
