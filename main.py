import shutil
from fastapi import FastAPI, File, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from database import connect_db
from apps.configs.routes import configs
from apps.assets.routes import assets
from apps.incidents.routes import incidents
from apps.settings.routes import settings
from apps.events.routes import events
import psycopg2

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(configs,    prefix="/configs",    tags=["Configs"])
app.include_router(assets,     prefix="/assets",     tags=["Assets"])
app.include_router(incidents,  prefix="/incidents",  tags=["Incidents"])
app.include_router(settings,   prefix="/settings",   tags=["Settings"])
app.include_router(events,     prefix="",            tags=["Events", "Logs"])


@app.get("/")
def read_root():
    return {"data": "Welcome to Indygen!"}


# Endpoint which accepts a file and stores in the server
@app.post("/share_file/")
async def create_upload_file(
    file: UploadFile = File(...),
):
    with open(f"shared/{file.filename}", "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"data": "File uploaded successfully"}


@app.get("/health")
async def health_check(db: psycopg2.extensions.connection = Depends(connect_db)):
    try: 
        with db.cursor() as cur:
            cur.execute("SELECT 1")
        db.close()
        return {"status": "ok"}
    except:
        raise Exception("Service is unhealthy")
