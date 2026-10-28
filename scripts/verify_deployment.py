"""Read-only HTTP acceptance checks for an explicitly selected demo URL."""

import argparse
import json
import urllib.request


def verify(base_url):
    base = base_url.rstrip("/")

    def get(path):
        with urllib.request.urlopen(base + path, timeout=30) as response:
            return json.load(response)

    def analyze(source, artifact=False):
        payload = {
            "source": source,
            "subject": 8,
            "start": 12,
            "duration": 4,
            "artifact": artifact,
        }
        request = urllib.request.Request(
            base + "/api/analyze",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    assert get("/api/health") == {"status": "ok", "device_connected": False}
    catalog = get("/api/catalog")
    assert catalog["sample_rate"] == 160 and catalog["public_available"]
    results = {}
    for source in ("synthetic", "physionet"):
        clean = analyze(source)
        assert clean["quality"]["accepted"] and clean["closed_probability"] is not None
        evaluation = clean["evaluation"]
        assert set(evaluation["train_subjects"]).isdisjoint(evaluation["test_subjects"])
        rejected = analyze(source, True)
        assert (
            not rejected["quality"]["accepted"]
            and rejected["closed_probability"] is None
        )
        results[source] = {
            "accepted": True,
            "artifact_rejected": True,
            "test_coverage": f"{evaluation['test_windows']}/{evaluation['test_total_windows']}",
            "balanced_accuracy_on_accepted_windows": evaluation["balanced_accuracy"],
        }
    print(json.dumps({"url": base, "status": "passed", "results": results}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    verify(parser.parse_args().base_url)
