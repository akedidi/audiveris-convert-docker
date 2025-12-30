import os
import glob
import uuid
import shutil
import subprocess
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

AUDIVERIS_JAR = os.getenv("AUDIVERIS_JAR", "/opt/audiveris/audiveris.jar")

# Ajuste selon Render (Free: 512MB). Tu peux baisser à 320m si OOM.
JAVA_XMS = os.getenv("JAVA_XMS", "64m")
JAVA_XMX = os.getenv("JAVA_XMX", "420m")

# Limite de logs renvoyés au client (les logs complets restent dans Render via print)
LOG_TAIL_CHARS = int(os.getenv("LOG_TAIL_CHARS", "8000"))

# Extensions supportées
ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

app = FastAPI(title="Audiveris OMR Service", version="1.0.0")


@app.get("/")
def health():
    return {
        "ok": True,
        "audiveris_jar_exists": os.path.exists(AUDIVERIS_JAR),
        "java_xms": JAVA_XMS,
        "java_xmx": JAVA_XMX,
    }


def _run_audiveris(input_path: str, out_dir: str) -> tuple[int, str]:
    """
    Lance Audiveris en mode batch et renvoie (returncode, combined_output).
    """
    cmd = [
        "java",
        f"-Xms{JAVA_XMS}",
        f"-Xmx{JAVA_XMX}",
        "-jar",
        AUDIVERIS_JAR,
        "-batch",
        "-export",
        "-output",
        out_dir,
        input_path,
    ]

    # Important: capture stdout+stderr pour debug
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout or ""


def _find_outputs(out_dir: str) -> list[str]:
    """
    Cherche les sorties générées par Audiveris.
    Priorité: .mxl puis .musicxml puis .xml
    """
    mxl = glob.glob(os.path.join(out_dir, "**", "*.mxl"), recursive=True)
    musicxml = glob.glob(os.path.join(out_dir, "**", "*.musicxml"), recursive=True)
    xml = glob.glob(os.path.join(out_dir, "**", "*.xml"), recursive=True)

    # Filtrer les fichiers non pertinents si besoin
    # (garde tout pour l’instant)
    return mxl + musicxml + xml


def _tail(s: str, n: int) -> str:
    if not s:
        return ""
    return s[-n:] if len(s) > n else s


def _error_response(message: str, returncode: int, logs: str, request_id: str, http_code: int = 500):
    # Log complet côté Render
    print(f"[{request_id}] ERROR: {message} (rc={returncode})")
    print(f"[{request_id}] === AUDIVERIS OUTPUT (FULL) ===")
    print(logs)

    return JSONResponse(
        status_code=http_code,
        content={
            "ok": False,
            "request_id": request_id,
            "returncode": returncode,
            "message": message,
            "log_tail": _tail(logs, LOG_TAIL_CHARS),
        },
    )


async def _save_upload_to_temp(file: UploadFile, dst_path: str):
    """
    Sauvegarde le fichier uploadé sur disque.
    """
    # lecture en mémoire -> ok pour fichiers modestes, sinon stream (mais suffisant MVP)
    data = await file.read()
    with open(dst_path, "wb") as f:
        f.write(data)


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    prefer: str = Query("mxl", description="Format préféré: mxl|musicxml|xml"),
):
    """
    Convertit un PDF/image en MusicXML/MXL.
    - Succès: renvoie directement le fichier (binary)
    - Échec: JSON avec logs (tail)
    """
    request_id = str(uuid.uuid4())[:8]

    if not os.path.exists(AUDIVERIS_JAR):
        raise HTTPException(500, f"Audiveris jar not found at {AUDIVERIS_JAR}")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Formats supportés: {', '.join(sorted(ALLOWED_EXTS))}")

    with tempfile.TemporaryDirectory() as work:
        in_path = os.path.join(work, "input" + ext)
        out_dir = os.path.join(work, "out")
        os.makedirs(out_dir, exist_ok=True)

        await _save_upload_to_temp(file, in_path)

        print(f"[{request_id}] Starting Audiveris on {file.filename} (saved to {in_path})")
        rc, logs = _run_audiveris(in_path, out_dir)
        print(f"[{request_id}] Audiveris finished rc={rc}")

        if rc != 0:
            return _error_response("Audiveris failed", rc, logs, request_id, http_code=500)

        outputs = _find_outputs(out_dir)
        if not outputs:
            return _error_response("No MusicXML output generated", rc, logs, request_id, http_code=500)

        # Choisir la sortie selon prefer
        prefer = (prefer or "mxl").lower().strip()
        chosen: Optional[str] = None

        if prefer == "mxl":
            for p in outputs:
                if p.lower().endswith(".mxl"):
                    chosen = p
                    break
        elif prefer == "musicxml":
            for p in outputs:
                if p.lower().endswith(".musicxml"):
                    chosen = p
                    break
        elif prefer == "xml":
            for p in outputs:
                if p.lower().endswith(".xml"):
                    chosen = p
                    break

        # Fallback: premier fichier trouvé
        if not chosen:
            chosen = outputs[0]

        filename = os.path.basename(chosen)
        print(f"[{request_id}] Returning output: {chosen}")

        return FileResponse(
            chosen,
            filename=filename,
            media_type="application/octet-stream",
        )


@app.post("/convert-debug")
async def convert_debug(file: UploadFile = File(...)):
    """
    Variante debug: renvoie toujours JSON:
    - rc, nb outputs, liste outputs, tail logs
    """
    request_id = str(uuid.uuid4())[:8]

    if not os.path.exists(AUDIVERIS_JAR):
        raise HTTPException(500, f"Audiveris jar not found at {AUDIVERIS_JAR}")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Formats supportés: {', '.join(sorted(ALLOWED_EXTS))}")

    with tempfile.TemporaryDirectory() as work:
        in_path = os.path.join(work, "input" + ext)
        out_dir = os.path.join(work, "out")
        os.makedirs(out_dir, exist_ok=True)

        await _save_upload_to_temp(file, in_path)

        print(f"[{request_id}] DEBUG Starting Audiveris on {file.filename}")
        rc, logs = _run_audiveris(in_path, out_dir)
        outputs = _find_outputs(out_dir)

        # log complet dans Render
        print(f"[{request_id}] DEBUG rc={rc}, outputs={len(outputs)}")
        print(f"[{request_id}] === AUDIVERIS OUTPUT (FULL) ===")
        print(logs)

        return {
            "ok": rc == 0 and len(outputs) > 0,
            "request_id": request_id,
            "returncode": rc,
            "outputs_count": len(outputs),
            "outputs": [os.path.relpath(p, out_dir) for p in outputs],
            "log_tail": _tail(logs, LOG_TAIL_CHARS),
        }
