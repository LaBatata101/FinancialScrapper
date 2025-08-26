import logging

from fastapi import FastAPI

from app.api.endpoints import router as api_router

logging.basicConfig(format="%(levelname)s [%(asctime)s] [%(name)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


app = FastAPI(
    title="Financial AUM Scraping System",
    version="1.0.0",
)

app.include_router(api_router, prefix="/api/v1")
