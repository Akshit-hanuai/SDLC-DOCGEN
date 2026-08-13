"""REST API for the telemetry acquisition subsystem (REQ-0001)."""

from fastapi import FastAPI, HTTPException

from .acquisition import AcquisitionEngine, Sample

app = FastAPI(title="telemetry-acq")
engine = AcquisitionEngine(num_channels=3, sample_rate_hz=100)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/acquire/start")
def start_acquisition() -> dict:
    engine.start()
    return {"started": True}


@app.get("/samples")
def get_samples() -> list[dict]:
    samples: list[Sample] = engine.read()
    return [{"channel": s.channel, "timestamp": s.timestamp, "values": s.values} for s in samples]


@app.post("/acquire/stop")
def stop_acquisition() -> dict:
    engine.stop()
    return {"stopped": True}


@app.get("/mtbf")
def get_mtbf() -> dict:
    raise HTTPException(status_code=501, detail="MTBF endpoint not yet implemented")
