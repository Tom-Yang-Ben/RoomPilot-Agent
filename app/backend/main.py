"""FastAPI server: list / parse bundled DXF plans, or parse an uploaded one.

Run:  uvicorn main:app --reload --port 8000   (from app/backend/)
The Vite dev server proxies /api here, so no CORS config is needed in dev;
CORS is left open anyway so the built frontend can be served from anywhere.
"""
import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dxf_parser import parse_dxf_file, parse_dxf_bytes, list_plans

PIC_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "pic", "temp"))

app = FastAPI(title="Room 3D")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/plans")
def plans():
    return {"plans": list_plans(PIC_DIR)}


@app.get("/api/plan")
def plan(name: str,
         scale_m: float | None = Query(None, gt=0, le=500),
         thickness: float = Query(0.08, gt=0, le=2),
         height: float = Query(2.7, gt=0, le=10)):
    path = os.path.join(PIC_DIR, os.path.basename(name))  # basename: no traversal
    if not os.path.isfile(path):
        raise HTTPException(404, f"plan not found: {name}")
    try:
        return parse_dxf_file(path, scale_m, thickness, height)
    except Exception as e:
        raise HTTPException(422, f"parse failed: {e}")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...),
                 scale_m: float | None = Query(None, gt=0, le=500),
                 thickness: float = Query(0.08, gt=0, le=2),
                 height: float = Query(2.7, gt=0, le=10)):
    data = await file.read()
    try:
        return parse_dxf_bytes(data, file.filename or "upload.dxf", scale_m, thickness, height)
    except Exception as e:
        raise HTTPException(422, f"parse failed: {e}")
