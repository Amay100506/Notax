from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api.routes import router
from backend.api.shopping_routes import router as shopping_router
from backend.database.connection import init_db
from backend.utils.configuration import settings
from backend.utils.logging_config import logger

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "backend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database schema is initialized
    logger.info("NotifyIQ API starting on %s:%d", settings.host, settings.port)
    init_db()
    yield
    logger.info("NotifyIQ API shutting down.")


app = FastAPI(
    title="NotifyIQ API & Mobile Gateway",
    description="Privacy-First, Explainable AI System for Android Notification Prioritization",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow CORS for local and LAN mobile requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for PWA manifests and icons
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Mobile PWA Application Entry Route
@app.get("/mobile", include_in_schema=False)
async def serve_mobile_pwa():
    """Serves the installable mobile PWA companion."""
    mobile_index = STATIC_DIR / "mobile" / "index.html"
    return FileResponse(str(mobile_index))


app.include_router(router, prefix="/api/v1")
app.include_router(router)  # Also mount at root for /health, /notifications etc.
app.include_router(shopping_router, prefix="/api/v1")
app.include_router(shopping_router)


if __name__ == "__main__":
    import uvicorn
    # Bind to 0.0.0.0 so mobile phones on the same Wi-Fi network can connect
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=False,
    )
