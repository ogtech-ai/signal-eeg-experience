from functools import lru_cache
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import ROOT, FS, CHANNELS, load_record, train, features, quality

app = FastAPI(title="OG 幸福腦技術體驗", version="0.1.0")
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
