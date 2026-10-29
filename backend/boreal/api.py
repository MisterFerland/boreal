"""Same-origin FastAPI application. All business work executes in durable workers."""

import hashlib
import io
import json
import logging
import os
import re
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

import psycopg
from fastapi import Depends, FastAPI, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import engine, schemas, service
from .auth import COOKIE, ORIGIN, current_user, fail, login, require, token_hash, validate_configuration
from .common import audit, canonical, clean, financial_records, verify_audit
from .db import connect

ROOT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger("boreal.api")
if not LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(handler)
LOG.setLevel(logging.INFO)
LOG.propagate = False
User = Annotated[dict, Depends(current_user)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
Page = Annotated[int, Query(ge=1, le=100000)]
Size = Annotated[int, Query(ge=1, le=100)]


def engine_archive(build):
    return Path(os.environ.get("BOREAL_ENGINE_BUILDS", str(ROOT / "engine" / "builds"))) / build


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


class PostRequest(BaseModel):
    failure_mode: Literal["before_commit", "after_commit"] | None = None


class ReasonRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=1000)


class SessionUser(BaseModel):
    id: str
    username: str
    role: Literal["operator", "approver", "auditor"]


class SessionResponse(BaseModel):
    user: SessionUser
    csrf: str


@asynccontextmanager
async def lifespan(app):
    validate_configuration()
    yield


app = FastAPI(
    title="BOREAL local synthetic operations", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None
)
host = urlparse(ORIGIN).hostname or "127.0.0.1"
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host, "localhost", "127.0.0.1", "[::1]"])


@app.middleware("http")
async def request_context(request, call_next):
    correlation = str(uuid.uuid4())
    request.state.correlation_id = correlation
    started = time.perf_counter()
    if (
        request.headers.get("content-length", "").isdigit()
        and int(request.headers["content-length"]) > service.MAX_UPLOAD + 65536
    ):
        return JSONResponse(
            {"detail": {"code": "UPLOAD_SIZE", "message": "The upload limit is 12 MiB."}}, status_code=413
        )
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    LOG.info(
        canonical(
            {
                "event": "http",
                "correlation_id": correlation,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(
        {
            "detail": {
                "code": "INVALID_REQUEST",
                "message": "Request fields are missing or invalid.",
                "fields": [list(e["loc"]) for e in exc.errors()],
            }
        },
        status_code=422,
    )


@app.exception_handler(psycopg.errors.UniqueViolation)
async def duplicate_error(request, exc):
    return JSONResponse(
        {
            "detail": {
                "code": "BUSINESS_KEY_CONFLICT",
                "message": "This financial business key already exists; no duplicate effect was committed.",
            }
        },
        status_code=409,
    )


@app.exception_handler(Exception)
async def internal_error(request, exc):
    correlation = getattr(request.state, "correlation_id", "unknown")
    LOG.exception("Unhandled request failure correlation=%s", correlation)
    return JSONResponse(
        {
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "The operation failed. Use the correlation ID to inspect local logs.",
                "correlation_id": correlation,
            }
        },
        status_code=500,
    )


@app.post("/api/auth/login", response_model=SessionResponse)
def sign_in(body: LoginRequest, request: Request, response: Response):
    return login(request, response, body.username, body.password)


@app.get("/api/auth/me", response_model=SessionResponse)
def me(user: User):
    return {"user": {k: user[k] for k in ("id", "username", "role")}, "csrf": user["csrf"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user: User):
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash(request.cookies.get(COOKIE, "")),))
        audit(conn, user["id"], "session.ended", user["id"])
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


def health():
    info = engine.build_info()
    with connect() as conn:
        worker = conn.execute(
            "SELECT max(seen_at)>now()-interval '90 seconds' AS healthy FROM worker_health"
        ).fetchone()["healthy"]
    return {
        "engine": "ready" if info.get("available") else "unavailable",
        "worker": "online" if worker else "offline",
        "engine_build": info.get("engine_build"),
        "compiler": info.get("compiler"),
        "demo": os.environ.get("BOREAL_DEMO") == "1",
    }


@app.get("/api/health/live")
def live():
    return {"status": "alive"}


@app.get("/api/health/ready")
def ready(response: Response):
    state = health()
    if state["engine"] != "ready" or state["worker"] != "online":
        response.status_code = 503
    return state


@app.get("/api/overview", response_model=schemas.Overview)
def overview(user: User):
    with connect() as conn:
        metrics = conn.execute("""SELECT
          (SELECT coalesce(sum(payable_total),0)::numeric(16,2) FROM batches WHERE result_digest IS NOT NULL) AS calculated,
          (SELECT coalesce(sum(b.payable_total),0)::numeric(16,2) FROM batches b JOIN approvals a ON a.batch_id=b.id) AS approved,
          (SELECT coalesce(sum(amount),0)::numeric(16,2) FROM journals WHERE kind='obligation') AS posted,
          (SELECT coalesce(sum(amount),0)::numeric(16,2) FROM journals WHERE kind='settlement') AS settled,
          (SELECT coalesce(sum(CASE WHEN kind='obligation' THEN amount ELSE -amount END),0)::numeric(16,2) FROM journals) AS outstanding,
          (SELECT count(*) FROM reconciliations WHERE classification<>'MATCH' AND state<>'accepted') AS exceptions,
          (SELECT count(*) FROM batches) AS batches""").fetchone()
        recent = [service.batch_view(r) for r in conn.execute("SELECT * FROM batches ORDER BY created_at DESC LIMIT 6")]
        activity = [
            service.audit_view(r) for r in conn.execute("SELECT * FROM audit ORDER BY sequence DESC LIMIT 8").fetchall()
        ]
    return {"metrics": clean(metrics), "recent_batches": recent, "health": health(), "activity": activity}


def paginate(conn, table, where, params, page, page_size, order="created_at DESC", columns="*", mapper=clean):
    # table/where/order/columns are code-owned allowlists, never raw query strings.
    total = conn.execute(f"SELECT count(*) AS n FROM {table} WHERE {where}", params).fetchone()["n"]
    rows = conn.execute(
        f"SELECT {columns} FROM {table} WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s",
        (*params, page_size, (page - 1) * page_size),
    ).fetchall()
    return {"items": [mapper(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@app.get("/api/batches", response_model=schemas.Page[schemas.Batch])
def batches(
    user: User,
    q: str = "",
    status: str = "",
    page: Page = 1,
    page_size: Size = 20,
    sort: Literal["created_at", "name", "payable_total"] = "created_at",
):
    with connect() as conn:
        return paginate(
            conn,
            "batches",
            "(name ILIKE %s OR id::text ILIKE %s) AND (%s='' OR status=%s)",
            (f"%{q}%", f"%{q}%", status, status),
            page,
            page_size,
            {
                "created_at": "created_at DESC,id",
                "name": "name,id",
                "payable_total": "payable_total DESC NULLS LAST,id",
            }[sort],
            mapper=service.batch_view,
        )


async def upload_bytes(file):
    raw = await file.read(service.MAX_UPLOAD + 1)
    await file.close()
    if len(raw) > service.MAX_UPLOAD:
        fail("UPLOAD_SIZE", "The upload limit is 12 MiB.", 413)
    return raw


@app.post("/api/batches", response_model=schemas.Batch)
async def upload_batch(file: UploadFile, user: User, idempotency_key: Key = None):
    raw = await upload_bytes(file)
    with connect() as conn:
        return service.import_batch(conn, user, idempotency_key, file.filename or "legacy.dat", raw)


@app.get("/api/batches/{batch_id}", response_model=schemas.BatchDetail)
def batch_detail(batch_id: uuid.UUID, user: User):
    with connect() as conn:
        batch = service.batch_view(conn.execute("SELECT * FROM batches WHERE id=%s", (batch_id,)).fetchone())
        batch["records"] = [
            service.record_view(r)
            for r in conn.execute("SELECT * FROM records WHERE batch_id=%s ORDER BY position LIMIT 100", (batch_id,))
        ]
        batch["jobs"] = [
            service.job_view(conn, r)
            for r in conn.execute(
                "SELECT * FROM jobs WHERE batch_id=%s ORDER BY created_at DESC", (batch_id,)
            ).fetchall()
        ]
        batch["approval"] = clean(conn.execute("SELECT * FROM approvals WHERE batch_id=%s", (batch_id,)).fetchone())
        return batch


@app.get("/api/batches/{batch_id}/records", response_model=schemas.Page[schemas.Record])
def batch_records(
    batch_id: uuid.UUID,
    user: User,
    q: str = "",
    state: str = "",
    page: Page = 1,
    page_size: Size = 20,
    sort: Literal["position", "reference", "payable"] = "position",
):
    with connect() as conn:
        return paginate(
            conn,
            "records",
            "batch_id=%s AND (reference ILIKE %s OR source ILIKE %s) AND (%s='' OR state=%s)",
            (batch_id, f"%{q}%", f"%{q}%", state, state),
            page,
            page_size,
            {"position": "position", "reference": "reference,position", "payable": "payable DESC NULLS LAST,position"}[
                sort
            ],
            mapper=service.record_view,
        )


@app.post("/api/batches/{batch_id}/approve", response_model=schemas.Batch)
def approve(batch_id: uuid.UUID, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.approve(conn, user, idempotency_key, batch_id)


@app.post("/api/batches/{batch_id}/post", response_model=schemas.Job)
def post(batch_id: uuid.UUID, body: PostRequest, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.post(conn, user, idempotency_key, batch_id, body.failure_mode)


@app.post("/api/batches/{batch_id}/replay", response_model=schemas.Job)
def replay(batch_id: uuid.UUID, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.queue_inspection(conn, user, idempotency_key, batch_id, "replay")


@app.post("/api/batches/{batch_id}/compare", response_model=schemas.Job)
def compare(batch_id: uuid.UUID, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.queue_inspection(conn, user, idempotency_key, batch_id, "compare")


@app.get("/api/jobs/{job_id}", response_model=schemas.Job)
def job_detail(job_id: uuid.UUID, user: User):
    with connect() as conn:
        return service.job_view(conn, conn.execute("SELECT * FROM jobs WHERE id=%s", (job_id,)).fetchone())


@app.post("/api/jobs/{job_id}/retry", response_model=schemas.Job)
def retry(job_id: uuid.UUID, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.retry_job(conn, user, idempotency_key, job_id)


@app.get("/api/jobs/{job_id}/differences")
def differences(job_id: uuid.UUID, user: User, page: Page = 1, page_size: Size = 20):
    with connect() as conn:
        job = conn.execute("SELECT result->>'difference_count' AS total FROM jobs WHERE id=%s", (job_id,)).fetchone()
        if not job:
            fail("JOB_NOT_FOUND", "Job not found.", 404)
        items = conn.execute(
            """SELECT item FROM jobs, jsonb_array_elements(result->'differences') WITH ORDINALITY AS d(item,position)
          WHERE jobs.id=%s ORDER BY position LIMIT %s OFFSET %s""",
            (job_id, page_size, (page - 1) * page_size),
        ).fetchall()
        return {
            "items": [r["item"] for r in items],
            "total": int(job["total"] or 0),
            "page": page,
            "page_size": page_size,
        }


@app.get("/api/records/{record_id}/trace", response_model=schemas.Trace)
def trace(record_id: uuid.UUID, user: User):
    with connect() as conn:
        row = conn.execute("SELECT * FROM records WHERE id=%s", (record_id,)).fetchone()
        if not row:
            fail("RECORD_NOT_FOUND", "Record not found.", 404)
        batch = service.batch_view(conn.execute("SELECT * FROM batches WHERE id=%s", (row["batch_id"],)).fetchone())
        attempts = clean(
            conn.execute(
                "SELECT a.* FROM attempts a JOIN jobs j ON j.id=a.job_id WHERE j.batch_id=%s ORDER BY a.started_at",
                (row["batch_id"],),
            ).fetchall()
        )
        journals = clean(
            conn.execute("SELECT * FROM journals WHERE record_id=%s ORDER BY created_at", (record_id,)).fetchall()
        )
        info = engine.build_info(batch["engine_build"])
        archive = engine_archive(batch["engine_build"]) / "src"
        names = sorted(p.name for p in archive.glob("*.cob"))
        source_name = next(
            (n for n in names if "award" in n.lower() or "calc" in n.lower()), names[0] if names else "award.cob"
        )
        return {
            "record": service.record_view(row),
            "batch": batch,
            "journals": journals,
            "attempts": attempts,
            "engine": info,
            "source_url": f"/api/engine/source/{batch['engine_build']}/{source_name}",
        }


@app.get("/api/ledger", response_model=schemas.Page[schemas.Journal])
def ledger(user: User, q: str = "", kind: str = "", page: Page = 1, page_size: Size = 20):
    with connect() as conn:
        return paginate(
            conn,
            "journals",
            "(reference ILIKE %s OR source ILIKE %s OR id::text ILIKE %s) AND (%s='' OR kind=%s)",
            (f"%{q}%", f"%{q}%", f"%{q}%", kind, kind),
            page,
            page_size,
        )


@app.post("/api/ledger/{journal_id}/reverse", response_model=schemas.Journal)
def reverse(journal_id: uuid.UUID, body: ReasonRequest, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.reverse(conn, user, idempotency_key, journal_id, body.reason)


@app.get("/api/audit/verify")
def audit_verification(user: User):
    with connect() as conn:
        return verify_audit(conn)


@app.get("/api/audit")
def audit_log(user: User, page: Page = 1, page_size: Size = 30):
    with connect() as conn:
        return paginate(conn, "audit", "true", (), page, page_size, "sequence DESC", mapper=service.audit_view)


@app.post("/api/reconciliation")
async def settlement_upload(file: UploadFile, user: User, idempotency_key: Key = None):
    raw = await upload_bytes(file)
    with connect() as conn:
        return service.import_settlement(conn, user, idempotency_key, file.filename or "settlements.csv", raw)


@app.get("/api/reconciliation", response_model=schemas.Page[schemas.Reconciliation])
def reconciliation(user: User, q: str = "", classification: str = "", page: Page = 1, page_size: Size = 20):
    with connect() as conn:
        return paginate(
            conn,
            "reconciliations",
            "(reference ILIKE %s OR coalesce(settlement_reference,'') ILIKE %s) AND (%s='' OR classification=%s)",
            (f"%{q}%", f"%{q}%", classification, classification),
            page,
            page_size,
        )


@app.post("/api/reconciliation/{row_id}/accept", response_model=schemas.Journal)
def accept(row_id: uuid.UUID, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.accept_settlement(conn, user, idempotency_key, row_id)


@app.post("/api/reconciliation/{row_id}/disposition")
def disposition(row_id: uuid.UUID, body: ReasonRequest, user: User, idempotency_key: Key = None):
    with connect() as conn:
        return service.disposition(conn, user, idempotency_key, row_id, body.reason)


@app.get("/api/engine/source/{build}/{name}")
def source(build: str, name: str, user: User):
    if not re.fullmatch(r"[a-f0-9]{12,64}", build) or not re.fullmatch(r"[A-Za-z0-9_-]+\.(cob|cpy)", name):
        fail("SOURCE_NOT_FOUND", "Source is not in the recorded build allowlist.", 404)
    archive = engine_archive(build)
    permitted = {
        p.name: p
        for folder in ("src", "copybooks")
        for p in (archive / folder).glob("*")
        if p.suffix in (".cob", ".cpy") and p.is_file()
    }
    if name not in permitted:
        fail("SOURCE_NOT_FOUND", "Source is not in the recorded build allowlist.", 404)
    source_hash = hashlib.sha256()
    for path in sorted(permitted.values()):
        source_hash.update(path.relative_to(archive).as_posix().encode() + b"\0" + path.read_bytes())
    if source_hash.hexdigest() != engine.build_info(build).get("source_hash"):
        fail("ENGINE_SOURCE_INTEGRITY", "Archived source does not match the recorded build.", 409)
    return PlainTextResponse(permitted[name].read_text(encoding="utf-8"))


@app.get("/api/fixtures/{name}")
def fixture(name: str, user: User):
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.(dat|csv|bin|json)", name):
        fail("FIXTURE_NOT_FOUND", "Fixture not found.", 404)
    path = ROOT / "fixtures" / name
    if not path.is_file():
        fail("FIXTURE_NOT_FOUND", "Fixture not found.", 404)
    return FileResponse(path, filename=name, media_type="application/octet-stream")


@app.get("/api/benchmarks")
def benchmarks(user: User):
    reports = []
    for name in ("benchmarks.json", "benchmark-report.json", "engine-benchmarks.json", "e2e-benchmarks.json"):
        path = ROOT / "artifacts" / name
        if path.exists():
            reports.append(json.loads(path.read_text(encoding="utf-8")))
    return {"reports": reports, "measured": bool(reports)}


@app.get("/api/engine/packed")
def packed_inspector(user: User):
    cases = []
    for path in sorted((ROOT / "fixtures").glob("*.bin")):
        raw = path.read_bytes()
        try:
            decoded = engine.decode_mixed(raw)
            cases.append({"name": path.name, "raw_hex": raw.hex(), "valid": True, "decoded": decoded.decode("ascii")})
        except engine.EngineError as exc:
            cases.append({"name": path.name, "raw_hex": raw.hex(), "valid": False, "error": str(exc)})
    return {
        "format": "BOREAL bounded IBM-037 character fields with signed packed decimal; not general mainframe compatibility",
        "cases": cases,
    }


@app.get("/api/batches/{batch_id}/evidence")
def evidence(batch_id: uuid.UUID, user: User):
    require(user, "auditor")
    files = {}
    with connect() as conn:
        batch = conn.execute("SELECT * FROM batches WHERE id=%s", (batch_id,)).fetchone()
        service.batch_view(batch)
        if not batch["result_digest"]:
            fail("NO_CALCULATION", "A completed calculation is required for financial evidence.", 409)
        # Append under READ COMMITTED so the advisory lock sees the latest head.
        # Never append from a repeatable-read snapshot that may predate another writer.
        audit(conn, user["id"], "evidence.requested", batch_id)
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        batch = conn.execute("SELECT * FROM batches WHERE id=%s", (batch_id,)).fetchone()
        records = [
            r["data"] for r in conn.execute("SELECT data FROM records WHERE batch_id=%s ORDER BY position", (batch_id,))
        ]
        journals = conn.execute(
            "SELECT * FROM journals WHERE batch_id=%s ORDER BY source,reference,kind", (batch_id,)
        ).fetchall()
        exceptions = conn.execute(
            "SELECT * FROM reconciliations WHERE record_id IN (SELECT id FROM records WHERE batch_id=%s) ORDER BY created_at,position",
            (batch_id,),
        ).fetchall()
        settlements = conn.execute(
            "SELECT DISTINCT s.* FROM settlement_imports s JOIN reconciliations r ON r.import_id=s.id JOIN records d ON d.id=r.record_id WHERE d.batch_id=%s",
            (batch_id,),
        ).fetchall()
        files["input/original.dat"] = bytes(batch["raw"])
        for item in settlements:
            files[f"input/settlement-{item['id']}.csv"] = bytes(item["raw"])
        documents = {
            "batch.json": service.batch_view(batch),
            "calculation.json": financial_records(records),
            "reference-snapshot.json": batch["reference_snapshot"],
            "journals.json": journals,
            "exceptions.json": exceptions,
            "approval.json": conn.execute("SELECT * FROM approvals WHERE batch_id=%s", (batch_id,)).fetchone(),
            "jobs.json": conn.execute(
                "SELECT * FROM jobs WHERE batch_id=%s ORDER BY created_at", (batch_id,)
            ).fetchall(),
            "receipts.json": conn.execute(
                "SELECT r.* FROM receipts r JOIN jobs j ON j.id=r.job_id WHERE j.batch_id=%s ORDER BY r.chunk",
                (batch_id,),
            ).fetchall(),
            "audit.json": conn.execute("SELECT * FROM audit ORDER BY sequence").fetchall(),
            "audit-verification.json": verify_audit(conn),
            "engine-build.json": engine.build_info(batch["engine_build"]),
        }
        for name, value in documents.items():
            files[name] = canonical(value).encode("utf-8")
    archive = engine_archive(batch["engine_build"])
    if archive.is_dir():
        for path in archive.rglob("*"):
            if path.is_file():
                relative = str(path.relative_to(archive)).replace("\\", "/")
                files[f"engine/{batch['engine_build']}/" + relative] = path.read_bytes()
                if relative.startswith(("src/", "copybooks/")):
                    files["repository/engine/" + relative] = path.read_bytes()
    for relative in (
        "CONTRACT.md",
        "docs/RECORDS.md",
        "docs/ARCHITECTURE.md",
        "docs/SECURITY.md",
        "docs/MAINFRAME.md",
        "docs/REFERENCES.md",
        "docs/VERIFICATION.md",
        "docs/REPORT.fr-CA.md",
        "README.md",
        "DEMO.md",
        "scripts/verify_evidence.py",
        "engine/build.py",
        "engine/build.sh",
        "engine/cli.py",
        "engine/limit_exec.py",
        "engine/replay_evidence.py",
        "backend/boreal/engine.py",
        "backend/boreal/__init__.py",
        "fixtures/generate.py",
    ):
        path = ROOT / relative
        if path.exists():
            files["repository/" + relative] = path.read_bytes()
    for name in (
        "tests.xml",
        "backend-tests.xml",
        "backend-evidence-tests.xml",
        "backend-recovery-tests.xml",
        "backend-retry-test.xml",
        "test-report.json",
        "benchmarks.json",
        "benchmark-report.json",
        "benchmark-initial-failure.json",
        "engine-benchmarks.json",
        "e2e-benchmarks.json",
        "backup-restore.json",
        "accessibility.json",
        "browser-quality.json",
        "browser-reflow.json",
        "browser-workflow.json",
        "browser-workflow-fr-CA-dark.json",
        "verification.json",
        "python-audit.json",
        "npm-audit.json",
    ):
        path = ROOT / "artifacts" / name
        if path.exists():
            files["reports/" + name] = path.read_bytes()
    if (ROOT / "engine/test-results.xml").is_file():
        files["reports/engine-tests.xml"] = (ROOT / "engine/test-results.xml").read_bytes()
    manifest = {
        "schema": "boreal-evidence-v1",
        "batch_id": str(batch_id),
        "engine_build": batch["engine_build"],
        "policy": batch["policy"],
        "input_sha256": batch["source_sha256"],
        "financial_result_digest": batch["result_digest"],
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
        "schema_version": batch["schema_version"],
        "reproduce": [
            "Install Python 3.12 and GnuCOBOL 3.2 including its runtime; extract this ZIP.",
            "python repository/scripts/verify_evidence.py <evidence.zip>",
            "python repository/engine/replay_evidence.py .",
            "cd repository && python engine/build.py",
            f"From repository/: chmod +x ../engine/{batch['engine_build']}/batch ../engine/{batch['engine_build']}/envelope ../engine/{batch['engine_build']}/reconcile ../engine/{batch['engine_build']}/packed ../engine/{batch['engine_build']}/aggregate ../engine/{batch['engine_build']}/reverse",
            f"From repository/: BOREAL_ENGINE_BUILDS=../engine PYTHONPATH=backend python engine/cli.py {'mixed' if batch['schema_version'] == 'BOREAL-MIXED01' else 'calculate'} ../input/original.dat --policy {batch['policy']} --build {batch['engine_build']}",
            "The retained Linux executable requires a compatible Linux x86_64 libc/libcob runtime. Rebuilding from the included COBOL source produces a new recorded build when compiler identity differs.",
            "The full application checkout and startup commands are described in repository/README.md.",
        ],
        "scope": "Synthetic CAD demonstration; no real payments or official affiliation.",
    }
    files["manifest.json"] = canonical(manifest).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in files.items():
            bundle.writestr(name, raw)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="boreal-{batch_id}-evidence.zip"'},
    )


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if path.startswith("api/"):
        fail("NOT_FOUND", "Endpoint not found.", 404)
    dist = (ROOT / "frontend" / "dist").resolve()
    requested = (dist / path).resolve()
    if requested.is_relative_to(dist) and requested.is_file():
        return FileResponse(requested)
    if (dist / "index.html").is_file():
        return FileResponse(dist / "index.html")
    return PlainTextResponse(
        "BOREAL frontend build is not available. Run npm ci && npm run build in frontend/.", status_code=503
    )
