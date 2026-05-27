"""IT runbook knowledge base — in-memory BM25-style word-overlap search."""
import math
import asyncio
from collections import Counter

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


# ── In-memory BM25-style retrieval (no external DB needed) ──────────────────

def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _idf(term: str, corpus: list[list[str]]) -> float:
    n = len(corpus)
    df = sum(1 for doc in corpus if term in doc)
    return math.log((n - df + 0.5) / (df + 0.5) + 1)


_CORPUS = [_tokenize(r["content"]) for r in RUNBOOKS]


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], k1: float = 1.5, b: float = 0.75) -> float:
    avg_dl = sum(len(d) for d in _CORPUS) / len(_CORPUS)
    tf = Counter(doc_tokens)
    score = 0.0
    for term in query_tokens:
        if term not in tf:
            continue
        idf = _idf(term, _CORPUS)
        dl = len(doc_tokens)
        score += idf * (tf[term] * (k1 + 1)) / (tf[term] + k1 * (1 - b + b * dl / avg_dl))
    return score


def seed_knowledge_base():
    """No-op — knowledge base is in-memory."""
    print(f"Knowledge base ready — {len(RUNBOOKS)} runbooks loaded (in-memory)")


async def search_knowledge(query: str, k: int = 4) -> list[dict]:
    """BM25 search over IT runbooks."""
    q_tokens = _tokenize(query)
    scored = [
        (_bm25_score(q_tokens, doc_tokens), runbook)
        for doc_tokens, runbook in zip(_CORPUS, RUNBOOKS)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"content": r["content"], "source": r["source"]}
        for _, r in scored[:k]
        if _ > 0
    ]
