import os, subprocess, tempfile, glob
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

AUDIVERIS_JAR = "/opt/audiveris/audiveris.jar"

app = FastAPI()

@app.get("/")
def health():
    return {"ok": True}

@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
        raise HTTPException(400, "Formats: pdf/png/jpg/tiff")

    with tempfile.TemporaryDirectory() as work:
        in_path = os.path.join(work, "input" + ext)
        out_dir = os.path.join(work, "out")
        os.makedirs(out_dir, exist_ok=True)

        with open(in_path, "wb") as f:
            f.write(await file.read())

        # Limiter la RAM Java (Render free peut être serré)
        cmd = [
            "java", "-Xms64m", "-Xmx420m",
            "-jar", AUDIVERIS_JAR,
            "-batch",
            "-export",
            "-output", out_dir,
            in_path
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise HTTPException(500, f"Audiveris failed: {e}")

        candidates = (
            glob.glob(out_dir + "/**/*.mxl", recursive=True)
            + glob.glob(out_dir + "/**/*.musicxml", recursive=True)
            + glob.glob(out_dir + "/**/*.xml", recursive=True)
        )
        if not candidates:
            raise HTTPException(500, "Aucun MusicXML/MXL généré (OMR a échoué ou partition trop complexe).")

        result = candidates[0]
        return FileResponse(result, filename=os.path.basename(result))
