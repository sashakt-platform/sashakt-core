from fastapi import FastAPI

from app.routers import organization
from app.routers.location import location

app = FastAPI()

app.include_router(location.router)
app.include_router(organization.router)


@app.get("/")
def read_root():
    return {"Sashakt": "Platform"}
