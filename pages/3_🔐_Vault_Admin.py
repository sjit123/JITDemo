from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from src.ui_theme import apply_security_theme, end_glass_card, pulse_chip, render_kicker, start_glass_card, status_chip

st.set_page_config(page_title="Vault Admin", page_icon="🔐", layout="wide")
apply_security_theme()

vault = st.session_state.get("vault")
actor = st.session_state.get("actor", "alice@corp")
if vault is None:
    st.error("Session is not initialized. Open app.py first.")
    st.stop()

st.title("🔐 Vault Admin")
render_kicker("Operational Controls")

if st.button("🔄 Refresh"):
    st.rerun()

start_glass_card()
st.markdown("### Policies")
policies = vault.list_policies()
policies_df = pd.DataFrame(
    [
        {
            "name": p.name,
            "description": p.description,
            "allowed_ops": ", ".join(sorted(p.allowed_ops)),
            "allowed_tables": ", ".join(sorted(p.allowed_tables)),
            "max_ttl_seconds": p.max_ttl_seconds,
            "requires_approval": p.requires_approval,
        }
        for p in policies
    ]
)
st.dataframe(policies_df, use_container_width=True)
end_glass_card()

start_glass_card()
st.markdown("### Active Leases")
active = vault.list_active_leases()
active_df = pd.DataFrame(
    [
        {
            "lease_id": str(lease.id),
            "subject": lease.subject,
            "policy": lease.policy_name,
            "granted_at": lease.granted_at.isoformat(),
            "expires_at": lease.expires_at.isoformat(),
            "seconds_remaining": round(max(0.0, (lease.expires_at - datetime.now(UTC)).total_seconds()), 1),
        }
        for lease in active
    ]
)

if active_df.empty:
    st.info("No active leases.")
    st.markdown(f"Lease State {status_chip('Idle', 'info')}", unsafe_allow_html=True)
else:
    st.dataframe(active_df, use_container_width=True)
    st.markdown(f"Lease State {status_chip('Live Leases', 'warning')}", unsafe_allow_html=True)
    st.markdown("#### Revoke Lease")
    for lease in active:
        col1, col2 = st.columns([3, 1])
        with col1:
            tone = "error" if lease.seconds_remaining <= 10 else "warning" if lease.seconds_remaining <= 30 else "success"
            st.markdown(
                (
                    f"{lease.subject} • {lease.policy_name} "
                    f"{pulse_chip(f'{lease.seconds_remaining:.1f}s remaining', tone)}"
                ),
                unsafe_allow_html=True,
            )
        with col2:
            if st.button("Revoke", key=f"revoke_{lease.id}"):
                vault.revoke(lease.id, reason="manual")
                st.success(f"Revoked lease {lease.id}")
                st.rerun()
end_glass_card()

start_glass_card()
st.markdown("### Manual Lease Creation")
with st.form("manual_lease"):
    subject = st.text_input("Subject", value=actor)
    policy_name = st.selectbox(
        "Policy",
        [p.name for p in policies],
        index=0,
    )
    ttl = st.slider("TTL (seconds)", min_value=10, max_value=300, value=30, step=5)
    submitted = st.form_submit_button("Grant Lease")

if submitted:
    token, lease = vault.request_lease(subject=subject, policy_name=policy_name, requested_ttl=ttl)
    st.success(f"Granted lease {lease.id} for {subject}")
    st.code(token, language="text")
    st.markdown(f"Grant Result {status_chip('Issued', 'success')}", unsafe_allow_html=True)
end_glass_card()
