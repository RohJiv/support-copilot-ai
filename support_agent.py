# support_agent.py — Customer Support AI Core Logic

import os
from dotenv import load_dotenv
from typing import TypedDict, Literal
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END

load_dotenv()

# ── LLM Setup ─────────────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

# ── STATE — the ticket file passed between all nodes ──────────
# TypedDict defines exactly what data flows through the workflow
class TicketState(TypedDict):
    ticket: str           # original customer message
    category: str         # bug / billing / feature / general
    sentiment: str        # angry / frustrated / neutral / happy
    priority: str         # urgent / high / normal / low
    draft_reply: str      # AI drafted response
    escalate: bool        # should human review this?
    escalation_reason: str # why escalated

# ── NODE 1 — Classify the ticket ─────────────────────────────
def classify_ticket(state: TicketState) -> TicketState:
    prompt = ChatPromptTemplate.from_template("""
You are a customer support classifier.

Classify this support ticket into ONE category:
- bug: software/product not working correctly
- billing: payment, invoice, subscription issues
- feature: request for new functionality
- general: general questions or other issues

Ticket: {ticket}

Reply with ONLY one word: bug, billing, feature, or general
""")
    chain = prompt | llm | StrOutputParser()
    category = chain.invoke({"ticket": state["ticket"]}).strip().lower()

    # Validate — if unexpected response default to general
    if category not in ["bug", "billing", "feature", "general"]:
        category = "general"

    return {**state, "category": category}

# ── NODE 2 — Detect sentiment ─────────────────────────────────
def detect_sentiment(state: TicketState) -> TicketState:
    prompt = ChatPromptTemplate.from_template("""
Analyze the emotional tone of this support ticket.

Ticket: {ticket}

Reply with ONLY one word:
- angry: hostile, threatening, very upset
- frustrated: annoyed, disappointed, impatient
- neutral: calm, matter of fact
- happy: positive, appreciative
""")
    chain = prompt | llm | StrOutputParser()
    sentiment = chain.invoke({"ticket": state["ticket"]}).strip().lower()

    if sentiment not in ["angry", "frustrated", "neutral", "happy"]:
        sentiment = "neutral"

    return {**state, "sentiment": sentiment}

# ── NODE 3 — Determine priority ───────────────────────────────
def determine_priority(state: TicketState) -> TicketState:
    # Rule based priority logic
    priority = "normal"

    if state["sentiment"] == "angry":
        priority = "urgent"
    elif state["sentiment"] == "frustrated" and state["category"] == "billing":
        priority = "high"
    elif state["category"] == "bug":
        priority = "high"
    elif state["sentiment"] == "frustrated":
        priority = "high"
    elif state["category"] == "billing":
        priority = "normal"
    else:
        priority = "low"

    return {**state, "priority": priority}

# ── NODE 4 — Decide escalation ────────────────────────────────
def decide_escalation(state: TicketState) -> TicketState:
    escalate = False
    reason = ""

    if state["sentiment"] == "angry":
        escalate = True
        reason = "Customer is angry — needs human empathy"
    elif state["priority"] == "urgent":
        escalate = True
        reason = "Urgent priority — immediate human attention needed"
    elif state["category"] == "billing" and state["sentiment"] == "frustrated":
        escalate = True
        reason = "Frustrated billing issue — risk of churn"

    return {**state, "escalate": escalate, "escalation_reason": reason}

# ── NODE 5a — Draft normal reply ──────────────────────────────
def draft_reply(state: TicketState) -> TicketState:
    prompt = ChatPromptTemplate.from_template("""
You are a professional customer support agent.

Write a helpful, empathetic reply to this support ticket.

Ticket: {ticket}
Category: {category}
Customer sentiment: {sentiment}

RULES:
- Be warm and professional
- Acknowledge their issue first
- Provide clear next steps
- Keep it under 150 words
- Do not make promises you cannot keep

REPLY:
""")
    chain = prompt | llm | StrOutputParser()
    reply = chain.invoke({
        "ticket": state["ticket"],
        "category": state["category"],
        "sentiment": state["sentiment"]
    })
    return {**state, "draft_reply": reply}

# ── NODE 5b — Draft escalation reply ─────────────────────────
def draft_escalation_reply(state: TicketState) -> TicketState:
    prompt = ChatPromptTemplate.from_template("""
You are a senior customer support agent handling an escalated ticket.

Write an empathetic reply that acknowledges urgency and assures human follow-up.

Ticket: {ticket}
Category: {category}
Sentiment: {sentiment}
Escalation reason: {escalation_reason}

RULES:
- Show strong empathy and understanding
- Acknowledge their frustration directly
- Assure them a senior agent will follow up within 2 hours
- Keep it under 150 words
- Be warm, not robotic

REPLY:
""")
    chain = prompt | llm | StrOutputParser()
    reply = chain.invoke({
        "ticket": state["ticket"],
        "category": state["category"],
        "sentiment": state["sentiment"],
        "escalation_reason": state["escalation_reason"]
    })
    return {**state, "draft_reply": reply}

# ── ROUTING — decide which node comes after escalation check ──
def route_after_escalation(state: TicketState) -> Literal["draft_reply", "draft_escalation_reply"]:
    if state["escalate"]:
        return "draft_escalation_reply"
    return "draft_reply"

# ── BUILD THE GRAPH ───────────────────────────────────────────
def build_graph():
    graph = StateGraph(TicketState)

    # Add all nodes
    graph.add_node("classify_ticket",        classify_ticket)
    graph.add_node("detect_sentiment",       detect_sentiment)
    graph.add_node("determine_priority",     determine_priority)
    graph.add_node("decide_escalation",      decide_escalation)
    graph.add_node("draft_reply",            draft_reply)
    graph.add_node("draft_escalation_reply", draft_escalation_reply)

    # Add edges — define the flow
    graph.set_entry_point("classify_ticket")
    graph.add_edge("classify_ticket",    "detect_sentiment")
    graph.add_edge("detect_sentiment",   "determine_priority")
    graph.add_edge("determine_priority", "decide_escalation")

    # Conditional edge — branches based on escalation decision
    graph.add_conditional_edges(
        "decide_escalation",
        route_after_escalation,
        {
            "draft_reply":            "draft_reply",
            "draft_escalation_reply": "draft_escalation_reply"
        }
    )

    # Both reply nodes end the workflow
    graph.add_edge("draft_reply",            END)
    graph.add_edge("draft_escalation_reply", END)

    return graph.compile()

# ── Main function to process a ticket ────────────────────────
def process_ticket(ticket_text: str) -> TicketState:
    graph = build_graph()

    initial_state: TicketState = {
        "ticket": ticket_text,
        "category": "",
        "sentiment": "",
        "priority": "",
        "draft_reply": "",
        "escalate": False,
        "escalation_reason": ""
    }

    result = graph.invoke(initial_state)
    return result

# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    test_ticket = """
    I have been charged TWICE for my subscription this month!
    This is completely unacceptable. I want my money back NOW.
    If this isn't resolved today I'm cancelling and disputing
    the charge with my bank!
    """

    print("🎫 Processing ticket...")
    result = process_ticket(test_ticket)

    print(f"\n📋 Category:  {result['category']}")
    print(f"😤 Sentiment: {result['sentiment']}")
    print(f"⚡ Priority:  {result['priority']}")
    print(f"🚨 Escalate:  {result['escalate']}")
    print(f"📌 Reason:    {result['escalation_reason']}")
    print(f"\n📝 Draft Reply:\n{result['draft_reply']}")
"""
```

---

## ▶️ Test the Core Logic First
```
cd C:\AI_Projects\support_copilot
python support_agent.py
```

---

## 🧠 LangGraph Flow Visualised
```
START
  ↓
classify_ticket      ← Node 1: bug/billing/feature/general
  ↓
detect_sentiment     ← Node 2: angry/frustrated/neutral/happy
  ↓
determine_priority   ← Node 3: urgent/high/normal/low
  ↓
decide_escalation    ← Node 4: should human review?
  ↓
  ├── YES → draft_escalation_reply  ← empathetic urgent reply
  └── NO  → draft_reply             ← normal helpful reply
                ↓
              END
"""