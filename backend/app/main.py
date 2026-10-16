"""ForgeGuard AI API (CLAUDE.md section 6 - FROZEN contract). Base path /api, JSON.

Every error is HTTP 4xx/5xx with {"error": "plain message"} - no stack traces, keys or internal URLs.
Run from the repo root:  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
"""

import logging

from fastapi import APIRouter, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app import explain
from backend.app.datasets import listed_datasets, load_demo_frames
from backend.app.pipeline import AnalysisError, analyze
from backend.app.schemas import AnalysisResult, DatasetInfo, HealthResponse, InspectionReport, LLMStatus
from backend.app.settings import get_settings
from backend.app.store import runs
from backend.app.validation import UploadError, check_upload, read_csv_bytes, resolve_dataset

log = logging.getLogger("forgeguard")
settings = get_settings()

app = FastAPI(title="ForgeGuard AI API", version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_origin_regex=settings.frontend_origin_regex or None,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    if exc.status_code == 404 and message == "Not Found":
        message = "Not found."
    return JSONResponse(status_code=exc.status_code, content={"error": message})


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
    reason = first.get("msg", "invalid value")
    return JSONResponse(status_code=400, content={"error": f"Missing or invalid field '{field}': {reason}."})


@app.exception_handler(Exception)
async def _unexpected_error(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"error": "Internal server error. Please try again."})


api = APIRouter(prefix="/api")


@api.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@api.get("/datasets", response_model=list[DatasetInfo])
def datasets() -> list[DatasetInfo]:
    return [d.info() for d in listed_datasets()]


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read(settings.max_upload_bytes + 1)
    check_upload(upload.filename, len(data), settings.max_upload_bytes)
    return data


def _run(readings_raw, notes_raw, dataset, is_demo: bool) -> AnalysisResult:
    try:
        result = analyze(readings_raw, notes_raw, dataset).result
    except AnalysisError as exc:
        raise ApiError(400, str(exc)) from None
    runs.put(result, is_demo=is_demo)
    return result


@api.post("/analyze", response_model=AnalysisResult)
async def analyze_upload(
    readings: UploadFile = File(...),
    notes: UploadFile | None = File(None),
    dataset_hint: str | None = Form(None),
) -> AnalysisResult:
    try:
        readings_raw = read_csv_bytes(await _read_upload(readings), readings.filename or "readings")
        notes_raw = None
        if notes is not None and notes.filename:
            notes_raw = read_csv_bytes(await _read_upload(notes), notes.filename)
        dataset = resolve_dataset(list(readings_raw.columns), dataset_hint)
    except UploadError as exc:
        raise ApiError(400, str(exc)) from None
    return await run_in_threadpool(_run, readings_raw, notes_raw, dataset, False)


@api.post("/analyze/demo/{dataset_id}", response_model=AnalysisResult)
def analyze_demo(dataset_id: str) -> AnalysisResult:
    if dataset_id not in {d.id for d in listed_datasets()}:
        known = ", ".join(d.id for d in listed_datasets())
        raise ApiError(404, f"Unknown demo dataset '{dataset_id}'. Available: {known}.")
    readings_raw, notes_raw = load_demo_frames(dataset_id)
    return _run(readings_raw, notes_raw, dataset_id, True)


@api.post("/runs/{run_id}/explain/{machine_id}", response_model=InspectionReport)
def explain_machine(run_id: str, machine_id: str) -> InspectionReport:
    run = runs.get(run_id)
    if run is None:
        raise ApiError(404, "Run not found. It may have expired - please run the analysis again.")
    try:
        return explain.explain_machine(run, machine_id)
    except KeyError:
        raise ApiError(404, f"Machine '{machine_id}' is not in this run.") from None


@api.get("/llm/status", response_model=LLMStatus)
def llm_status() -> LLMStatus:
    return explain.llm_status()


app.include_router(api)
