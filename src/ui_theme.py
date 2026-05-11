from __future__ import annotations

import streamlit as st


def apply_security_theme() -> None:
    """Apply a high-fidelity security-operations visual theme to Streamlit pages."""
    st.markdown(
        """
<style>
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1200px 700px at 0% 0%, #1a2340 0%, rgba(26, 35, 64, 0) 60%),
        radial-gradient(900px 600px at 100% 0%, #12243f 0%, rgba(18, 36, 63, 0) 62%),
        linear-gradient(160deg, #060e20 0%, #0b1326 35%, #131b2e 100%);
    color: #dae2fd;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #060e20 0%, #131b2e 100%);
    border-right: 1px solid #414755;
}

[data-testid="stSidebarNav"] a {
    border-radius: 10px;
}

[data-testid="stSidebarNav"] [aria-current="page"] {
    background: rgba(75, 142, 255, 0.16);
    border: 1px solid rgba(75, 142, 255, 0.45);
}

h1, h2, h3, h4, h5, h6,
p, li, label, span, div {
    color: #dae2fd;
}

h1 {
    letter-spacing: -0.02em;
}

a {
    color: #adc6ff;
}

[data-baseweb="input"],
[data-baseweb="select"],
[data-baseweb="textarea"],
.stTextInput > div > div,
.stSelectbox > div > div,
.stTextArea > div > div,
.stMultiSelect > div > div {
    background: rgba(23, 31, 51, 0.7);
    border: 1px solid #414755;
    border-radius: 10px;
}

.stTabs [role="tablist"] {
    gap: 8px;
}

.stTabs [role="tab"] {
    background: rgba(23, 31, 51, 0.65);
    border: 1px solid #414755;
    border-radius: 10px;
    text-decoration: none !important;
    box-shadow: none;
}

.stTabs [aria-selected="true"] {
    border-color: #4b8eff;
    box-shadow: inset 0 0 0 1px rgba(75, 142, 255, 0.4);
}

.stTabs [aria-selected="true"]::after {
    content: none !important;
}

[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {
    background: #2f6ed8;
    color: #eaf1ff;
    border: 1px solid rgba(173, 198, 255, 0.4);
    border-radius: 10px;
    box-shadow: none;
}

[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover {
    border-color: rgba(173, 198, 255, 0.65);
    background: #3d7af0;
    box-shadow: none;
}

[data-testid="stCodeBlock"] {
    background: rgba(6, 14, 32, 0.85);
    border: 1px solid #414755;
    border-radius: 12px;
}

[data-testid="stAlert"] {
    border-radius: 12px;
    border: 1px solid rgba(173, 198, 255, 0.3);
    background: rgba(23, 31, 51, 0.7);
}

.glass-card {
    background: linear-gradient(180deg, rgba(23, 31, 51, 0.8) 0%, rgba(19, 27, 46, 0.8) 100%);
    border: 1px solid rgba(139, 144, 160, 0.35);
    border-radius: 14px;
    padding: 14px 16px;
    margin: 10px 0 14px;
    box-shadow: 0 0 20px rgba(9, 18, 36, 0.35);
}

.kicker {
    color: #adc6ff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 2px;
}

.status-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 9999px;
    border: 1px solid transparent;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.03em;
    margin-left: 8px;
    vertical-align: middle;
}

@keyframes chipPulse {
    0% {
        box-shadow: 0 0 0 rgba(75, 142, 255, 0.0);
        transform: translateY(0);
    }
    50% {
        box-shadow: 0 0 14px rgba(75, 142, 255, 0.4);
        transform: translateY(-1px);
    }
    100% {
        box-shadow: 0 0 0 rgba(75, 142, 255, 0.0);
        transform: translateY(0);
    }
}

.status-chip--success {
    background: rgba(0, 165, 114, 0.2);
    color: #6ffbbe;
    border-color: rgba(78, 222, 163, 0.45);
}

.status-chip--warning {
    background: rgba(255, 183, 77, 0.18);
    color: #ffd48a;
    border-color: rgba(255, 183, 77, 0.45);
}

.status-chip--error {
    background: rgba(147, 0, 10, 0.35);
    color: #ffdad6;
    border-color: rgba(255, 180, 171, 0.4);
}

.status-chip--info {
    background: rgba(75, 142, 255, 0.2);
    color: #d8e2ff;
    border-color: rgba(173, 198, 255, 0.45);
}

.status-chip--pulse {
    animation: chipPulse 1.8s ease-in-out infinite;
}

.timer-badge {
    display: inline-flex;
    gap: 8px;
    align-items: center;
    border-radius: 10px;
    border: 1px solid rgba(173, 198, 255, 0.45);
    background: rgba(75, 142, 255, 0.16);
    padding: 4px 10px;
    margin: 6px 0 4px;
}

.timer-badge-row {
    margin: 6px 0;
}

.timer-badge__label {
    color: #c1c6d7;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
}

.timer-badge__value {
    color: #e1e0ff;
    font-family: "JetBrains Mono", monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.02em;
}

[data-testid="stDataFrame"] {
    border: 1px solid #414755;
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="stSlider"] [role="slider"] {
    box-shadow: 0 0 10px rgba(75, 142, 255, 0.6);
}

small,
[data-testid="stCaptionContainer"] {
    color: #c1c6d7;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_kicker(text: str) -> None:
    st.markdown(f'<div class="kicker">{text}</div>', unsafe_allow_html=True)


def start_glass_card() -> None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)


def end_glass_card() -> None:
    st.markdown('</div>', unsafe_allow_html=True)


def status_chip(text: str, tone: str = "info") -> str:
    safe_tone = tone if tone in {"success", "warning", "error", "info"} else "info"
    return f'<span class="status-chip status-chip--{safe_tone}">{text}</span>'


def pulse_chip(text: str, tone: str = "info") -> str:
    safe_tone = tone if tone in {"success", "warning", "error", "info"} else "info"
    return f'<span class="status-chip status-chip--{safe_tone} status-chip--pulse">{text}</span>'


def timer_badge(label: str, value: str) -> str:
    return (
        '<div class="timer-badge-row">'
        '<span class="timer-badge">'
        f'<span class="timer-badge__label">{label}</span>'
        f'<span class="timer-badge__value">{value}</span>'
        "</span>"
        "</div>"
    )