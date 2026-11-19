import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import init_db, get_db
from .data.import_aliments import importer
from fastapi.responses import RedirectResponse
from .routers import plans, generate

app = FastAPI(title='NutriFit AI')
init_db()
with get_db() as con:
    vide = con.execute("SELECT COUNT(*) FROM aliments").fetchone()[0] == 0
if vide: importer()

@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/app/")

app.include_router(plans.router)
app.include_router(generate.router)


@app.get('/health')
def health():
    return {'status': 'ok', 'mode': os.getenv('NUTRIFIT_MODE', 'demo')}


FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'
app.mount('/app', StaticFiles(directory=FRONTEND, html=True), name='frontend')
