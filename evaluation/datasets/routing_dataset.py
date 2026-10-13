"""Supervisor Routing Evaluation Dataset — 20 benchmark routing test cases.

Evaluates whether the LangGraph supervisor correctly classifies intent and
routes queries to the appropriate specialist agent:
- rag (Document knowledge retrieval)
- sql (Database querying and analytics)
- tool (Deterministic computation / utilities)
- memory (User preferences, long-term context recall)
- direct (Conversational banter, system info, greetings)
"""

from __future__ import annotations

from typing import TypedDict


class RoutingTestCase(TypedDict):
    id: str
    user_message: str
    expected_agent: str  # rag, sql, tool, memory, direct
    intent_description: str


ROUTING_DATASET: list[RoutingTestCase] = [
    # ── RAG Intent (5 cases) ─────────────────────────────────────────────────
    {
        "id": "route_01",
        "user_message": "What is our policy on remote work equipment reimbursement?",
        "expected_agent": "rag",
        "intent_description": "Company policy retrieval from employee handbook",
    },
    {
        "id": "route_02",
        "user_message": "What are the response time SLAs for Severity 1 outages?",
        "expected_agent": "rag",
        "intent_description": "Support SLA lookup from customer agreements",
    },
    {
        "id": "route_03",
        "user_message": "According to our architecture docs, what is the database backup frequency and retention?",
        "expected_agent": "rag",
        "intent_description": "Infrastructure standards verification",
    },
    {
        "id": "route_04",
        "user_message": "How many days of paid vacation do full-time employees receive per year?",
        "expected_agent": "rag",
        "intent_description": "HR handbook PTO query",
    },
    {
        "id": "route_05",
        "user_message": "Does our refund policy cover annual contracts, and who has approval authority?",
        "expected_agent": "rag",
        "intent_description": "Financial and SLA refund guidelines",
    },

    # ── SQL Intent (5 cases) ─────────────────────────────────────────────────
    {
        "id": "route_06",
        "user_message": "How many registered users are currently in our database?",
        "expected_agent": "sql",
        "intent_description": "Database count query over users table",
    },
    {
        "id": "route_07",
        "user_message": "What is the total token consumption and cost across all chats this month?",
        "expected_agent": "sql",
        "intent_description": "Aggregated metrics query over chats table",
    },
    {
        "id": "route_08",
        "user_message": "Show me a list of all documents with 'completed' processing status.",
        "expected_agent": "sql",
        "intent_description": "Filtered query over documents table",
    },
    {
        "id": "route_09",
        "user_message": "Find the top 5 most active users ordered by chat message count.",
        "expected_agent": "sql",
        "intent_description": "Sorted ranking query over database",
    },
    {
        "id": "route_10",
        "user_message": "Count how many approval requests are currently in 'pending' status.",
        "expected_agent": "sql",
        "intent_description": "Operational count query over approvals table",
    },

    # ── Tool Intent (4 cases) ────────────────────────────────────────────────
    {
        "id": "route_11",
        "user_message": "Calculate the square root of 144 multiplied by 3.14159.",
        "expected_agent": "tool",
        "intent_description": "Mathematical calculation tool invocation",
    },
    {
        "id": "route_12",
        "user_message": "What is the current UTC timestamp and what day of the week is it?",
        "expected_agent": "tool",
        "intent_description": "Current date and time utility",
    },
    {
        "id": "route_13",
        "user_message": "Generate a random 16-character alphanumeric password for a staging test account.",
        "expected_agent": "tool",
        "intent_description": "Utility string generation",
    },
    {
        "id": "route_14",
        "user_message": "Compute 2 to the power of 16 minus 1024.",
        "expected_agent": "tool",
        "intent_description": "Arithmetic computation",
    },

    # ── Memory Intent (3 cases) ──────────────────────────────────────────────
    {
        "id": "route_15",
        "user_message": "Remember that my preferred report format is bullet points with markdown tables.",
        "expected_agent": "memory",
        "intent_description": "Storing user preference into long-term memory",
    },
    {
        "id": "route_16",
        "user_message": "What preferences or notes do you have saved about me?",
        "expected_agent": "memory",
        "intent_description": "Recalling user context from long-term memory",
    },
    {
        "id": "route_17",
        "user_message": "Forget my note regarding the staging server IP address.",
        "expected_agent": "memory",
        "intent_description": "Deleting or updating memory record",
    },

    # ── Direct / Conversational Intent (3 cases) ─────────────────────────────
    {
        "id": "route_18",
        "user_message": "Hello! What can you help me with today?",
        "expected_agent": "direct",
        "intent_description": "Conversational greeting and capability overview",
    },
    {
        "id": "route_19",
        "user_message": "Who created you and what architecture do you run on?",
        "expected_agent": "direct",
        "intent_description": "System identity inquiry",
    },
    {
        "id": "route_20",
        "user_message": "Thank you for the explanation, that was very clear!",
        "expected_agent": "direct",
        "intent_description": "Conversational acknowledgment",
    },

    # ── Adversarial / Ambiguous Multi-Intent (6 cases) ───────────────────────
    {
        "id": "adv_route_01",
        "user_message": "Check our customer support SLA document for Severity 1 response time and tell me how many Severity 1 tickets are in the database.",
        "expected_agent": "rag",
        "intent_description": "Adversarial: Dual RAG and SQL intent (tests supervisor single-hop resolution)",
    },
    {
        "id": "adv_route_02",
        "user_message": "What is our home office equipment stipend and compute 18% tax deduction on that amount?",
        "expected_agent": "rag",
        "intent_description": "Adversarial: Dual RAG and Tool math computation",
    },
    {
        "id": "adv_route_03",
        "user_message": "Remember my preference for concise tables and query PostgreSQL for all active users.",
        "expected_agent": "memory",
        "intent_description": "Adversarial: Dual Memory preference and SQL database query",
    },
    {
        "id": "adv_route_04",
        "user_message": "How do I configure Redis caching according to architecture standards and how many Redis records are currently stored in the DB?",
        "expected_agent": "rag",
        "intent_description": "Adversarial: Dual Architecture RAG and SQL analytics",
    },
    {
        "id": "adv_route_05",
        "user_message": "Calculate 25 * 40 and remember that my project code is ALPHA_7.",
        "expected_agent": "tool",
        "intent_description": "Adversarial: Dual Tool computation and Memory record",
    },
    {
        "id": "adv_route_06",
        "user_message": "What is the capital of France and who won the 2022 World Cup?",
        "expected_agent": "direct",
        "intent_description": "Adversarial: Out-of-enterprise-scope trivia query",
    },
]

