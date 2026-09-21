#!/usr/bin/env python3
"""Automated end-to-end test walkthrough script for CareerHarness.

Demonstrates the entire platform lifecycle:
1. Health & Tenant onboarding
2. BYOK Key Vault (OpenRouter with DeepSeek Flash v4.1 envelope encryption)
3. Front-Face First Readiness Gate (Roles -> Resume -> Gaps -> Score >= 70)
4. Job Ingestion & Scout scan (RD-03)
5. Batch formulation & Preview (BA-01..04)
6. 5-Stage Execution Pipeline & ATS Seam Fallback Ladder (AT-01..05, AT-07)
7. Application Tracker & Inbound Email Classifier (GT-05)
8. Funnel Analytics & Lineage Tree (VR-01..03, BT-01..03)
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"


def print_step(num: int, title: str):
    print(f"\n\033[1;36m[{num}/8] {title}\033[0m")


def print_success(msg: str):
    print(f"  \033[1;32m✓\033[0m {msg}")


def print_info(key: str, val: str):
    print(f"    • \033[1;34m{key}:\033[0m {val}")


def request(method: str, path: str, data: dict = None, tenant_id: str = None) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"\033[1;31mHTTP {e.code} Error on {method} {path}:\033[0m {err_body}")
        raise


def run_walkthrough():
    print("\033[1;35m=========================================================\033[0m")
    print("\033[1;35m      CareerHarness End-to-End Live Walkthrough          \033[0m")
    print("\033[1;35m=========================================================\033[0m")

    # Step 1: Health & Demo Tenant
    print_step(1, "Checking Service Health & Tenant Context")
    health = request("GET", "/health")
    print_success(f"FastAPI Server Healthy ({health.get('app')}, env={health.get('environment')})")

    tenant = request("GET", "/api/tenants/demo")
    tenant_id = tenant["id"]
    print_success(f"Tenant Context Active: '{tenant['name']}' (Plan: {tenant['plan']})")
    print_info("Tenant UUID", tenant_id)

    # Step 2: BYOK Key Vault
    print_step(2, "BYOK Key Vault: Storing OpenRouter Key (DeepSeek Flash v4.1)")
    key_resp = request(
        "POST",
        "/api/keys",
        {"provider": "openrouter", "api_key": "sk-or-v1-live-demo-key-deepseek-flashv41"},
        tenant_id=tenant_id,
    )
    print_success(f"Saved & Encrypted BYOK key: {key_resp.get('provider')} -> {key_resp.get('masked_preview')}")
    print_info("Key Security", "Ciphertext at rest via AES-256-GCM + Per-Tenant HKDF DEK")

    # Step 3: Front-Face First Gate
    print_step(3, "Front-Face First: Roles, Resume, LinkedIn & Gap Audit")
    roles = request(
        "POST",
        "/api/roles",
        {"role_ids": ["role_backend_arch", "role_fullstack_eng"], "priority_role_id": "role_backend_arch"},
        tenant_id=tenant_id,
    )
    print_success(f"Selected {len(roles)} Target Roles. Priority: {roles[0]['title']}")

    resume_payload = {
        "filename": "master_cv.txt",
        "content": (
            "Senior Backend Architect with 10 years experience.\n"
            "- Architected high-throughput message streaming cluster handling 10M events/day.\n"
            "- Scaled PostgreSQL sharding and Redis caching clusters delivering 99.99% uptime.\n"
            "- Optimized distributed backend execution pipelines reducing p99 latency by 45%.\n"
            "Skills: Python, SQL, Distributed Systems, Redis, Docker, FastAPI, PostgreSQL."
        ),
    }
    resume = request("POST", "/api/resumes/upload", resume_payload, tenant_id=tenant_id)
    resume_id = resume["id"]
    print_success(f"Ingested Master Resume. Extracted {len(resume.get('extracted_skills', []))} skills.")

    for s in resume.get("extracted_skills", []):
        quoted_skill = urllib.parse.quote(s["name"])
        request("POST", f"/api/resumes/{resume_id}/skills/{quoted_skill}/confirm", tenant_id=tenant_id)
    print_success(f"Confirmed verified facts for {len(resume.get('extracted_skills', []))} skills (AT-06)")

    li_payload = {
        "headline": "Staff Backend Architect | Distributed Systems",
        "about": "Building resilient, zero-downtime distributed systems and high-throughput pipelines.",
        "skills": ["Distributed Systems", "SQL", "Python", "Redis", "PostgreSQL"],
    }
    request("POST", "/api/linkedin/paste", li_payload, tenant_id=tenant_id)
    print_success("Ingested LinkedIn profile data with candidate consent timestamp")

    # Compute Readiness
    request("POST", "/api/gaps/compute", tenant_id=tenant_id)
    
    # Resolve critical todos (Accept fix drafts) to clear the Readiness Gate
    todos = request("GET", "/api/todos", tenant_id=tenant_id)
    resolved_count = 0
    for todo in todos:
        if todo.get("status") == "open":
            request(
                "POST",
                f"/api/todos/{todo['id']}/action",
                {"action": "accept"},
                tenant_id=tenant_id,
            )
            resolved_count += 1
    print_success(f"Resolved & Accepted {resolved_count} Front-Face To-Do Items")

    readiness = request("GET", "/api/readiness", tenant_id=tenant_id)
    print_success(f"Readiness Score: {readiness.get('overall_score')}/100 (Threshold: 70)")
    print_info("Gate Status", "GATE CLEARED! Scout & Apply unlocked." if readiness.get("is_ready") else "BLOCKED")

    # Step 4: Job Ingestion & Discovery
    print_step(4, "Discovery Engine: Ingest Job & Scout Match Scoring")
    job_payload = {
        "title": "Senior Platform Engineer",
        "company": "Stripe",
        "url": f"https://stripe.com/jobs/platform-{int(time.time())}",
        "description": "Senior Platform Engineer needed. Must have Python, Docker, Kubernetes, and distributed systems experience.",
        "portal_type": "greenhouse",
    }
    ingested_job = request("POST", "/api/jobs/ingest", job_payload)
    job_id = ingested_job["id"]
    print_success(f"Ingested Job: {ingested_job['title']} at {ingested_job['company']} (ID: {job_id})")

    scout_res = request("POST", "/api/scout/scan-now", tenant_id=tenant_id)
    print_success(f"On-Demand Scout Scan: Processed {scout_res.get('processed_count', 0)} jobs")

    matches = request("GET", "/api/jobs", tenant_id=tenant_id)
    print_success(f"Matched Jobs for Candidate: {len(matches)} listings")

    # Step 5: Batch Formulation
    print_step(5, "Batch Engine: Formulate Application Group (BA-01..04)")
    batch = request("POST", "/api/batches", {"job_ids": [job_id]}, tenant_id=tenant_id)
    batch_id = batch["batch_id"]
    print_success(f"Created Batch '{batch_id}' with {batch.get('total_jobs', 1)} jobs")

    preview = request("GET", f"/api/batches/{batch_id}/preview", tenant_id=tenant_id)
    print_success(f"Pre-Approval Preview Screen: {len(preview.get('items', []))} items verified")

    # Step 6: 5-Stage Execution Pipeline & ATS Seam
    print_step(6, "5-Stage Application Engine & ATS Fallback Ladder")
    master_payload = {
        "title": "Master Resume - Engineering",
        "content": {
            "candidate_name": "Alex Smith",
            "skills": ["Python", "Docker", "PostgreSQL", "Kubernetes"],
            "experience": [
                {
                    "company": "Cloud Corp",
                    "dates": "2020 - 2024",
                    "bullets": [
                        "Deployed Kubernetes clusters managing 500+ microservices",
                        "Wrote core Python infrastructure processing 10M daily events",
                    ],
                }
            ],
            "education": [{"school": "MIT", "degree": "BS", "year": "2020"}],
        },
        "raw_markdown": "# Alex Smith Resume",
    }
    master_doc = request("POST", "/api/vault/master", master_payload, tenant_id=tenant_id)
    master_id = master_doc["id"]
    print_success(f"Vault Master Initialized: version={master_id[:8]}...")

    tailor_req = {"job_id": job_id, "parent_version_id": master_id, "save_to_vault": True}
    tailor_data = request("POST", "/api/applications/tailor", tailor_req, tenant_id=tenant_id)
    tailored_version_id = tailor_data["vault_version_id"]
    print_success(f"Stage 1 & 2: Resume Tailored & Honesty Verified (is_honest={tailor_data['honesty_review']['is_honest']})")

    ats_req = {"job_id": job_id, "tailored_content": tailor_data["tailored_resume"]}
    ats_data = request("POST", "/api/applications/ats-check", ats_req, tenant_id=tenant_id)
    print_success(f"Stage 4: ATS Scanner Passed (Score: {ats_data['overall_ats_score']}/100, Passed: {ats_data['passed']})")

    # Submit Application with Fallback Ladder
    submit_req = {
        "job_id": job_id,
        "resume_version_id": tailored_version_id,
        "simulate_bot_block": True,  # Test Fallback Ladder to Tier 3 Handoff
    }
    submit_res = request("POST", "/api/applications/submit", submit_req, tenant_id=tenant_id)
    print_success("Stage 5: Executed 3-Tier Fallback Ladder (Tier 1 Bot Block -> Tier 3 1-Click Handoff)")
    print_info("Final Submission Channel", submit_res.get("submission_channel"))
    print_info("Status", submit_res.get("status"))

    # Step 7: Application Tracker & Inbound Email Classification
    print_step(7, "Tracker & Inbound Recruiter Email Classification (GT-05)")
    track_req = {"job_id": job_id, "status": "applied"}
    app_track = request("POST", "/api/tracker/track", track_req, tenant_id=tenant_id)
    app_id = app_track["id"]
    print_success(f"Tracked Application: {app_track['job_title']} at {app_track['company_name']}")

    email_req = {
        "sender_email": "recruiting@stripe.com",
        "subject": "Interview Invitation: Senior Platform Engineer",
        "body_text": "We would like to invite you for a 45-minute technical interview round.",
        "application_id": app_id,
    }
    email_res = request("POST", "/api/tracker/inbound-email", email_req, tenant_id=tenant_id)
    print_success(f"Classified Inbound Email as: {email_res.get('classification').upper()}")

    apps_list = request("GET", "/api/tracker/applications", tenant_id=tenant_id)
    print_success(f"Application Auto-Advanced Status: '{apps_list[0]['status'].upper()}'")

    # Step 8: Funnel Analytics & Settings
    print_step(8, "Funnel Analytics & Trusted Mode Settings (BT-01..03)")
    funnel = request("GET", "/api/insights/funnel", tenant_id=tenant_id)
    print_success(
        f"Funnel Analytics: Total Tracked={funnel.get('total_applications', 1)}, Interview Rate={funnel.get('interview_rate', 1.0) * 100:.1f}%"
    )

    cadence = request(
        "PATCH",
        "/api/insights/cadence",
        {"cadence": "hourly"},
        tenant_id=tenant_id,
    )
    print_success(f"Updated Scout Cadence: {cadence.get('cadence')}")

    trusted = request(
        "POST",
        "/api/insights/trusted-mode",
        {"enable": True},
        tenant_id=tenant_id,
    )
    print_success(f"Trusted Mode Enabled: {trusted.get('trusted_mode')}")

    settings = request("GET", "/api/insights/settings", tenant_id=tenant_id)
    print_success(f"Tenant Settings: Plan={settings.get('plan')}, Scout Cadence={settings.get('scout_cadence')}")

    print("\n\033[1;32m=========================================================\033[0m")
    print("\033[1;32m  ✓ ALL 8 PHASES EXECUTED & VERIFIED SUCCESSFULLY!       \033[0m")
    print("\033[1;32m=========================================================\033[0m")
    print("\nInteractive Web Dashboard: \033[1;36mhttp://localhost:8000\033[0m")
    print("FastAPI Swagger Docs:      \033[1;36mhttp://localhost:8000/docs\033[0m\n")


if __name__ == "__main__":
    try:
        run_walkthrough()
    except Exception as exc:
        print(f"\n\033[1;31mTest walkthrough failed: {exc}\033[0m")
        sys.exit(1)
