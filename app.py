import os
import uuid
import glob
import subprocess
import tempfile
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

AUDIVERIS_CMD = os.getenv("AUDIVERIS_CMD", "/opt/audiveris/run-audiveris.sh")

app = FastAPI()

@app.get("/")
def health():
    return {"ok": True}

@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())[:8]

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "request_id": request_id, "message": "Formats: pdf/png/jpg/tiff"}
        )

    with tempfile.TemporaryDirectory() as work:
        in_path = os.path.join(work, "input" + ext)
        out_dir = os.path.join(work, "out")
        os.makedirs(out_dir, exist_ok=True)

        with open(in_path, "wb") as f:
            f.write(await file.read())

        print(f"[{request_id}] Starting Audiveris on {file.filename} (saved to {in_path})")

        # Appel du wrapper (launcher-first + fallback classpath)
        cmd = [
            AUDIVERIS_CMD,
            "-batch",
            "-export",
            "-output", out_dir,
            in_path
        ]

        # Limite mémoire (Render free)
        env = os.environ.copy()
        env.setdefault("JAVA_TOOL_OPTIONS", "-Xms64m -Xmx420m")

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        print(f"[{request_id}] Audiveris finished rc={proc.returncode}")

        if proc.returncode != 0:
            tail = (proc.stdout or "")[-4000:]
            print(f"[{request_id}] ERROR: Audiveris failed (rc={proc.returncode})")
            print(f"[{request_id}] === AUDIVERIS OUTPUT (FULL) ===\n{proc.stdout}")

            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "request_id": request_id,
                    "returncode": proc.returncode,
                    "message": "Audiveris failed",
                    "log_tail": tail,
                },
            )

        candidates = (
            glob.glob(out_dir + "/**/*.mxl", recursive=True)
            + glob.glob(out_dir + "/**/*.musicxml", recursive=True)
            + glob.glob(out_dir + "/**/*.xml", recursive=True)
        )

        if not candidates:
            tail = (proc.stdout or "")[-4000:]
            print(f"[{request_id}] ERROR: No output generated")
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "request_id": request_id,
                    "returncode": proc.returncode,
                    "message": "No MusicXML/MXL generated",
                    "log_tail": tail,
                },
            )

        result_path = candidates[0]
        print(f"[{request_id}] Success output: {result_path}")

        return FileResponse(result_path, filename=os.path.basename(result_path))
