import os, shutil, subprocess, tempfile, glob
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

AUDIVERIS_JAR = "/opt/audiveris/audiveris.jar"

app = FastAPI()

@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
        raise HTTPException(400, "Format supporté: pdf/png/jpg/tiff")

    with tempfile.TemporaryDirectory() as work:
        in_path = os.path.join(work, "input" + suffix)
        out_dir = os.path.join(work, "out")
        os.makedirs(out_dir, exist_ok=True)

        # Save upload
        with open(in_path, "wb") as f:
            f.write(await file.read())

        # Run Audiveris CLI
        # Exemple d’usage avec -output vu dans la communauté Audiveris. :contentReference[oaicite:4]{index=4}
        cmd = [
            "java",
            "-Xms64m", "-Xmx420m",   # limite mémoire pour essayer de tenir en Free
            "-jar", AUDIVERIS_JAR,
            "-batch",
            "-export",
            "-output", out_dir,
            in_path
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise HTTPException(500, f"Audiveris a échoué: {e}")

        # Audiveris crée souvent un sous-dossier basé sur le nom du fichier
        candidates = glob.glob(out_dir + "/**/*.mxl", recursive=True) + glob.glob(out_dir + "/**/*.xml", recursive=True)
        if not candidates:
            raise HTTPException(500, "Aucun MusicXML/MXL généré (OMR a peut-être échoué).")

        # Prend le premier résultat
        result_path = candidates[0]
        return FileResponse(result_path, filename=os.path.basename(result_path))
