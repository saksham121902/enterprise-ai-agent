"""Database seed script — creates default tenant, roles, demo users, sample documents,
sample chats, approvals, and memories.

Usage::

    # From the backend directory:
    python -m app.seed

    # With custom admin credentials:
    ADMIN_EMAIL=admin@company.com ADMIN_PASSWORD=s3cret python -m app.seed

This script is idempotent — safe to run multiple times without duplicating data.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.base import Base
from app.models.chat import Chat, Message
from app.models.document import Document
from app.models.operational import Approval, CostTracking, Memory
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User


from app.core.sample_data import SAMPLE_DOCUMENTS


async def seed_database() -> None:
    """Seed the database with initial tenant, roles, users, documents, chats, and operational data."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # Ensure all database tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        try:
            # ── 1. Create Default Tenant ────────────────────────────────────
            result = await session.execute(
                select(Tenant).where(Tenant.slug == "default")
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                tenant = Tenant(
                    id=uuid.uuid4(),
                    name="Default Organization",
                    slug="default",
                    description="Default tenant for development and demo",
                    is_active=True,
                )
                session.add(tenant)
                await session.flush()
                print(f"✓ Created tenant: {tenant.name} ({tenant.id})")
            else:
                print(f"• Tenant already exists: {tenant.name}")

            # ── 2. Create Roles ─────────────────────────────────────────────
            roles_config = [
                {
                    "name": "admin",
                    "description": "Full system administrator access",
                    "permissions_csv": (
                        "chat:create,chat:read,chat:delete,"
                        "document:upload,document:read,document:delete,"
                        "workflow:read,workflow:manage,"
                        "analytics:read,analytics:export,"
                        "memory:create,memory:read,memory:delete,"
                        "approval:read,approval:manage,"
                        "user:manage,tenant:manage,settings:manage"
                    ),
                },
                {
                    "name": "manager",
                    "description": "Team management and approval privileges",
                    "permissions_csv": (
                        "chat:create,chat:read,chat:delete,"
                        "document:upload,document:read,document:delete,"
                        "workflow:read,"
                        "analytics:read,"
                        "memory:create,memory:read,memory:delete,"
                        "approval:read,approval:manage"
                    ),
                },
                {
                    "name": "employee",
                    "description": "Standard user and chat access",
                    "permissions_csv": (
                        "chat:create,chat:read,"
                        "document:upload,document:read,"
                        "workflow:read,"
                        "analytics:read,"
                        "memory:create,memory:read,memory:delete"
                    ),
                },
            ]

            role_map: dict[str, Role] = {}
            for role_data in roles_config:
                res = await session.execute(
                    select(Role).where(Role.name == role_data["name"])
                )
                role = res.scalar_one_or_none()
                if not role:
                    role = Role(
                        id=uuid.uuid4(),
                        name=role_data["name"],
                        description=role_data["description"],
                        permissions_csv=role_data["permissions_csv"],
                    )
                    session.add(role)
                    await session.flush()
                    print(f"✓ Created role: {role.name}")
                else:
                    print(f"• Role already exists: {role.name}")
                role_map[role.name] = role

            # ── 3. Create Admin & Demo Users ────────────────────────────────
            admin_email = os.getenv("ADMIN_EMAIL", "admin@enterprise-ai.local")
            admin_user_res = await session.execute(
                select(User).where(User.email == admin_email)
            )
            admin_user = admin_user_res.scalar_one_or_none()
            if not admin_user:
                admin_user = User(
                    id=uuid.uuid4(),
                    email=admin_email,
                    username=os.getenv("ADMIN_USERNAME", "admin"),
                    hashed_password=hash_password(os.getenv("ADMIN_PASSWORD", "admin123!")),
                    full_name=os.getenv("ADMIN_FULL_NAME", "System Administrator"),
                    is_active=True,
                    is_verified=True,
                    tenant_id=tenant.id,
                    role_id=role_map["admin"].id,
                )
                session.add(admin_user)
                await session.flush()
                print(f"✓ Created admin user: {admin_email} / admin123!")
            else:
                print(f"• Admin user exists: {admin_email}")

            demo_email = "demo@enterprise-ai.local"
            demo_user_res = await session.execute(
                select(User).where(User.email == demo_email)
            )
            demo_user = demo_user_res.scalar_one_or_none()
            if not demo_user:
                demo_user = User(
                    id=uuid.uuid4(),
                    email=demo_email,
                    username="demouser",
                    hashed_password=hash_password("demo123!"),
                    full_name="Demo Evaluation User",
                    is_active=True,
                    is_verified=True,
                    tenant_id=tenant.id,
                    role_id=role_map["employee"].id,
                )
                session.add(demo_user)
                await session.flush()
                print(f"✓ Created demo user: {demo_email} / demo123!")
            else:
                print(f"• Demo user exists: {demo_email}")

            # ── 4. Seed Sample Documents & Embeddings ───────────────────────
            upload_dir = Path("/tmp/uploads") if os.name == "nt" else Path("./uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)

            for doc_info in SAMPLE_DOCUMENTS:
                file_path = upload_dir / doc_info["filename"]
                file_path.write_text(doc_info["content"], encoding="utf-8")

                content_hash = hashlib.sha256(doc_info["content"].encode()).hexdigest()
                existing_doc_res = await session.execute(
                    select(Document).where(Document.filename == doc_info["filename"])
                )
                existing_doc = existing_doc_res.scalar_one_or_none()

                if not existing_doc:
                    new_doc = Document(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        uploaded_by=admin_user.id,
                        filename=doc_info["filename"],
                        original_filename=doc_info["title"],
                        file_type="txt",
                        file_size_bytes=len(doc_info["content"].encode()),
                        file_path=str(file_path),
                        status="completed",
                        page_count=1,
                        chunk_count=3,
                        character_count=len(doc_info["content"]),
                        collection_name=f"tenant_{tenant.id}_documents",
                        content_hash=content_hash,
                    )
                    session.add(new_doc)
                    await session.flush()
                    print(f"✓ Seeded document: {doc_info['title']}")

                    # Attempt to embed into ChromaDB if available
                    try:
                        import chromadb
                        from app.services.document_service import _chunk_text

                        chroma_client = chromadb.HttpClient(
                            host=settings.chromadb_host,
                            port=settings.chromadb_port,
                        )
                        collection = chroma_client.get_or_create_collection(
                            name=f"tenant_{tenant.id}_documents",
                            metadata={"hnsw:space": "cosine"},
                        )
                        chunks = _chunk_text(doc_info["content"])
                        chunk_ids = [f"{new_doc.id}_chunk_{i}" for i in range(len(chunks))]
                        metadatas = [
                            {
                                "source": doc_info["filename"],
                                "document_id": str(new_doc.id),
                                "chunk_index": i,
                                "chunk_id": chunk_ids[i],
                                "tenant_id": str(tenant.id),
                                "page_number": 1,
                            }
                            for i in range(len(chunks))
                        ]
                        collection.upsert(ids=chunk_ids, documents=chunks, metadatas=metadatas)
                        print(f"  → Embedded {len(chunks)} chunks into ChromaDB collection")
                    except Exception as exc:
                        print(f"  → (ChromaDB embedding skipped during seed: {exc})")
                else:
                    print(f"• Document already exists: {doc_info['title']}")

            # ── 5. Seed Realistic Sample Chats & Messages ───────────────────
            existing_chats = await session.execute(
                select(Chat).where(Chat.tenant_id == tenant.id)
            )
            if not existing_chats.scalars().first():
                # Chat 1: SQL Analytics
                chat_1 = Chat(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=admin_user.id,
                    title="System Users & Tenants Audit",
                    total_messages=2,
                    total_tokens=420,
                    total_cost=Decimal("0.001250"),
                )
                session.add(chat_1)
                await session.flush()

                msg_1_user = Message(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    chat_id=chat_1.id,
                    role="user",
                    content="How many users and organizations are registered in our platform?",
                    input_tokens=15,
                    output_tokens=0,
                    cost=Decimal("0"),
                    processing_time_ms=0,
                )
                msg_1_asst = Message(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    chat_id=chat_1.id,
                    role="assistant",
                    content=(
                        "I queried the system database to check our active tenants and user counts.\n\n"
                        "```sql\n"
                        "SELECT COUNT(DISTINCT id) AS total_users, COUNT(DISTINCT tenant_id) AS total_tenants FROM users;\n"
                        "```\n\n"
                        "**Query Results:**\n"
                        "```\n"
                        "total_users | total_tenants\n"
                        "--------------------------\n"
                        "2           | 1\n"
                        "```\n\n"
                        "Currently, there are **2 registered users** across **1 active organization**."
                    ),
                    model="gpt-4o",
                    provider="openai",
                    input_tokens=220,
                    output_tokens=185,
                    cost=Decimal("0.001250"),
                    processing_time_ms=780,
                    agent_trace_json=json.dumps([{"agent": "supervisor", "next": "sql"}, {"agent": "sql", "status": "executed"}]),
                )
                session.add_all([msg_1_user, msg_1_asst])

                # Chat 2: Policy RAG
                chat_2 = Chat(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=demo_user.id,
                    title="Remote Work Equipment Budget",
                    total_messages=2,
                    total_tokens=560,
                    total_cost=Decimal("0.001850"),
                )
                session.add(chat_2)
                await session.flush()

                msg_2_user = Message(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    chat_id=chat_2.id,
                    role="user",
                    content="What is our home office equipment stipend and how do I claim it?",
                    input_tokens=18,
                    output_tokens=0,
                    cost=Decimal("0"),
                    processing_time_ms=0,
                )
                msg_2_asst = Message(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    chat_id=chat_2.id,
                    role="assistant",
                    content=(
                        "According to the **Acme Corp Employee Handbook 2024** (Section 2: Remote Work & Equipment Stipend):\n\n"
                        "• **Amount**: Full-time new hires receive a **$500 one-time home office equipment stipend**.\n"
                        "• **Eligible Items**: Desks, monitors, and ergonomic seating.\n"
                        "• **Submission Window**: Receipts must be submitted via the expense portal within **60 days** of your start date.\n"
                        "• **Laptops**: Laptops are refreshed automatically every 3 years."
                    ),
                    model="gpt-4o",
                    provider="openai",
                    input_tokens=350,
                    output_tokens=192,
                    cost=Decimal("0.001850"),
                    processing_time_ms=640,
                    agent_trace_json=json.dumps([{"agent": "supervisor", "next": "rag"}, {"agent": "rag", "chunks_retrieved": 2}]),
                )
                session.add_all([msg_2_user, msg_2_asst])

                # Cost tracking entries
                cost_1 = CostTracking(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=admin_user.id,
                    chat_id=chat_1.id,
                    provider="openai",
                    model="gpt-4o",
                    input_tokens=220,
                    output_tokens=185,
                    cost_usd=Decimal("0.001250"),
                    agent_type="sql",
                )
                cost_2 = CostTracking(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=demo_user.id,
                    chat_id=chat_2.id,
                    provider="openai",
                    model="gpt-4o",
                    input_tokens=350,
                    output_tokens=192,
                    cost_usd=Decimal("0.001850"),
                    agent_type="rag",
                )
                session.add_all([cost_1, cost_2])
                print("✓ Seeded sample chats and cost records")
            else:
                print("• Sample chats already present")

            # ── 6. Seed Pending Approval Request ────────────────────────────
            existing_approvals = await session.execute(
                select(Approval).where(Approval.tenant_id == tenant.id)
            )
            if not existing_approvals.scalars().first():
                sample_approval = Approval(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    requested_by=demo_user.id,
                    operation_type="SQL_DELETE",
                    status="pending",
                    description="Truncate legacy staging test records from table `staging_sync_events`",
                    payload_json=json.dumps({
                        "query": "DELETE FROM staging_sync_events WHERE created_at < NOW() - INTERVAL '30 days';",
                        "affected_rows_estimated": 450,
                        "risk_level": "medium",
                    }),
                )
                session.add(sample_approval)
                print("✓ Seeded sample pending approval request")
            else:
                print("• Approvals already present")

            # ── 7. Seed Long-term Memories ──────────────────────────────────
            existing_memories = await session.execute(
                select(Memory).where(Memory.tenant_id == tenant.id)
            )
            if not existing_memories.scalars().first():
                mem_1 = Memory(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=demo_user.id,
                    memory_type="user_preference",
                    content="Prefers structured Markdown summaries with bullet points and code blocks.",
                    importance_score=0.90,
                    source="chat_session",
                    is_active=True,
                )
                mem_2 = Memory(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=admin_user.id,
                    memory_type="system_fact",
                    content="Production database maintenance window is scheduled on Sundays 02:00-04:00 UTC.",
                    importance_score=0.95,
                    source="admin_note",
                    is_active=True,
                )
                session.add_all([mem_1, mem_2])
                print("✓ Seeded long-term user memories")
            else:
                print("• Memories already present")

            await session.commit()
            print("\n🎉 Database seed completed successfully!")
            print(f"   Admin: {admin_email} / admin123!")
            print("   Demo:  demo@enterprise-ai.local / demo123!\n")

        except Exception as e:
            await session.rollback()
            print(f"\n✗ Seeding failed: {e}")
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())
