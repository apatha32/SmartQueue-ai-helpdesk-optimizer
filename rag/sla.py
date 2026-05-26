"""SLA tracking — computes breach risk for support tickets."""
from datetime import datetime, timezone
from typing import Any

SLA_HOURS: dict[int, int] = {1: 1, 2: 4, 3: 8, 4: 48}


def check_sla_status(job: dict[str, Any]) -> dict:
    priority = int(job.get("payload", {}).get("priority", 3))
    sla_hours = job.get("payload", {}).get("sla_hours") or SLA_HOURS.get(priority, 8)

    created_raw = job.get("created_at")
    if not created_raw:
        return {"status": "unknown", "remaining_minutes": None, "breach_risk": "unknown"}

    try:
        created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
    except ValueError:
        return {"status": "unknown", "remaining_minutes": None, "breach_risk": "unknown"}

    now = datetime.now(timezone.utc)
    elapsed_min = (now - created_dt).total_seconds() / 60
    sla_min = sla_hours * 60
    remaining_min = sla_min - elapsed_min
    pct = elapsed_min / sla_min

    if remaining_min < 0:
        status, risk = "breached", "breached"
    elif pct >= 0.75:
        status, risk = "at_risk", "high"
    elif pct >= 0.50:
        status, risk = "warning", "medium"
    else:
        status, risk = "ok", "low"

    return {
        "status": status,
        "remaining_minutes": round(remaining_min),
        "breach_risk": risk,
        "sla_hours": sla_hours,
        "elapsed_minutes": round(elapsed_min),
        "pct_elapsed": round(pct * 100),
    }


def get_at_risk_jobs(jobs: list[dict]) -> list[dict]:
    """Return jobs with high/breached SLA risk, sorted by urgency."""
    at_risk = []
    for job in jobs:
        sla = check_sla_status(job)
        if sla["breach_risk"] in ("high", "breached"):
            at_risk.append({**job, "sla": sla})
    return sorted(at_risk, key=lambda j: j["sla"]["remaining_minutes"])
