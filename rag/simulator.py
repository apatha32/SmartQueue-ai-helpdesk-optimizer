"""Demo ticket flood generator — submits realistic IT support tickets to Go API."""
import asyncio
import random
from datetime import datetime, timezone

import httpx

from classifier import classify_ticket

TICKET_POOL = [
    # P1 — Outage
    {"text": "CRITICAL: Production API returning 500 errors for all users. Revenue impact ongoing.", "customer_tier": "enterprise"},
    {"text": "Main database unreachable. Application completely down. 500+ users affected.", "customer_tier": "enterprise"},
    {"text": "Payment processing service is down. Cannot complete any transactions.", "customer_tier": "enterprise"},
    # P1 — Security
    {"text": "Suspicious logins on admin account from foreign IP. Possible breach. Lock now.", "customer_tier": "enterprise"},
    {"text": "Employee clicked phishing attachment. Laptop may be compromised. Need containment.", "customer_tier": "standard"},
    # P2 — Technical
    {"text": "Dashboard loading extremely slowly (30+ seconds). Entire sales team blocked.", "customer_tier": "enterprise"},
    {"text": "Bulk export broken since yesterday's update. Cannot export >100 rows.", "customer_tier": "standard"},
    {"text": "SSO integration not working for SAML provider. Users cannot log in via corporate identity.", "customer_tier": "enterprise"},
    {"text": "API rate limits hit unexpectedly. Automation workflows failing at scale.", "customer_tier": "enterprise"},
    # P2 — Billing
    {"text": "Charged double for last month's subscription. Please refund and explain.", "customer_tier": "standard"},
    {"text": "Need to upgrade from Standard to Enterprise urgently — team expanding next week.", "customer_tier": "standard"},
    {"text": "Q2 invoice shows incorrect usage figures. Need itemized breakdown and correction.", "customer_tier": "enterprise"},
    # P3 — Technical
    {"text": "Email notifications not sent when tickets are updated. Broke last week.", "customer_tier": "standard"},
    {"text": "Search returning irrelevant results. Seems like indexing issue after migration.", "customer_tier": "standard"},
    {"text": "Mobile app crashes on iOS 18 when opening settings. Reproducible on multiple devices.", "customer_tier": "free"},
    {"text": "CSV import silently fails on files >10MB. No error message shown.", "customer_tier": "standard"},
    {"text": "2FA emails going to spam for our domain. SPF/DKIM misconfiguration?", "customer_tier": "standard"},
    # P3 — Access
    {"text": "New employee starting Monday needs: email, VPN, and dev environment access.", "customer_tier": "enterprise"},
    {"text": "Employee locked out after too many failed password attempts. Urgent unlock needed.", "customer_tier": "standard"},
    {"text": "Lost admin panel access after email domain migration. Need account re-verification.", "customer_tier": "enterprise"},
    # P4 — Feature
    {"text": "Would love dark mode for the web dashboard. Many team members prefer it.", "customer_tier": "free"},
    {"text": "Can you add CSV export to the analytics reports? Only PDF available now.", "customer_tier": "standard"},
    {"text": "Requesting Slack integration to receive ticket status updates in our workspace.", "customer_tier": "standard"},
    {"text": "Need bulk ticket assignment for team leads to handle multiple tickets at once.", "customer_tier": "enterprise"},
    {"text": "Please add JIRA integration to sync tickets with our dev board automatically.", "customer_tier": "enterprise"},
]


async def simulate_tickets(count: int, api_base: str = "http://api:8080") -> list[dict]:
    """Classify and submit `count` realistic tickets to the Go API concurrently."""
    selected = random.choices(TICKET_POOL, k=min(count, len(TICKET_POOL) * 2))[:count]

    async def process_one(tmpl: dict) -> dict | None:
        try:
            classification = await classify_ticket(tmpl["text"], tmpl["customer_tier"])
            job_body = {
                "type": "support_ticket",
                "payload": {
                    "text": tmpl["text"],
                    "customer_tier": tmpl["customer_tier"],
                    "category": classification.get("category", "technical"),
                    "tier": classification.get("tier", "tier1"),
                    "estimated_minutes": classification.get("estimated_minutes", 30),
                    "sla_hours": classification.get("sla_hours", 8),
                    "summary": classification.get("summary", tmpl["text"][:60]),
                    "tags": classification.get("tags", []),
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                },
                "priority": classification.get("priority", 3),
                "max_retries": 3,
            }
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(f"{api_base}/api/v1/jobs", json=job_body)
                if resp.status_code == 201:
                    return {**job_body, "id": resp.json().get("id")}
        except Exception as exc:
            print(f"[simulator] ticket failed: {exc}")
        return None

    # Run all classifications and submissions concurrently — 10 at a time
    results = []
    batch_size = 10
    for i in range(0, len(selected), batch_size):
        batch = selected[i:i + batch_size]
        batch_results = await asyncio.gather(*[process_one(t) for t in batch])
        results.extend(r for r in batch_results if r is not None)

    return results
