from fastapi import FastAPI, APIRouter
from app.routers.location import location
from app.routers import organization

app = FastAPI()

app.include_router(location.router)
app.include_router(organization.router)


@app.get("/")
def read_root():
    return {"Sashakt": "Platform"}
