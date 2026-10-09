"""
HTTP routes for the thoughts dashboard.

Each route:
  - Validates all user input (whitelist, type, range)
  - Delegates database work to query functions in database.py
  - Returns safe, escaped output via Jinja2 templates
  - Never leaks sensitive info in error responses

Spec: specs/architecture/web_application.spec (Routing)
Spec: specs/security/web_security.spec (Input Validation REQ-10..12)
"""
import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request

from src.database import get_all_thoughts

logger = logging.getLogger(__name__)

# Allowed values for the status filter — whitelist validation (REQ-10)
ALLOWED_STATUSES = {"APPROVED", "REJECTED", "IN_REVIEW", "PENDING", "ALL"}

# Pagination hard limits (REQ-11 type/range validation)
MAX_LIMIT = 500
DEFAULT_LIMIT = 100

bp = Blueprint("main", __name__)


@bp.route("/health")
def health() -> Any:
    """
    Health check endpoint for container orchestration.

    Exempt from CSRF (GET, read-only, no auth).
    Spec: specs/architecture/web_application.spec (Health Check REQ)
    """
    db = current_app.extensions.get("db")
    db_ok = db.health_check() if db else False
    status = "healthy" if db_ok else "unhealthy"
    http_code = 200 if db_ok else 503

    return (
        jsonify(
            {
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": {"database": "ok" if db_ok else "failed"},
            }
        ),
        http_code,
    )


@bp.route("/")
def index() -> Any:
    """
    Main dashboard: display all thoughts in a table.

    Accepts optional query parameters:
      - status: filter by status (whitelist-validated)
      - limit:  max rows to display (type and range validated)

    Spec: specs/security/web_security.spec (REQ-10, REQ-11, REQ-12)
    """
    db = current_app.extensions.get("db")

    # --- Input validation: status filter (REQ-10 whitelist) ---
    raw_status = request.args.get("status", "ALL").strip().upper()
    if raw_status not in ALLOWED_STATUSES:
        logger.warning(
            "Input validation failure: invalid status=%r from %s",
            raw_status,
            request.remote_addr,
        )
        return render_template(
            "error.html",
            message="Invalid status filter. Allowed values: "
            + ", ".join(sorted(ALLOWED_STATUSES - {"ALL"})),
        ), 400

    # --- Input validation: limit (REQ-11 type + range) ---
    try:
        limit = int(request.args.get("limit", str(DEFAULT_LIMIT)))
        limit = max(1, min(limit, MAX_LIMIT))  # clamp to valid range
    except ValueError:
        logger.warning(
            "Input validation failure: non-integer limit from %s",
            request.remote_addr,
        )
        return render_template(
            "error.html",
            message=f"Invalid limit parameter. Must be an integer between 1 and {MAX_LIMIT}.",
        ), 400

    thoughts = []
    error_message = None

    try:
        if db:
            thoughts = get_all_thoughts(db)
            # Apply status filter in Python (no user input touches SQL)
            if raw_status != "ALL":
                thoughts = [t for t in thoughts if t.get("status") == raw_status]
            # Apply limit
            thoughts = thoughts[:limit]
        else:
            error_message = "Database connection unavailable."
            logger.error("No database connection available for index route")
    except Exception as exc:
        # Generic message to user — full detail in logs only (REQ-17)
        error_message = "Unable to retrieve thoughts. Please try again later."
        logger.error("Error fetching thoughts: %s", exc)

    return render_template(
        "index.html",
        thoughts=thoughts,
        error_message=error_message,
        current_status=raw_status,
        current_limit=limit,
        allowed_statuses=sorted(ALLOWED_STATUSES - {"ALL"}),
    )
