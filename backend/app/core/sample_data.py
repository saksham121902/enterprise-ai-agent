"""Pre-seeded enterprise document texts and operational sample data.

Pure standard library Python data structures — zero third-party dependencies.
Used by both the database seed script and evaluation benchmark runner.
"""

from __future__ import annotations

SAMPLE_DOCUMENTS = [
    {
        "filename": "employee_handbook_2024.txt",
        "title": "Acme Corp Employee Handbook 2024",
        "content": (
            "ACME CORP EMPLOYEE HANDBOOK 2024\n\n"
            "1. WORKPLACE POLICIES & CORE HOURS\n"
            "Standard core collaboration hours are 10:00 AM to 4:00 PM EST. Flexible scheduling "
            "is permitted outside of core hours with manager alignment. All employees are expected "
            "to attend required sprint planning and cross-functional syncs.\n\n"
            "2. REMOTE WORK & EQUIPMENT STIPEND\n"
            "Acme Corp operates a remote-first workplace model. New full-time hires receive a "
            "one-time $500 home office equipment stipend for desks, monitors, and ergonomic seating. "
            "Receipts must be submitted via the expense portal within 60 days of start date.\n"
            "Company laptops are refreshed every three (3) years. Lost or damaged equipment must "
            "be reported to IT security within 24 hours.\n\n"
            "3. PAID TIME OFF (PTO) & SICK LEAVE\n"
            "Full-time employees receive 20 days of paid vacation per calendar year, accrued monthly. "
            "In addition, 10 paid sick days and 11 observed federal holidays are provided. Up to 5 unused "
            "vacation days may roll over into the following calendar year.\n\n"
            "4. CODE OF CONDUCT & DATA PRIVACY\n"
            "All proprietary code, customer records, and internal strategy documents are strictly confidential. "
            "Sharing customer personally identifiable information (PII) on public channels or unauthorized "
            "third-party AI services without anonymization is strictly prohibited."
        ),
    },
    {
        "filename": "cloud_architecture_standards.txt",
        "title": "Acme Cloud Architecture & Security Standards",
        "content": (
            "ACME CLOUD ARCHITECTURE & SECURITY STANDARDS v3.2\n\n"
            "1. CLOUD ENVIRONMENT TIERING\n"
            "We maintain three distinct environments: Development (dev), Staging (stage), and Production (prod). "
            "Production access is restricted to on-call platform engineers using hardware MFA tokens.\n\n"
            "2. DATA STORAGE & ENCRYPTION PROTOCOLS\n"
            "All PostgreSQL and ChromaDB persistent volumes must enforce AES-256 encryption at rest. "
            "In-transit communication requires TLS 1.3. Database backups are taken automatically every 6 hours "
            "and retained in multi-region cold storage for 30 days.\n\n"
            "3. CONTINUOUS DEPLOYMENT & ROLLBACK SLA\n"
            "All microservices must provide automated health probes (/health for liveness, /readiness for dependency checks). "
            "Deployments must execute zero-downtime rolling updates. If error rate exceeds 1% over a 5-minute window, "
            "automated rollback is triggered immediately.\n\n"
            "4. SAFEGUARDING SENSITIVE DATABASE OPERATIONS\n"
            "Direct write access (INSERT, UPDATE, DELETE, DROP) against production tables requires human approval "
            "from an Engineering Manager or Admin before execution via the operations agent."
        ),
    },
    {
        "filename": "customer_support_slas.txt",
        "title": "Customer Support SLAs & Refund Guidelines",
        "content": (
            "ACME CUSTOMER SUPPORT SERVICE LEVEL AGREEMENTS (SLA) & REFUNDS\n\n"
            "1. SUPPORT SEVERITY TIERS\n"
            "- Severity 1 (Critical Outage): Initial response within 15 minutes, 2-hour target resolution. 24/7 coverage.\n"
            "- Severity 2 (Major Degradation): Initial response within 1 hour, 8-hour target resolution.\n"
            "- Severity 3 (Minor Issue / General Inquiry): Initial response within 8 business hours.\n\n"
            "2. REFUND POLICY\n"
            "Enterprise contracts include a 30-day money-back guarantee for unused monthly platform credits. "
            "Full refunds for annual contracts require VP of Finance approval. Support credit adjustments up to $500 "
            "can be approved directly by Support Team Leads."
        ),
    },
]
