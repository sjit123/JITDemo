from __future__ import annotations

import streamlit as st

from src.ui_theme import apply_security_theme, end_glass_card, start_glass_card, status_chip

st.set_page_config(page_title="Standing Access", page_icon="⚠️", layout="wide")
apply_security_theme()

vault = st.session_state.get("vault")
conn = st.session_state.get("db_conn")
if vault is None or conn is None:
    st.error("Session is not initialized. Open app.py first.")
    st.stop()

st.title("⚠️ Standing Access: Credential Leak Blast Radius")

start_glass_card()
st.markdown("### Hardcoded credential (anti-pattern)")
DB_PASSWORD = "supersecret"
st.code('DB_PASSWORD = "supersecret"', language="python")

st.caption("In this baseline simulation, this static credential never rotates and never expires.")

if st.button("Simulate credential leak at T+0"):
    st.session_state["standing_leak_started"] = True

if not st.session_state.get("standing_leak_started", False):
    st.warning("Click 'Simulate credential leak at T+0' to begin.")
    end_glass_card()
    st.stop()


def _standing_access_query(password: str) -> int:
    if password != DB_PASSWORD:
        raise ValueError("invalid password")
    cursor = conn.execute("SELECT COUNT(*) AS count FROM customers")
    row = cursor.fetchone()
    return int(row[0])


days_since_leak = st.slider("Days since leak", min_value=0, max_value=3650, value=30, step=1)
st.write(f"Days since leak: {days_since_leak}")

try:
    row_count = _standing_access_query(DB_PASSWORD)
    st.success(f"✅ Credential still works after {days_since_leak} days")
    st.write(f"Query succeeded. Retrieved customer count: {row_count}")
    st.markdown(
        f"Operational Status {status_chip('Standing Access Active', 'warning')}",
        unsafe_allow_html=True,
    )
except Exception as exc:  # noqa: BLE001
    st.error(f"Query failed: {exc}")

st.error("Blast radius is unbounded: leak once, compromise forever.")
end_glass_card()
