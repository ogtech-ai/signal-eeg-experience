"""Read-only report acceptance for an explicitly selected deployment URL."""

import argparse
import json
import urllib.request


def verify(base_url):
    base = base_url.rstrip("/")

    def get(path):
        with urllib.request.urlopen(base + path, timeout=30) as response:
            result = json.load(response)
            if path.startswith("/api/report/"):
                assert response.headers["Cache-Control"] == "no-store"
            return result

    assert get("/api/health") == {"status": "ok", "device_connected": False}
    results = {}
    for source in ("synthetic-clean", "synthetic-artifacts", "public-open"):
        result = get("/api/report/demo?source=" + source)
        assert len(result["bands"]) == 4
        assert abs(sum(b["relative"] for b in result["bands"]) - 1) < 1e-6
        assert result["quality"]["included_windows"] > 0
        results[source] = result["quality"]
    print(json.dumps({"url": base, "status": "passed", "quality": results}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    verify(parser.parse_args().base_url)
