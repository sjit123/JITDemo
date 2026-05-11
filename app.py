from __future__ import annotations

import logging
import sqlite3

import streamlit as st

from src.db_proxy import DBProxy
from src.seed import seed_db, seed_policies
from src.ui_theme import apply_security_theme, end_glass_card, render_kicker, start_glass_card, status_chip
from src.vault import MiniVault

ACTOR_OPTIONS = ["alice@corp", "bob@corp", "etl-job", "research-agent"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

st.set_page_config(page_title="JIT Access Demo", page_icon="🔐", layout="wide")
apply_security_theme()

# Critical guard: initialize exactly once per Streamlit session.
if "vault" not in st.session_state:
    vault = MiniVault()
    seed_policies(vault)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    seed_db(conn)

    vault.lease_manager.start_sweeper(interval=1.0)

    st.session_state["vault"] = vault
    st.session_state["db_conn"] = conn
    st.session_state["db_proxy"] = DBProxy(conn, vault)

if "actor" not in st.session_state:
    st.session_state["actor"] = ACTOR_OPTIONS[0]

with st.sidebar:
    st.header("Demo Actor")
    st.session_state["actor"] = st.selectbox(
        "Who is acting right now?",
        options=ACTOR_OPTIONS,
        index=ACTOR_OPTIONS.index(st.session_state["actor"]),
    )

st.title("JIT Access Demo")
st.subheader("Just-in-Time access vs standing credentials")

render_kicker("Security Operations Simulation")

start_glass_card()
st.markdown(
    """
This demo makes three ideas visible in minutes:

1. A leaked standing credential stays dangerous forever.
2. JIT access can be requested, granted, used, and revoked autonomously.
3. Every grant, use, denial, revocation, and expiry is auditable.
"""
)
end_glass_card()

st.markdown(f"### Start Here {status_chip('Guided Flow', 'info')}", unsafe_allow_html=True)
st.page_link("pages/1_⚠️_Standing_Access.py", label="⚠️ Standing Access")
st.page_link("pages/2_✅_JIT_Flow.py", label="✅ JIT Flow")
st.page_link("pages/3_🔐_Vault_Admin.py", label="🔐 Vault Admin")
st.page_link("pages/4_📜_Audit_Log.py", label="📜 Audit Log")

st.info(
    "Tip: Run Standing Access first, then JIT Flow, then revoke a live lease in Vault Admin and watch Audit Log update."
)
