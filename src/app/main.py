import logging
import time
from contextlib import asynccontextmanager

import uvicorn  # Import uvicorn for local running checks
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.app.core.config import settings
from src.app.lib.supabase_client import get_supabase_admin_client
from src.app.routers import analyze

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

description = """
BoligAnalyse API helps you analyze real estate listings using AI. 🚀

You can submit URLs for analysis and retrieve the results.
"""

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=description,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENVIRONMENT != "production" else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for now, tighten in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Logging / Timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"  # Use f-string

    log_details = {
        "method": request.method,
        "path": request.url.path,
        "query_params": str(request.query_params),
        "client_host": request.client.host if request.client else "unknown",
        "status_code": response.status_code,
        "process_time_ms": round(process_time * 1000, 2)
    }

    # Use structured logging if available, otherwise format nicely
    logger.info(f"Request processed: {log_details}")
    return response


# --- Exception Handlers ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log the detailed validation errors
    logger.warning(f"Validation error for {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        # Return a user-friendly message and optionally the detailed errors
        content={"detail": "Validation Error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for {request.method} {request.url.path}", exc_info=True)  # Log traceback
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Code to run on startup
    logger.info("Application startup...")
    # Initialize Supabase client here if needed, although get_supabase_admin_client handles it lazily
    await get_supabase_admin_client()
    yield
    logger.info("Shutdown complete.")


# Assign the lifespan context manager to the app instance
app.router.lifespan_context = lifespan

app.include_router(analyze.router, prefix=settings.API_V1_STR, tags=["Analysis"])


@app.get("/", tags=["Root"])
async def read_root():
    """ Basic health check endpoint. """
    return {"status": "ok", "message": f"Welcome to the {settings.PROJECT_NAME}!"}


if __name__ == "__main__":
    print(f"Starting Uvicorn server for local development on http://127.0.0.1:8000")
    print(f"Using Supabase URL: {settings.SUPABASE_URL[:20]}...")  # Don't log full URL always
    # Check if keys are loaded (basic check)
    if not settings.SUPABASE_SERVICE_ROLE_KEY or "YOUR_DEFAULT" in settings.SUPABASE_SERVICE_ROLE_KEY:
        print("\n*** WARNING: Supabase Service Role Key seems unconfigured! Check .env file. ***\n")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="debug"
    )
