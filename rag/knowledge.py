"""IT runbook knowledge base backed by ChromaDB (ONNX embeddings — no torch)."""
import os
import asyncio
from functools import lru_cache

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

RUNBOOKS = [
    {
        "id": "kb001",
        "source": "Password Reset Runbook",
        "content": (
            "To reset a user password in Active Directory: Open ADUC, find user, "
            "right-click → Reset Password. Set temp password (12+ chars, upper+lower+number+symbol). "
            "Check 'User must change at next logon'. Notify via phone not email. "
            "For Azure AD: portal → Users → select user → Reset password. "
            "For MFA reset: Azure AD → Users → Authentication methods → Delete all methods."
        ),
    },
    {
        "id": "kb002",
        "source": "VPN Troubleshooting Runbook",
        "content": (
            "VPN connectivity steps: Check VPN service is running (services.msc). "
            "Verify credentials not expired. Disconnect fully, wait 30s, reconnect. "
            "Check split tunneling if only internal sites fail. DNS: flush DNS (ipconfig /flushdns). "
            "Firewall: ensure UDP 500, 4500 and ESP protocol allowed. "
            "Certificate issues: check if VPN cert expired, re-import if needed. "
            "Cisco AnyConnect: clear cache in preferences. Collect logs and escalate to tier2 if persistent."
        ),
    },
    {
        "id": "kb003",
        "source": "P1 Service Outage Response",
        "content": (
            "P1 Outage Response: Immediately page on-call engineering. "
            "Create incident Slack channel #incident-YYYYMMDD-[service]. "
            "Update status page to 'Investigating'. Check blast radius (how many users affected). "
            "Check recent deployments (last 2 hours) as likely cause. "
            "Review dashboards: CPU, memory, error rates, latency. "
            "Check cloud provider status page. If deployment caused it: initiate rollback. "
            "Update status page every 15 minutes. Post-incident report within 24 hours."
        ),
    },
    {
        "id": "kb004",
        "source": "New User Onboarding",
        "content": (
            "New employee provisioning: Create AD account firstname.lastname@company.com. "
            "Set initial password, force change on first login. Add to security groups by department. "
            "Assign Microsoft 365 license via M365 admin center. "
            "Set up MFA: user enrolls authenticator app on first login. "
            "Create email signature. Grant SharePoint/Teams access. "
            "Set up VPN if required. Install standard software via SCCM/Intune. "
            "Schedule 30-min IT orientation call."
        ),
    },
    {
        "id": "kb005",
        "source": "Database Performance Issues",
        "content": (
            "Slow DB troubleshooting: Identify slow queries via sys.dm_exec_query_stats. "
            "Check index fragmentation with sys.dm_db_index_physical_stats. "
            "Look for blocking: sys.dm_exec_requests WHERE blocking_session_id != 0. "
            "Check execution plans for Index Scan vs Seek. Update statistics. "
            "Check tempdb usage. Review recent schema changes. "
            "Add indexes for frequently filtered columns. "
            "Cloud DB: check DTU/RCU and scale if needed. "
            "Persistent: schedule DBCC CHECKDB in maintenance window."
        ),
    },
    {
        "id": "kb006",
        "source": "Email Delivery Issues",
        "content": (
            "Email troubleshooting: Check MX records (nslookup -type=MX domain.com). "
            "Verify SPF record (nslookup -type=TXT, look for v=spf1). "
            "Test DKIM in mail headers. Check blacklist via MXToolbox. "
            "Exchange/M365: use message trace in admin center. "
            "Check spam filter logs for false positives. "
            "External emails failing: verify connector config. "
            "NDR codes: 550 5.1.1=user not found, 550 5.7.1=policy rejection, 421=temp failure."
        ),
    },
    {
        "id": "kb007",
        "source": "Security Incident Response",
        "content": (
            "Security incident: IMMEDIATELY isolate affected systems from network. "
            "Preserve evidence: memory dump, disk image. Do NOT power off. "
            "Notify security lead and CISO within 15 minutes. "
            "Document timeline: when detected, what observed, systems affected. "
            "Change all potentially compromised credentials immediately. "
            "Check lateral movement in adjacent systems. "
            "Review auth logs for unauthorized access. "
            "Ransomware: do NOT pay, contact FBI and cyber insurance. "
            "All comms via out-of-band channel (phone if email compromised)."
        ),
    },
    {
        "id": "kb008",
        "source": "Network Connectivity Troubleshooting",
        "content": (
            "Network troubleshooting: ping gateway, ping 8.8.8.8, ping domain. "
            "If IP works but not domain: DNS issue, check DNS server settings. "
            "tracert/traceroute to find where packets drop. "
            "Check NIC duplex/speed mismatch. "
            "802.1X: check certificate validity, RADIUS server logs. "
            "VLAN: verify port VLAN on switch. "
            "Wireless: check SSID, WPA2-Enterprise cert. "
            "IP conflicts: arp -a to see ARP table. "
            "Bandwidth: use network monitor for top talkers. "
            "Physical: check cable, switch port error counters."
        ),
    },
    {
        "id": "kb009",
        "source": "Billing and Subscription",
        "content": (
            "Billing handling: Verify customer identity before discussing details. "
            "Overage charges: download usage report, walk through line items. "
            "Failed payments: check card expiry, retry charge, send payment method update link. "
            "Enterprise downgrades require 30-day notice. "
            "Refunds: pro-rated within 30 days of renewal, no refunds after. "
            "Invoice disputes: within 60 days. "
            "Credits: manager approval >$500, VP approval >$5000. "
            "Tax exemptions: customer provides certificate, apply retroactively up to 90 days."
        ),
    },
    {
        "id": "kb010",
        "source": "Software Installation",
        "content": (
            "Software install: Must be on approved list, else submit request (5-day approval). "
            "Mass deploy via SCCM/Intune. Manual: download from official vendor or internal repo only. "
            "Check system requirements (OS, RAM, disk). Run as administrator or PAM tool. "
            "Test in staging before production. Update CMDB inventory after. "
            "macOS: use Jamf, avoid DMG direct installs. "
            "License keys: record in team password vault."
        ),
    },
]


@lru_cache(maxsize=1)
def _client():
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8001"))
    return chromadb.HttpClient(host=host, port=port)


@lru_cache(maxsize=1)
def _ef():
    return DefaultEmbeddingFunction()


def _collection():
    return _client().get_or_create_collection(
        name="helpdesk_knowledge",
        embedding_function=_ef(),
    )


def seed_knowledge_base():
    """Upsert all runbooks into ChromaDB on startup."""
    col = _collection()
    col.upsert(
        ids=[r["id"] for r in RUNBOOKS],
        documents=[r["content"] for r in RUNBOOKS],
        metadatas=[{"source": r["source"]} for r in RUNBOOKS],
    )
    print(f"Knowledge base ready — {len(RUNBOOKS)} runbooks loaded")


async def search_knowledge(query: str, k: int = 4) -> list[dict]:
    """Semantic search over IT runbooks (runs in thread to not block event loop)."""
    loop = asyncio.get_event_loop()

    def _search():
        col = _collection()
        results = col.query(query_texts=[query], n_results=min(k, len(RUNBOOKS)))
        return [
            {"content": doc, "source": meta.get("source", "KB")}
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]

    return await loop.run_in_executor(None, _search)
