import os
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

NAS_ROOT = Path(os.getenv("NAS_ROOT", "/mnt/nas"))
UPLOAD_ROOT = NAS_ROOT / "images"
PUBLISH_LINK = Path(os.getenv("PUBLISH_LINK", "/srv/osshare/install.wim"))
CAPTURE_ROOT = Path(os.getenv("CAPTURE_ROOT", "/srv/osshare/captured"))

IMPORT_JOBS: dict[str, dict] = {}
IMPORT_JOBS_LOCK = threading.Lock()

APP_TAG = os.getenv("APP_TAG", "LaszloK")

app = FastAPI(title=f"{APP_TAG} OS Image Publisher", version="0.9.0")
templates = Jinja2Templates(directory="templates")


def list_wim_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.wim"))


def list_cached_wim_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.glob("*.wim"))


def current_target() -> Optional[Path]:
    try:
        if PUBLISH_LINK.is_symlink():
            return PUBLISH_LINK.resolve()
        if PUBLISH_LINK.exists():
            return PUBLISH_LINK.resolve()
    except Exception:
        return None
    return None


def build_image_name(
    vendor: str,
    product_family: str,
    platform: str,
    windows_edition: str,
    release: str,
    build: str,
    is_licensed: bool = False,
    no_update: bool = False,
    customer_name: str = "",
) -> str:
    parts = []

    for value in [vendor, product_family, platform, windows_edition, release, build]:
        value = value.strip()
        if value:
            parts.append(value)

    if is_licensed:
        parts.append("L")

    if no_update:
        parts.append("NoUpdate")

    customer_name = customer_name.strip()
    if customer_name:
        parts.append(customer_name)

    return "_".join(parts)


def parse_image_name(filename_stem: str) -> dict:
    parts = filename_stem.split("_")
    result = {
        "vendor": "",
        "product_family": "",
        "platform": "",
        "windows_edition": "",
        "release": "",
        "build": "",
        "licensed": False,
        "no_update": False,
        "customer": "",
    }

    if len(parts) < 7:
        if parts:
            result["vendor"] = parts[0]
        return result

    result["vendor"] = parts[0]
    result["product_family"] = parts[1]
    result["platform"] = parts[2]
    result["windows_edition"] = "_".join(parts[3:5])
    result["release"] = parts[5]
    result["build"] = parts[6]

    rest = parts[7:]
    customer_tokens = []

    for token in rest:
        if token == "L":
            result["licensed"] = True
        elif token == "NoUpdate":
            result["no_update"] = True
        else:
            customer_tokens.append(token)

    result["customer"] = "_".join(customer_tokens)
    return result


def stream_upload_to_file(upload_file: UploadFile, target_file: Path, chunk_size: int = 8 * 1024 * 1024) -> None:
    tmp_file = target_file.with_suffix(target_file.suffix + ".part")
    try:
        with tmp_file.open("wb") as file_obj:
            while True:
                chunk = upload_file.file.read(chunk_size)
                if not chunk:
                    break
                file_obj.write(chunk)
        os.replace(tmp_file, target_file)
    finally:
        try:
            upload_file.file.close()
        except Exception:
            pass
        if tmp_file.exists() and not target_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass


def ensure_inside(root: Path, candidate: Path) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except Exception:
        raise HTTPException(status_code=400, detail=f"Path is outside allowed root: {candidate}")


def set_job(job_id: str, **kwargs) -> None:
    with IMPORT_JOBS_LOCK:
        job = IMPORT_JOBS.setdefault(job_id, {})
        job.update(kwargs)


def copy_cached_to_nas(job_id: str, source: Path, target: Path, chunk_size: int = 32 * 1024 * 1024) -> None:
    tmp_target = target.with_suffix(target.suffix + ".part")
    try:
        total_bytes = source.stat().st_size
        set_job(
            job_id,
            status="running",
            copied_bytes=0,
            total_bytes=total_bytes,
            percent=0,
            source=str(source),
            target=str(target),
            source_removed=False,
        )

        target.parent.mkdir(parents=True, exist_ok=True)

        with source.open("rb") as src, tmp_target.open("wb") as dst:
            copied = 0
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                percent = int((copied / total_bytes) * 100) if total_bytes else 100
                set_job(job_id, copied_bytes=copied, percent=percent)

        os.replace(tmp_target, target)
        source.unlink()

        set_job(
            job_id,
            status="completed",
            copied_bytes=total_bytes,
            total_bytes=total_bytes,
            percent=100,
            source_removed=not source.exists(),
        )
    except Exception as exc:
        try:
            if tmp_target.exists():
                tmp_target.unlink()
        except Exception:
            pass
        set_job(job_id, status="failed", error=str(exc))


@app.on_event("startup")
def startup() -> None:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    PUBLISH_LINK.parent.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    images = list_wim_files(NAS_ROOT)
    cached_images = list_cached_wim_files(CAPTURE_ROOT)
    current = current_target()

    rows = []
    for img in images:
        parsed = parse_image_name(img.stem)
        rows.append(
            {
                "full_path": str(img),
                "name": img.name,
                "published": current is not None and img.resolve() == current,
                **parsed,
            }
        )

    cache_rows = []
    for img in cached_images:
        cache_rows.append(
            {
                "full_path": str(img),
                "name": img.name,
                "size_mb": round(img.stat().st_size / (1024 * 1024), 1),
            }
        )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "images": rows,
            "cached_images": cache_rows,
            "nas_root": str(NAS_ROOT),
            "upload_root": str(UPLOAD_ROOT),
            "capture_root": str(CAPTURE_ROOT),
            "publish_link": str(PUBLISH_LINK),
            "current_target": str(current) if current else None,
            "app_tag": APP_TAG,
        },
    )


@app.post("/publish")
def publish_image(image_path: str = Form(...)) -> RedirectResponse:
    candidate = Path(image_path)

    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {candidate}")
    if not candidate.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {candidate}")
    if candidate.suffix.lower() != ".wim":
        raise HTTPException(status_code=400, detail="Only .wim files can be published")

    ensure_inside(NAS_ROOT, candidate)

    PUBLISH_LINK.parent.mkdir(parents=True, exist_ok=True)

    tmp_link = PUBLISH_LINK.with_suffix(".wim.tmp")
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    tmp_link.symlink_to(candidate)
    os.replace(tmp_link, PUBLISH_LINK)

    return RedirectResponse(url="/", status_code=303)


@app.post("/unpublish")
def unpublish() -> RedirectResponse:
    if PUBLISH_LINK.exists() or PUBLISH_LINK.is_symlink():
        PUBLISH_LINK.unlink()
    return RedirectResponse(url="/", status_code=303)


@app.post("/upload")
def upload_image(
    request: Request,
    upload_file: UploadFile = File(...),
    vendor: str = Form(...),
    product_family: str = Form(...),
    platform: str = Form(...),
    windows_edition: str = Form(...),
    release: str = Form(...),
    build: str = Form(...),
    is_licensed: Optional[str] = Form(default=None),
    no_update: Optional[str] = Form(default=None),
    customer_name: str = Form(default=""),
):
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    ext = Path(upload_file.filename).suffix.lower()
    if ext != ".wim":
        raise HTTPException(status_code=400, detail="Only .wim files are supported")

    image_name = build_image_name(
        vendor=vendor,
        product_family=product_family,
        platform=platform,
        windows_edition=windows_edition,
        release=release,
        build=build,
        is_licensed=bool(is_licensed),
        no_update=bool(no_update),
        customer_name=customer_name,
    )

    if not image_name.strip():
        raise HTTPException(status_code=400, detail="Generated image name is empty")

    target_dir = UPLOAD_ROOT / image_name
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / f"{image_name}.wim"
    stream_upload_to_file(upload_file, target_file)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse(
            {
                "ok": True,
                "image_name": image_name,
                "target_file": str(target_file),
            }
        )

    return RedirectResponse(url="/", status_code=303)


@app.post("/import-capture-start")
def import_capture_start(
    source_file: str = Form(...),
    vendor: str = Form(...),
    product_family: str = Form(...),
    platform: str = Form(...),
    windows_edition: str = Form(...),
    release: str = Form(...),
    build: str = Form(...),
    is_licensed: Optional[str] = Form(default=None),
    no_update: Optional[str] = Form(default=None),
    customer_name: str = Form(default=""),
):
    source = Path(source_file)

    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Cached file not found: {source}")
    if not source.is_file():
        raise HTTPException(status_code=400, detail=f"Cached path is not a file: {source}")
    if source.suffix.lower() != ".wim":
        raise HTTPException(status_code=400, detail="Only .wim files can be imported")

    ensure_inside(CAPTURE_ROOT, source)

    image_name = build_image_name(
        vendor=vendor,
        product_family=product_family,
        platform=platform,
        windows_edition=windows_edition,
        release=release,
        build=build,
        is_licensed=bool(is_licensed),
        no_update=bool(no_update),
        customer_name=customer_name,
    )

    if not image_name.strip():
        raise HTTPException(status_code=400, detail="Generated image name is empty")

    target_dir = UPLOAD_ROOT / image_name
    target_file = target_dir / f"{image_name}.wim"

    if target_file.exists() or target_file.with_suffix(target_file.suffix + ".part").exists():
        raise HTTPException(status_code=400, detail=f"Target already exists or is in progress: {target_file}")

    job_id = uuid.uuid4().hex
    set_job(
        job_id,
        status="queued",
        copied_bytes=0,
        total_bytes=source.stat().st_size,
        percent=0,
        source=str(source),
        target=str(target_file),
        source_removed=False,
        image_name=image_name,
        created_at=time.time(),
    )

    thread = threading.Thread(target=copy_cached_to_nas, args=(job_id, source, target_file), daemon=True)
    thread.start()

    return JSONResponse(
        {
            "ok": True,
            "job_id": job_id,
            "image_name": image_name,
            "target_file": str(target_file),
        }
    )


@app.get("/import-capture-status/{job_id}")
def import_capture_status(job_id: str) -> JSONResponse:
    with IMPORT_JOBS_LOCK:
        job = IMPORT_JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(job)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "nas_root": str(NAS_ROOT),
        "upload_root": str(UPLOAD_ROOT),
        "capture_root": str(CAPTURE_ROOT),
        "publish_link": str(PUBLISH_LINK),
        "current_target": str(current_target()) if current_target() else None,
        "image_count": len(list_wim_files(NAS_ROOT)),
        "cached_count": len(list_cached_wim_files(CAPTURE_ROOT)),
    }
