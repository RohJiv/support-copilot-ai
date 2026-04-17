# app.py — AI Customer Support Copilot (Complete Final Version)

import streamlit as st
from support_agent import process_ticket

# Works locally (from .env) AND on Railway (from environment variables)
def get_api_key():
    # Try Streamlit secrets first (production)
    try:
        return st.secrets["GROQ_API_KEY"]
    except:
        # Fall back to .env (local development)
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("GROQ_API_KEY")

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="🎧 Support Copilot",
    page_icon="🎧",
    layout="wide"
)

# ── Initialize session state ──────────────────────────────────
if "history" not in st.session_state:
    st.session_state["history"] = []

if "loaded_ticket" not in st.session_state:
    st.session_state["loaded_ticket"] = ""

# ── Global maps — used everywhere ────────────────────────────
priority_colors = {
    "urgent": "🔴",
    "high":   "🟠",
    "normal": "🟡",
    "low":    "🟢"
}

sentiment_emoji = {
    "angry":      "😡",
    "frustrated": "😤",
    "neutral":    "😐",
    "happy":      "😊"
}

category_emoji = {
    "bug":     "🐛",
    "billing": "💳",
    "feature": "💡",
    "general": "💬"
}

# ── Sample tickets ────────────────────────────────────────────
SAMPLE_TICKETS = {
    "😡 Angry Billing":
        "I've been charged TWICE this month! This is theft! "
        "Fix it NOW or I'm disputing with my bank and leaving a 1-star review everywhere!",

    "🐛 Bug Report":
        "Hi, the export button in the dashboard stopped working since yesterday's update. "
        "I'm getting a 500 error. Please fix this ASAP as I need to export my reports.",

    "💡 Feature Request":
        "Hello, it would be really helpful if you could add dark mode to the app. "
        "Many of us work late and the bright screen is tiring. Would love to see this!",

    "😤 Frustrated Billing":
        "I cancelled my subscription 2 weeks ago but I was still charged. "
        "I have the cancellation email. Please refund me. This is very disappointing.",

    "😊 Happy Customer":
        "Just wanted to say your support team has been amazing! "
        "Quick question — can you help me understand how to use the API integration?"
}

# ── Title ─────────────────────────────────────────────────────
st.title("🎧 AI Customer Support Copilot")
st.caption("Paste any support ticket — AI classifies, prioritises and drafts a reply instantly")

# ── Two column layout ─────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

# ── LEFT COLUMN — Ticket Input ────────────────────────────────
with col_left:
    st.subheader("📥 Support Ticket")

    # Sample ticket buttons
    st.caption("Quick load a sample ticket:")
    btn_cols = st.columns(len(SAMPLE_TICKETS))
    for i, (label, ticket) in enumerate(SAMPLE_TICKETS.items()):
        if btn_cols[i].button(label, use_container_width=True):
            st.session_state["loaded_ticket"] = ticket
            st.rerun()

    st.divider()

    # Ticket text area
    ticket_text = st.text_area(
        "ticket_input",
        value=st.session_state["loaded_ticket"],
        height=200,
        placeholder="Paste customer support ticket here...",
        label_visibility="collapsed"
    )

    # Process button
    process_btn = st.button(
        "🚀 Process Ticket",
        type="primary",
        use_container_width=True
    )

# ── RIGHT COLUMN — AI Analysis ────────────────────────────────
with col_right:
    st.subheader("🤖 AI Analysis")

    if process_btn and ticket_text:

        with st.spinner("🔄 Processing through AI workflow..."):
            result = process_ticket(ticket_text)

        # Save to history
        st.session_state["history"].append(result)

        # Metrics row
        m1, m2, m3 = st.columns(3)

        with m1:
            cat = result["category"]
            st.metric(
                "Category",
                f"{category_emoji.get(cat, '📌')} {cat.title()}"
            )

        with m2:
            sent = result["sentiment"]
            st.metric(
                "Sentiment",
                f"{sentiment_emoji.get(sent, '😐')} {sent.title()}"
            )

        with m3:
            pri = result["priority"]
            st.metric(
                "Priority",
                f"{priority_colors.get(pri, '⚪')} {pri.title()}"
            )

        st.divider()

        # Escalation alert
        if result["escalate"]:
            st.error(
                f"🚨 **ESCALATE TO HUMAN AGENT**\n\n"
                f"{result['escalation_reason']}"
            )
        else:
            st.success("✅ **AI can handle this — no escalation needed**")

        st.divider()

        # Draft reply
        st.markdown("**📝 Draft Reply:**")
        st.text_area(
            "draft_reply",
            value=result["draft_reply"],
            height=220,
            label_visibility="collapsed"
        )

        # Action buttons
        c1, c2 = st.columns(2)
        with c1:
            st.button(
                "✅ Approve & Send",
                type="primary",
                use_container_width=True
            )
        with c2:
            st.button(
                "✏️ Edit Before Sending",
                use_container_width=True
            )

    elif process_btn and not ticket_text:
        st.warning("⚠️ Please paste a support ticket first")

    else:
        st.info("👈 Paste a ticket and click 'Process Ticket' to see AI analysis")

# ── Ticket History ────────────────────────────────────────────
if st.session_state["history"]:
    st.divider()
    st.subheader(
        f"📜 Processed Tickets — "
        f"{len(st.session_state['history'])} total"
    )

    # Summary stats
    s1, s2, s3, s4 = st.columns(4)

    total     = len(st.session_state["history"])
    escalated = sum(1 for t in st.session_state["history"] if t["escalate"])
    handled   = total - escalated
    urgent    = sum(1 for t in st.session_state["history"] if t["priority"] == "urgent")

    s1.metric("📊 Total",       total)
    s2.metric("🚨 Escalated",   escalated)
    s3.metric("✅ Auto Handled", handled)
    s4.metric("🔴 Urgent",      urgent)

    st.divider()

    # Ticket history list
    for i, ticket in enumerate(reversed(st.session_state["history"])):
        ticket_num = len(st.session_state["history"]) - i
        cat        = ticket["category"]
        pri        = ticket["priority"]
        escalated  = ticket["escalate"]

        with st.expander(
            f"Ticket #{ticket_num} | "
            f"{category_emoji.get(cat, '📌')} {cat.title()} | "
            f"{priority_colors.get(pri, '⚪')} {pri.title()} | "
            f"{'🚨 Escalated' if escalated else '✅ Auto handled'}"
        ):
            st.markdown("**Original Ticket:**")
            st.info(ticket["ticket"])

            st.markdown("**Draft Reply:**")
            st.success(ticket["draft_reply"])

            # Show all details
            d1, d2, d3 = st.columns(3)
            d1.metric("Category",  ticket["category"].title())
            d2.metric("Sentiment", ticket["sentiment"].title())
            d3.metric("Priority",  ticket["priority"].title())

            if ticket["escalation_reason"]:
                st.error(f"🚨 {ticket['escalation_reason']}")
"""```

---

Save (`Ctrl+S`) and run:
```
streamlit run app.py
"""