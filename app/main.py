from typing import Literal
from fastapi import Request
from fastapi.responses import Response
from .reporting import MAX_BYTES, analyze_report, csv_bytes, demo_record, parse_csv
import hashlib
from functools import lru_cache
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import ROOT, FS, CHANNELS, load_record, train, features, quality

app = FastAPI(title="OG EEG 檢測報告工作台", version="0.2.0")
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")


@lru_cache(maxsize=2)
def baseline(source):
    return train(source)


def source_check(source):
    if source not in ("synthetic", "physionet"):
        raise HTTPException(422, "未知資料來源")


@app.get("/")
def index():
    return FileResponse(ROOT / "app/static/index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "device_connected": False}


@app.get("/api/catalog")
def catalog():
    available = all(
        (ROOT / "data" / f"S{s:03d}R{r:02d}.npz").exists()
        for s in range(1, 9)
        for r in (1, 2)
    )
    return {
        "public_available": available,
        "channels": CHANNELS,
        "sample_rate": FS,
        "device_connected": False,
    }


@app.get("/api/record")
def record(source: str = "synthetic", closed: bool = False, subject: int = 7):
    source_check(source)
    if subject not in (7, 8):
        raise HTTPException(422, "展示受試者限 7、8")
    try:
        x = load_record(subject, closed, source)
    except FileNotFoundError as e:
        raise HTTPException(409, str(e))
    return {
        "signal": x[:, ::2].round(3).tolist(),
        "sample_rate": FS / 2,
        "duration": x.shape[1] / FS,
        "source": source,
        "label": "閉眼" if closed else "睜眼",
        "subject": subject,
        "channels": CHANNELS,
    }


class Analysis(BaseModel):
    source: str = "synthetic"
    subject: int = Field(default=7, ge=7, le=8)
    closed: bool = False
    start: float = Field(default=0, ge=0)
    duration: float = Field(default=4, ge=4, le=10)
    artifact: bool = False


@app.post("/api/analyze")
def analyze(req: Analysis):
    source_check(req.source)
    tick = time.perf_counter()
    try:
        x = load_record(req.subject, req.closed, req.source)
        if req.start + req.duration > x.shape[1] / FS:
            raise HTTPException(422, "片段超出錄製長度")
        x = x[:, int(req.start * FS) : int((req.start + req.duration) * FS)].copy()
        if req.artifact:
            x[0, FS : FS + 8] += 400
        q = quality(x)
        feat, bands = features(x)
        model, report = baseline(req.source)
    except FileNotFoundError as e:
        raise HTTPException(409, str(e))
    probability = float(model.predict_proba([feat])[0, 1]) if q["accepted"] else None
    label = (
        ("閉眼" if probability >= 0.5 else "睜眼")
        if probability is not None
        else "暫停判讀"
    )
    summary = f"{('合成訊號功能測試' if req.source=='synthetic' else 'PhysioNet 公開 EEG 錄製回放')}，S{req.subject:03d}，{req.start:.1f}–{req.start+req.duration:.1f} 秒。品質{'通過' if q['accepted'] else '未通過'}，模型結果：{label}。Alpha 相對功率 {bands[1]*100:.1f}%。此為研究任務辨識，非壓力、疾病或療效評估；幸福腦硬體尚未串接。"
    return {
        "request": req.model_dump(),
        "record_label": "eyes_closed" if req.closed else "eyes_open",
        "model_version": "welch-log-relative-lr-v1",
        "data_reference": "https://physionet.org/content/eegmmidb/1.0.0/"
        if req.source == "physionet"
        else "app.core.synthetic deterministic generator",
        "quality": q,
        "closed_probability": probability,
        "prediction": label,
        "bands": dict(zip(("theta", "alpha", "beta"), bands.tolist())),
        "summary": summary,
        "evaluation": report,
        "elapsed_ms": round((time.perf_counter() - tick) * 1000, 2),
        "artifact_injected": req.artifact,
        "source": req.source,
        "segment_signal": x[:, ::2].round(3).tolist(),
        "sample_rate": FS / 2,
    }


@app.get("/api/model")
def model(source: str = "synthetic"):
    source_check(source)
    try:
        return baseline(source)[1]
    except FileNotFoundError as e:
        raise HTTPException(409, str(e))


# New report workflow: no patient fields or uploaded files are persisted.


@app.middleware("http")
async def report_privacy_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/report/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/report/catalog")
def report_catalog():
    public = all((ROOT / "data" / f"S008R{r:02d}.npz").exists() for r in (1, 2))
    return {
        "public_available": public,
        "sources": [
            {"id": "public-open", "label": "公開 EEG · S008 睜眼", "available": public},
            {
                "id": "public-closed",
                "label": "公開 EEG · S008 閉眼",
                "available": public,
            },
            {
                "id": "synthetic-artifacts",
                "label": "合成示範 · 含人工偽跡",
                "available": True,
            },
            {
                "id": "synthetic-clean",
                "label": "合成示範 · 乾淨訊號",
                "available": True,
            },
        ],
        "upload": {
            "format": "UTF-8 CSV",
            "max_bytes": MAX_BYTES,
            "max_channels": 8,
            "sample_rate_hz": [128, 512],
            "duration_seconds": [8, 120],
        },
    }


@app.get("/api/report/demo")
def report_demo(source: str = "synthetic-artifacts"):
    try:
        x, fs, channels, meta = demo_record(source)
        digest = hashlib.sha256(x.astype("<f8").tobytes()).hexdigest()
        return analyze_report(x, fs, channels, meta, digest)
    except FileNotFoundError as error:
        raise HTTPException(
            409, "公開樣本尚未下載；仍可選擇明確標示的合成示範。"
        ) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/report/demo.csv")
def report_demo_csv(source: str = "synthetic-artifacts"):
    try:
        x, fs, channels, _ = demo_record(source)
        return Response(
            csv_bytes(x, fs, channels),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="eeg-demo.csv"'},
        )
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(422, "此示範來源不可用。") from error


@app.post("/api/report/upload")
async def report_upload(
    request: Request,
    condition: Literal["eyes_open", "eyes_closed", "unspecified"] = "unspecified",
):
    if request.headers.get("content-type", "").split(";")[0] not in (
        "text/csv",
        "application/octet-stream",
    ):
        raise HTTPException(
            415, "此版只接受原始 UTF-8 CSV，不接受 EDF、multipart 或壓縮檔。"
        )
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_BYTES):
        raise HTTPException(413, "上傳大小上限為 8 MiB。")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "上傳大小上限為 8 MiB。")
        body.extend(chunk)
    try:
        x, fs, channels = parse_csv(body)
        digest = hashlib.sha256(body).hexdigest()
        return analyze_report(
            x,
            fs,
            channels,
            {
                "kind": "upload",
                "label": "使用者上傳 CSV",
                "condition": condition,
                "reference": "本次工作階段；SHA-256 見報告",
                "notice": "使用者提供的數值，未獨立驗證其來源。沒有儲存檔案、個案資料或共享 session。",
            },
            digest,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
