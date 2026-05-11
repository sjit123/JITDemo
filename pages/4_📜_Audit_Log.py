from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.ui_theme import apply_security_theme, end_glass_card, render_kicker, start_glass_card, status_chip

st.set_page_config(page_title="Audit Log", page_icon="📜", layout="wide")
apply_security_theme()

vault = st.session_state.get("vault")
if vault is None:
    st.error("Session is not initialized. Open app.py first.")
    st.stop()

st.title("📜 Audit Log")
render_kicker("Traceability and Forensics")

if st.button("🔄 Refresh"):
    st.rerun()

events = list(reversed(vault.audit_log.tail(1000)))

if not events:
    st.info("No audit events yet.")
    st.stop()

start_glass_card()

rows = [
    {
        "timestamp": event.timestamp.isoformat(),
        "actor": event.actor,
        "action": event.action,
        "resource": event.resource,
        "outcome": event.outcome,
        "lease_id": str(event.lease_id) if event.lease_id else "",
        "details": json.dumps(event.details),
    }
    for event in events
]
df = pd.DataFrame(rows)

actor_options = ["All"] + sorted(df["actor"].dropna().unique().tolist())
action_options = ["All"] + sorted(df["action"].dropna().unique().tolist())
outcome_options = ["All"] + sorted(df["outcome"].dropna().unique().tolist())

col1, col2, col3 = st.columns(3)
with col1:
    actor_filter = st.selectbox("Filter actor", actor_options)
with col2:
    action_filter = st.selectbox("Filter action", action_options)
with col3:
    outcome_filter = st.selectbox("Filter outcome", outcome_options)

if actor_filter != "All":
    df = df[df["actor"] == actor_filter]
if action_filter != "All":
    df = df[df["action"] == action_filter]
if outcome_filter != "All":
    df = df[df["outcome"] == outcome_filter]

st.markdown(f"Filter State {status_chip(f'{len(df)} Events', 'info')}", unsafe_allow_html=True)


def _style_rows(row: pd.Series) -> list[str]:
    if row["action"] == "lease_expired":
        return ["background-color: #222a3d; color: #dae2fd"] * len(row)
    if row["outcome"] == "success":
        return ["background-color: #123128; color: #dae2fd"] * len(row)
    if row["outcome"] == "denied":
        return ["background-color: #3a1820; color: #dae2fd"] * len(row)
    return [""] * len(row)

styled = df.style.apply(_style_rows, axis=1)
st.dataframe(styled, use_container_width=True)

st.download_button(
    "Export filtered events as JSON",
    data=df.to_json(orient="records", indent=2),
    file_name="audit_events.json",
    mime="application/json",
)
st.markdown(f"Export {status_chip('Ready', 'success')}", unsafe_allow_html=True)
end_glass_card()
