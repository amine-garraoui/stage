from pathlib import Path
import logging
import os
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from core import anomalies, kpi
from core.config import load_config, resolve_path, setup_logging
from core.exceptions import KpiError
from core.service import load_dataset_cached
from core.audit import get_audit_logger
from reports.excel import export_month_excel
from reports.pdf import export_month_pdf


setup_logging()
config = load_config()
app = FastAPI(title=config.api_title, version="1.0.0")
logger = logging.getLogger(__name__)
audit = get_audit_logger()

# SECURITY: Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_list(
        "CORS_ORIGINS", "http://localhost:8501,http://localhost:3000"
    ),
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_env_list("ALLOWED_HOSTS", "localhost,127.0.0.1"),
)

security = HTTPBearer(auto_error=False)
VALID_API_KEYS = frozenset(_env_list("API_KEYS", ""))


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Validate the configured local API key."""
    if not credentials:
        logger.warning("Unauthorized API key attempt")
        audit.log_auth_attempt(user="unknown", success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.credentials not in VALID_API_KEYS:
        logger.warning("Unauthorized API key attempt")
        audit.log_auth_attempt(user=credentials.credentials[:8] + "...", success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Log successful authentication
    audit.log_auth_attempt(user=credentials.credentials[:8] + "...", success=True)
    return credentials.credentials


def validate_month_format(mois: str) -> str:
    """Validate month parameter format (YYYY-MM)."""
    if not re.match(r"^\d{4}-\d{2}$", mois):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid month format. Use YYYY-MM",
        )
    try:
        datetime.strptime(mois, "%Y-%m")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date",
        )
    return mois


# SECURITY: Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# SECURITY: Set request size limits
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@app.middleware("http")
async def check_request_size(request: Request, call_next):
    if request.method == "POST" or request.method == "PUT":
        if "content-length" in request.headers:
            content_length = int(request.headers["content-length"])
            if content_length > MAX_UPLOAD_SIZE:
                logger.warning(
                    "Request rejected: content too large (%d bytes)", content_length
                )
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request payload too large"},
                )
    return await call_next(request)


def _dataset():
    try:
        return load_dataset_cached("config.yaml")
    except KpiError as exc:
        logger.error("Dataset load error: %s", str(exc))
        raise HTTPException(status_code=400, detail="Failed to load dataset") from exc


@app.get("/health")
@limiter.limit("30/minute")
async def health(request: Request) -> dict:
    return {"status": "ok"}


@app.get("/months")
@limiter.limit("20/minute")
async def months(
    request: Request, api_key: str = Depends(verify_api_key)
) -> dict:
    try:
        return {"months": kpi.available_months(_dataset())}
    except Exception as exc:
        logger.error("Error fetching months: %s", str(exc))
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@app.get("/kpi/{mois}")
@limiter.limit("20/minute")
async def month_kpi(
    request: Request,
    mois: str = Depends(validate_month_format),
    api_key: str = Depends(verify_api_key),
) -> dict:
    try:
        # SECURITY: Audit this data access
        audit.log_data_access(user=api_key[:8] + "...", mois=mois, data_type="KPI")
        
        df = _dataset()
        if mois not in kpi.available_months(df):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Month not found"
            )
        summary = kpi.monthly_summary(df)
        return {
            "kpi": kpi.calculate_month_kpi(df, mois).as_dict(),
            "comparison": anomalies.compare_months(summary, mois),
            "anomalies": anomalies.detect_anomalies(
                summary,
                mois,
                config.thresholds.anomaly_std_multiplier,
                config.thresholds.anomaly_window_months,
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error calculating KPI for %s: %s", mois, str(exc))
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@app.get("/kpi/{mois}/par-site")
@limiter.limit("20/minute")
async def kpi_by_site(
    request: Request,
    mois: str = Depends(validate_month_format),
    api_key: str = Depends(verify_api_key),
) -> list[dict]:
    try:
        return kpi.distribution(_dataset(), mois, "site").to_dict(orient="records")
    except Exception as exc:
        logger.error("Error fetching KPI by site for %s: %s", mois, str(exc))
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@app.get("/kpi/{mois}/sujets")
@limiter.limit("20/minute")
async def kpi_by_subject(
    request: Request,
    mois: str = Depends(validate_month_format),
    api_key: str = Depends(verify_api_key),
) -> list[dict]:
    try:
        return kpi.subjects_opened_month(_dataset(), mois).to_dict(orient="records")
    except Exception as exc:
        logger.error("Error fetching subjects for %s: %s", mois, str(exc))
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@app.get("/satisfaction/{mois}")
@limiter.limit("20/minute")
async def satisfaction(
    request: Request,
    mois: str = Depends(validate_month_format),
    api_key: str = Depends(verify_api_key),
) -> dict:
    try:
        # SECURITY: Audit this data access
        audit.log_data_access(user=api_key[:8] + "...", mois=mois, data_type="Satisfaction")
        
        result = kpi.calculate_month_kpi(_dataset(), mois)
        return {"mois": mois, **result.satisfaction.as_dict()}
    except Exception as exc:
        logger.error("Error fetching satisfaction for %s: %s", mois, str(exc))
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@app.get("/export/{mois}")
@limiter.limit("10/minute")
async def export(
    request: Request,
    mois: str = Depends(validate_month_format),
    api_key: str = Depends(verify_api_key),
) -> dict:
    try:
        # SECURITY: Audit this sensitive export
        audit.log_export(user=api_key[:8] + "...", mois=mois, format="PDF/Excel")
        
        df = _dataset()
        exports_dir = resolve_path(config.data.exports_dir) or Path("data/exports")
        pdf_path = export_month_pdf(df, mois, exports_dir, config.company_name)
        excel_path = export_month_excel(df, mois, exports_dir)
        # SECURITY: Don't expose full paths to client
        return {
            "mois": mois,
            "pdf": pdf_path.name,
            "excel": excel_path.name,
            "download_url_pdf": f"/download/pdf/{mois}",
            "download_url_excel": f"/download/excel/{mois}",
        }
    except Exception as exc:
        logger.error("Error exporting month %s: %s", mois, str(exc))
        raise HTTPException(status_code=500, detail="Internal server error") from exc
