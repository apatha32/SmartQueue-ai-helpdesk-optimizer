import streamlit as st
import requests
import redis
import json
import time
import pandas as pd
import plotly.graph_objects as go
import os

API_URL = os.getenv("API_URL", "http://localhost:8080")
REDIS_ADDR = os.getenv("REDIS_ADDR", "localhost:6379")
redis_host, redis_port = REDIS_ADDR.split(":")

st.set_page_config(page_title="Task Queue Monitor", page_icon="⚙️", layout="wide")
st.title("Distributed Task Queue — Live Monitor")


@st.cache_resource
def get_redis_client():
    return redis.Redis(host=redis_host, port=int(redis_port), decode_responses=True)


def get_stats() -> dict:
    try:
        resp = requests.get(f"{API_URL}/api/v1/stats", timeout=2)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def submit_job(job_type: str, payload: dict, priority: int, max_retries: int) -> dict:
    try:
        resp = requests.post(
            f"{API_URL}/api/v1/jobs",
            json={"type": job_type, "payload": payload, "priority": priority, "max_retries": max_retries},
            timeout=2,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Submit Job")
    job_type = st.selectbox("Job Type", ["email", "image_resize", "report"])
    priority_label, priority_val = st.selectbox(
        "Priority",
        [("High (1)", 1), ("Medium (2)", 2), ("Low (3)", 3)],
        format_func=lambda x: x[0],
    )
    max_retries = st.slider("Max Retries", 0, 5, 3)
    payload_str = st.text_area("Payload (JSON)", '{"key": "value"}')

    if st.button("Submit Job", type="primary"):
        try:
            payload = json.loads(payload_str)
            result = submit_job(job_type, payload, priority_val, max_retries)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(f"Queued: {result.get('id', '')[:8]}…")
        except json.JSONDecodeError:
            st.error("Invalid JSON payload")

    st.divider()
    auto_refresh = st.checkbox("Auto-refresh every 5s", value=True)

# ── Metrics ──────────────────────────────────────────────────────────────────
stats = get_stats()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Pending",    stats.get("pending_count", 0))
c2.metric("Processing", stats.get("processing_count", 0))
c3.metric("Completed",  stats.get("completed_count", 0))
c4.metric("Failed",     stats.get("failed_count", 0))
c5.metric("Dead",       stats.get("dead_count", 0))

# ── Donut chart ───────────────────────────────────────────────────────────────
fig = go.Figure(go.Pie(
    labels=["Pending", "Processing", "Completed", "Failed", "Dead"],
    values=[
        stats.get("pending_count", 0),
        stats.get("processing_count", 0),
        stats.get("completed_count", 0),
        stats.get("failed_count", 0),
        stats.get("dead_count", 0),
    ],
    hole=0.45,
    marker_colors=["#f59e0b", "#3b82f6", "#10b981", "#ef4444", "#6b7280"],
))
fig.update_layout(title="Job Distribution", height=340, margin=dict(t=40, b=0))
st.plotly_chart(fig, use_container_width=True)

# ── In-flight jobs ────────────────────────────────────────────────────────────
st.subheader("Currently Processing")
r = get_redis_client()
processing = r.hgetall("queue:processing")
if processing:
    rows = []
    now_ms = time.time() * 1000
    for job_id, ts in processing.items():
        elapsed = (now_ms - float(ts)) / 1000
        rows.append({"Job ID": job_id[:8] + "…", "Running (s)": f"{elapsed:.1f}"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.info("No jobs currently processing.")

# ── Dead-letter queue ─────────────────────────────────────────────────────────
st.subheader("Dead Letter Queue  (last 10)")
dead_ids = r.lrange("queue:dead", 0, 9)
if dead_ids:
    rows = []
    for job_id in dead_ids:
        raw = r.get(f"job:{job_id}")
        if raw:
            job = json.loads(raw)
            rows.append({
                "ID":      job_id[:8] + "…",
                "Type":    job.get("type"),
                "Retries": job.get("retries"),
                "Error":   job.get("error", ""),
            })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.success("Dead letter queue is empty.")

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(5)
    st.rerun()
