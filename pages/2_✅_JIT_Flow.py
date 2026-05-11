from __future__ import annotations

import re
from datetime import UTC, datetime

import streamlit as st

from src.personas import agent, app as app_persona, human
from src.ui_theme import apply_security_theme, end_glass_card, render_kicker, start_glass_card, status_chip, timer_badge

st.set_page_config(page_title="JIT Flow", page_icon="✅", layout="wide")
apply_security_theme()

vault = st.session_state.get("vault")
db_proxy = st.session_state.get("db_proxy")
actor = st.session_state.get("actor", "alice@corp")
if vault is None or db_proxy is None:
    st.error("Session is not initialized. Open app.py first.")
    st.stop()

st.title("✅ JIT Flow: Request → Use → Revoke")
st.caption(f"Current actor from sidebar: {actor}")
render_kicker("Ephemeral Access Lifecycle")

active_leases = vault.list_active_leases()
if active_leases:
    start_glass_card()
    st.markdown(f"### Live Lease Timers {status_chip(f'{len(active_leases)} Active', 'warning')}", unsafe_allow_html=True)
    for lease in active_leases:
        st.markdown(
            timer_badge(f"{lease.subject} • {lease.policy_name}", f"{lease.seconds_remaining:.1f}s"),
            unsafe_allow_html=True,
        )
    end_glass_card()
else:
    st.info("No active lease timers yet. Run a scenario to issue a lease.")


def _render_stream(events: list[dict]) -> None:
    prefix_pattern = re.compile(r"^[^\w\[]+\s*")

    def _sanitize_text(raw_text: str) -> str:
        # Remove decorative emoji/symbol prefixes from persona output.
        return prefix_pattern.sub("", raw_text).strip()

    lines: list[str] = []
    for event in events:
        kind = event.get("kind", "result")
        label = {
            "thought": "[THINK]",
            "action": "[ACTION]",
            "result": "[OK]",
            "error": "[ERROR]",
        }.get(kind, "[INFO]")
        text = _sanitize_text(str(event.get("text", "")))
        lines.append(f"{label} {text}")
    st.markdown("\n\n".join(lines))


def _post_summary(start_time: datetime) -> None:
    events = [e for e in vault.audit_log.tail(200) if e.timestamp >= start_time]
    lease_granted = [e for e in events if e.action == "lease_granted"]
    lease_revoked = [e for e in events if e.action == "lease_revoked"]
    access_events = [e for e in events if e.action in {"access_granted", "access_denied"}]

    st.markdown("### Scenario Summary")
    if lease_granted:
        grant = lease_granted[0]
        matching_revoke = next((e for e in lease_revoked if e.lease_id == grant.lease_id), None)
        if matching_revoke is not None:
            duration = (matching_revoke.timestamp - grant.timestamp).total_seconds()
            st.write(f"Lease lifetime: {grant.timestamp.isoformat()} → {matching_revoke.timestamp.isoformat()} ({duration:.1f}s)")
            st.markdown(timer_badge("Lease Lifetime", f"{duration:.1f}s"), unsafe_allow_html=True)
        else:
            st.write(f"Lease granted at {grant.timestamp.isoformat()} (not yet revoked)")
            active_lease = next((lease for lease in vault.list_active_leases() if lease.id == grant.lease_id), None)
            if active_lease is not None:
                st.markdown(
                    timer_badge("Time Remaining", f"{active_lease.seconds_remaining:.1f}s"),
                    unsafe_allow_html=True,
                )

    st.write(f"Ops performed (audit events): {len(access_events)}")
    st.write(f"Audit events emitted this run: {len(events)}")


with st.sidebar:
    st.markdown("### Leak Window Comparison")
    st.info("If this token leaked at T+5s, it stops working when the lease expires or is revoked.")
    st.warning("Compare with Standing Access: leaked static password still works years later.")

human_tab, app_tab, agent_tab = st.tabs(["Human", "App", "Agent"])

with human_tab:
    start_glass_card()
    st.subheader("Human Persona")
    policy_name = st.selectbox("Policy", ["customer-readonly", "customer-writer", "customer-admin"], key="human_policy")
    task = st.text_input("Task", value="Investigate customer balances", key="human_task")
    if st.button("Run Human Scenario", key="run_human"):
        log = st.empty()
        events: list[dict] = []
        started = datetime.now(UTC)
        for event in human.run(
            vault=vault,
            db_proxy=db_proxy,
            subject=actor,
            policy_name=policy_name,
            task_description=task,
            think_delay=0.4,
        ):
            events.append(event)
            with log.container():
                _render_stream(events)
        _post_summary(started)
        st.markdown(
            f"Run Status {status_chip('Completed', 'success')}",
            unsafe_allow_html=True,
        )
    end_glass_card()

with app_tab:
    start_glass_card()
    st.subheader("App Persona (Nightly Batch)")
    if st.button("Run App Scenario", key="run_app"):
        log = st.empty()
        events: list[dict] = []
        started = datetime.now(UTC)
        for event in app_persona.run(vault=vault, db_proxy=db_proxy, think_delay=0.4):
            events.append(event)
            with log.container():
                _render_stream(events)
        _post_summary(started)
        st.markdown(
            f"Run Status {status_chip('Completed', 'success')}",
            unsafe_allow_html=True,
        )
    end_glass_card()

with agent_tab:
    start_glass_card()
    st.subheader("Agent Persona")
    mode = st.radio("Mode", ["Happy Path", "Denial Path"], horizontal=True)
    if st.button("Run Agent Scenario", key="run_agent"):
        log = st.empty()
        events: list[dict] = []
        started = datetime.now(UTC)
        runner = agent.run_happy_path if mode == "Happy Path" else agent.run_denial_path
        for event in runner(vault=vault, db_proxy=db_proxy, think_delay=0.4):
            events.append(event)
            with log.container():
                _render_stream(events)
        _post_summary(started)
        chip = status_chip("Policy Denied", "error") if mode == "Denial Path" else status_chip("Authorized", "success")
        st.markdown(f"Run Status {chip}", unsafe_allow_html=True)
    end_glass_card()
