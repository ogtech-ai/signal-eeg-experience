"""Package only committed demo source and explicitly allowlisted public EEG samples."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "signal-eeg-experience"
NOTICE = """Public EEG sample subset (derived O1/Oz/O2 microvolt arrays, 160 Hz).
Contains information from EEG Motor Movement/Imagery Dataset 1.0.0,
made available under the Open Data Commons Attribution License v1.0.
Source: https://physionet.org/content/eegmmidb/1.0.0/
License: https://physionet.org/content/eegmmidb/view-license/1.0.0/
Schalk, G. (2009), PhysioNet, DOI: 10.13026/C28G6P.
Full attribution and baseline limitations: ../docs/SOURCES.md, ../docs/VALIDATION.md.
R01 eyes open; R02 eyes closed. Public recording replay, not live device data.
These samples and evaluation are reproducible using scripts/prepare_data.py.
No customer recordings, private weights or credentials are included.
"""


def main():
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        raise SystemExit("Commit source changes before packaging.")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    output = ROOT / "artifacts" / "migration"
    output.mkdir(parents=True, exist_ok=True)
    source = output / f"{PREFIX}-source-{commit[:12]}.tar.gz"
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            f"--prefix={PREFIX}/",
            f"--output={source}",
            commit,
        ],
        cwd=ROOT,
        check=True,
    )
    samples = [
        ROOT / "data" / f"S{s:03d}R{r:02d}.npz" for s in range(1, 9) for r in (1, 2)
    ]
    samples += [ROOT / "data" / "manifest.json", ROOT / "data" / "evaluation.json"]
    for path in samples:
        if not path.is_file():
            raise SystemExit(f"Missing public sample component: {path.name}")
    data_archive = output / f"{PREFIX}-public-samples.tar.gz"
    # Fixed metadata makes repeated packaging of the same public samples deterministic.
    with data_archive.open("wb") as raw, gzip.GzipFile(
        filename="", mode="wb", fileobj=raw, mtime=0
    ) as compressed, tarfile.open(fileobj=compressed, mode="w") as tar:
        for path in samples:
            content = path.read_bytes()
            info = tarfile.TarInfo(f"{PREFIX}/data/{path.name}")
            info.mode = 0o644
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        content = NOTICE.encode()
        info = tarfile.TarInfo(f"{PREFIX}/data/DATA_NOTICE.md")
        info.mode = 0o644
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    source_names = []
    with tarfile.open(source) as tar:
        source_names = [m.name for m in tar.getmembers() if m.isfile()]
        for name in source_names:
            parts = Path(name).parts
            assert not set(parts) & {".git", ".venv", "artifacts", "__pycache__"}
            assert not name.endswith(
                (".env", ".edf", ".npz", ".joblib", ".pem", ".key")
            )
    manifest = {
        "source_root": str(ROOT),
        "source_commit": commit,
        "source_file_count": len(source_names),
        "target_platform": "linux/amd64",
        "archives": [
            {
                "file": p.name,
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in (source, data_archive)
        ],
        "public_sample_files": [
            {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in samples
        ],
        "private_data_or_credentials_included": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
