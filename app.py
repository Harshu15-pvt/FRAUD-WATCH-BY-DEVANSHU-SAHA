"""
FRAUDWATCH — Insurance Fraud Intelligence Command Center
"Nebula Risk Intelligence" — Internal Assessment 2, InsurTech & Digital Risk Solutions
Devanshu Saha | 25WU0203008 | MBA Financial Services

ARCHITECTURE NOTES
-------------------
Every major visualization in this dashboard is REAL WebGL 3D, built with a
locally-bundled copy of Three.js (static/three.min.js — no CDN, works fully
offline). Streamlit cannot execute <script> tags inserted through
st.markdown, and a components.html iframe cannot resolve relative
<script src="..."> paths against the app's working directory (its document
has no such base). So the only way to "load Three.js locally" inside a
Streamlit-rendered scene is to read the local file's bytes in Python and
inline them into the iframe's HTML at render time — that is what
webgl_component() below does. The file still lives on disk at
static/three.min.js (inspectable, swappable, versioned normally); Python
just has to hand its contents to the iframe itself.

Every scene is wrapped in a WebGL-capability check and a JS try/catch (see
static/harness.js: bootstrapScene). If WebGL is unavailable or a render
call throws, the canvas hides and a "VISUAL ENGINE — FALLBACK MODE" panel
appears instead — the dashboard can never go blank because of a 3D
rendering failure.

CAMERA: static/harness.js:CameraRig is a genuine free spherical-orbit
controller (left-drag orbits a full 360 degrees horizontally and nearly
pole-to-pole vertically; right-drag/Shift+drag pans the target; wheel and
pinch zoom; one/two-finger touch does the same) with continuous per-frame
damping — nothing snaps. Every analytical scene gets a floating glass
toolbar (Reset / Fit / Zoom +/- / Front / Back / Left / Right / Top /
Bottom / Isometric / Auto Rotate) wired to that same rig, plus real
raycasting: hovering glows/scales an object, clicking dollies the camera
toward it and opens a detail card built from the exact data passed into
that scene.

HONEST LIMITATION: a literal full-viewport WebGL "wallpaper" sitting
behind every widget (sidebar, KPI cards, panels) is not reliably
achievable from inside a Streamlit-embedded iframe — the iframe only
controls its own box, not the surrounding page. Rather than fake that
claim, the cosmic black-hole/nebula/particle scene is a real, bounded
WebGL panel near the top of Command Center (with mouse parallax and
continuous animation), and the rest of the app uses a CSS starfield for
visual continuity everywhere else.

I cannot execute a browser myself, so unlike the Python code below (which
is exercised by an automated test harness on every change), the Three.js
scenes in static/scenes.js are verified for JS syntax validity only, not
for pixel-correct WebGL output. If a scene ever looks wrong on your
machine, the diagnostic panel and toolbar will tell you what's going on;
every KPI/table number is computed independently of whether the 3D layer
renders at all.
"""

import json
import os
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

# ============================================================================
# 0. CONSTANTS & THEME
# ============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_data_file(filename: str) -> str:
    """Look for a data file in the app folder, then ./data/, then cwd."""
    candidates = [
        os.path.join(BASE_DIR, filename),
        os.path.join(BASE_DIR, "data", filename),
        filename,
        os.path.join("data", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(BASE_DIR, filename)  # default — load_data() will report the miss


CLAIMS_FILE = _find_data_file("claims.csv")
INDICATORS_FILE = _find_data_file("fraud_indicators.csv")

COLORS = {
    "bg_primary": "#05070f",
    "bg_secondary": "#0a0e1f",
    "glass_bg": "rgba(255,255,255,0.045)",
    "glass_border": "rgba(255,255,255,0.10)",
    "royal_blue": "#3b5bfd",
    "electric_blue": "#4cc9f0",
    "violet": "#8b6bf7",
    "cyan": "#22d3ee",
    "teal": "#14b8a6",
    "green": "#3ddc97",
    "gold": "#f5c451",
    "orange": "#ff9f5b",
    "coral": "#ff5c72",
    "text_primary": "#eef1fb",
    "text_secondary": "#9aa3c4",
    "text_muted": "#6b7394",
}

CATEGORY_COLORS = {
    "confirmed": COLORS["coral"],
    "fraud": COLORS["orange"],
    "review": COLORS["gold"],
    "normal": COLORS["cyan"],
}

NAV_ITEMS = [
    ("command_center", "COMMAND CENTER", "\u25c7"),
    ("risk_terrain", "RISK TERRAIN", "\u25c7"),
    ("claim_investigation", "CLAIM INVESTIGATION", "\u25c7"),
    ("fraud_drivers", "FRAUD DRIVERS", "\u25c7"),
    ("analytics", "ANALYTICS", "\u25c7"),
]

FONT_STACK = "Inter, 'Segoe UI', Roboto, Arial, sans-serif"

MAX_SCENE_CLAIMS = 160  # visual sampling cap — calculations always use the full filtered set


# ============================================================================
# 1. PAGE CONFIG & CSS
# ============================================================================

def configure_page():
    st.set_page_config(
        page_title="FRAUDWATCH | Nebula Risk Intelligence",
        page_icon="\U0001f6f0\ufe0f",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css():
    st.markdown(
        """
        <style>
        html, body, [class*="css"], .stApp { font-family: """ + FONT_STACK + """; }

        .stApp {
            background:
                radial-gradient(1.6px 1.6px at 8% 12%, rgba(255,255,255,0.85), transparent),
                radial-gradient(1.2px 1.2px at 22% 38%, rgba(255,255,255,0.65), transparent),
                radial-gradient(1.8px 1.8px at 38% 8%, rgba(255,255,255,0.8), transparent),
                radial-gradient(1.2px 1.2px at 52% 55%, rgba(255,255,255,0.55), transparent),
                radial-gradient(1.6px 1.6px at 68% 22%, rgba(255,255,255,0.75), transparent),
                radial-gradient(1.2px 1.2px at 81% 46%, rgba(255,255,255,0.6), transparent),
                radial-gradient(1.8px 1.8px at 91% 12%, rgba(255,255,255,0.85), transparent),
                radial-gradient(1.2px 1.2px at 14% 72%, rgba(255,255,255,0.55), transparent),
                radial-gradient(1.6px 1.6px at 30% 88%, rgba(255,255,255,0.7), transparent),
                radial-gradient(1.2px 1.2px at 60% 78%, rgba(255,255,255,0.55), transparent),
                radial-gradient(1.8px 1.8px at 85% 82%, rgba(255,255,255,0.75), transparent),
                radial-gradient(ellipse 900px 500px at 12% -8%, rgba(59,91,253,0.20), transparent 60%),
                radial-gradient(ellipse 900px 600px at 100% 0%, rgba(139,107,247,0.16), transparent 55%),
                radial-gradient(ellipse 1200px 700px at 50% 110%, rgba(20,184,166,0.10), transparent 60%),
                linear-gradient(180deg, #05070f 0%, #0a0e1f 100%);
            background-attachment: fixed;
            animation: fw-galaxy-drift 140s linear infinite;
            color: """ + COLORS["text_primary"] + """;
        }
        @keyframes fw-galaxy-drift {
            0% { background-position: 0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0; }
            100% { background-position: -60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,-60px 40px,0 0,0 0,0 0,0 0; }
        }

        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1440px; }

        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(139,107,247,0.35); border-radius: 8px; }

        @keyframes fw-fade-up {
            0% { opacity: 0; transform: translateY(14px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        .fw-hero, .fw-panel, .fw-kpi { animation: fw-fade-up 0.55s ease both; }
        .fw-kpi:nth-of-type(1) { animation-delay: 0.02s; }
        .fw-kpi:nth-of-type(2) { animation-delay: 0.08s; }
        .fw-kpi:nth-of-type(3) { animation-delay: 0.14s; }
        .fw-kpi:nth-of-type(4) { animation-delay: 0.20s; }
        .fw-kpi:nth-of-type(5) { animation-delay: 0.26s; }

        /* ---------- Hero ---------- */
        .fw-hero {
            position: relative; padding: 32px 38px 28px 38px; border-radius: 22px;
            background:
                radial-gradient(circle at 20% 20%, rgba(76,201,240,0.16), transparent 45%),
                radial-gradient(circle at 85% 15%, rgba(139,107,247,0.20), transparent 45%),
                linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015));
            border: 1px solid """ + COLORS["glass_border"] + """;
            box-shadow: 0 24px 70px -24px rgba(59,91,253,0.4), inset 0 1px 0 rgba(255,255,255,0.07);
            overflow: hidden; margin-bottom: 22px; backdrop-filter: blur(6px);
        }
        .fw-eyebrow {
            font-size: 12px; font-weight: 700; letter-spacing: 3px; color: """ + COLORS["electric_blue"] + """;
            text-transform: uppercase; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        }
        .fw-dot {
            width: 7px; height: 7px; border-radius: 50%; display: inline-block;
            background: """ + COLORS["green"] + """; box-shadow: 0 0 12px 2px rgba(61,220,151,0.8);
            animation: fw-pulse 1.8s ease-in-out infinite;
        }
        @keyframes fw-pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.35; transform: scale(1.4); } }
        .fw-title {
            font-size: 48px; font-weight: 800; letter-spacing: 1px; margin: 8px 0 2px 0; line-height: 1.05;
            background: linear-gradient(100deg, #ffffff 10%, """ + COLORS["electric_blue"] + """ 45%, """ + COLORS["violet"] + """ 80%);
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }
        .fw-subtitle {
            font-size: 12.5px; font-weight: 600; letter-spacing: 2.2px; color: """ + COLORS["text_secondary"] + """;
            text-transform: uppercase; margin-top: 6px;
        }
        .fw-divider { height: 1px; margin: 18px 0 14px 0; background: rgba(255,255,255,0.08); }
        .fw-authorbar { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 12px; }
        .fw-author-name { font-size: 15px; font-weight: 700; color: """ + COLORS["text_primary"] + """; }
        .fw-author-role { font-size: 11.5px; color: """ + COLORS["text_muted"] + """; letter-spacing: 0.5px; }
        .fw-status-panel { display: flex; flex-direction: column; gap: 4px; align-items: flex-end; }
        .fw-status-line { font-size: 10px; font-weight: 700; letter-spacing: 1.2px; color: """ + COLORS["text_secondary"] + """; display: flex; align-items: center; gap: 6px; }
        .fw-status-chip { width: 6px; height: 6px; border-radius: 50%; background: """ + COLORS["green"] + """; box-shadow: 0 0 6px 1px rgba(61,220,151,0.7); }

        /* ---------- Navigation — CSS 3D tilt tiles ---------- */
        div[data-testid="column"] { perspective: 900px; }
        div[data-testid="stButton"] button {
            width: 100%; background: """ + COLORS["glass_bg"] + """ !important; border: 1px solid """ + COLORS["glass_border"] + """ !important;
            color: """ + COLORS["text_secondary"] + """ !important; font-weight: 700 !important; font-size: 12px !important;
            letter-spacing: 1.2px !important; text-transform: uppercase; border-radius: 14px !important;
            padding: 13px 6px !important; transition: transform 0.25s cubic-bezier(.2,.8,.3,1), box-shadow 0.25s ease, color 0.2s ease, border-color 0.2s ease !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.05); transform-style: preserve-3d;
        }
        div[data-testid="stButton"] button:hover {
            transform: translateY(-3px) rotateX(8deg) scale(1.02); border-color: rgba(76,201,240,0.6) !important;
            color: """ + COLORS["text_primary"] + """ !important; box-shadow: 0 16px 34px -14px rgba(76,201,240,0.5);
        }
        .fw-nav-glow {
            height: 3px; border-radius: 3px; margin: 5px 8px 0 8px;
            background: linear-gradient(90deg, """ + COLORS["electric_blue"] + """, """ + COLORS["violet"] + """);
            box-shadow: 0 0 12px 1px rgba(76,201,240,0.8); animation: fw-glow-pulse 1.6s ease-in-out infinite;
        }
        @keyframes fw-glow-pulse { 0%,100% { opacity: 0.55; } 50% { opacity: 1; } }

        /* ---------- Glass panel ---------- */
        .fw-panel {
            background: linear-gradient(160deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015));
            border: 1px solid """ + COLORS["glass_border"] + """; border-radius: 18px; padding: 18px 20px;
            backdrop-filter: blur(14px);
            box-shadow: 0 16px 46px -24px rgba(0,0,0,0.65), inset 0 1px 0 rgba(255,255,255,0.05);
            margin-bottom: 18px;
        }
        .fw-panel-title { font-size: 13px; font-weight: 800; letter-spacing: 1.6px; color: """ + COLORS["text_primary"] + """; text-transform: uppercase; margin-bottom: 2px; }
        .fw-panel-sub { font-size: 12px; color: """ + COLORS["text_muted"] + """; margin-bottom: 14px; }

        /* ---------- KPI — CSS 3D glass tilt ---------- */
        .fw-kpi-outer { perspective: 800px; }
        .fw-kpi {
            position: relative; background: linear-gradient(155deg, rgba(255,255,255,0.065), rgba(255,255,255,0.015));
            border: 1px solid """ + COLORS["glass_border"] + """; border-radius: 16px; padding: 17px 16px 15px 16px;
            backdrop-filter: blur(14px); box-shadow: 0 12px 34px -18px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.07);
            transition: transform 0.3s cubic-bezier(.2,.8,.3,1), box-shadow 0.3s ease, border-color 0.3s ease;
            overflow: hidden; min-height: 122px; transform-style: preserve-3d;
        }
        .fw-kpi:hover {
            transform: translateY(-5px) translateZ(6px) rotateX(6deg) rotateY(-4deg);
            border-color: rgba(76,201,240,0.45); box-shadow: 0 22px 50px -18px rgba(76,201,240,0.4);
        }
        .fw-kpi::after {
            content: ""; position: absolute; top: -30%; right: -20%; width: 90px; height: 90px; border-radius: 50%;
            background: radial-gradient(circle, var(--accent, """ + COLORS["electric_blue"] + """) 0%, transparent 70%);
            opacity: 0.22; filter: blur(4px);
        }
        .fw-kpi.fw-risk { animation: fw-fade-up 0.55s ease both, fw-risk-glow 2.4s ease-in-out infinite; }
        @keyframes fw-risk-glow {
            0%,100% { box-shadow: 0 12px 34px -18px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,92,114,0.0); }
            50% { box-shadow: 0 12px 34px -18px rgba(0,0,0,0.75), 0 0 20px 1px rgba(255,92,114,0.32); }
        }
        .fw-kpi-icon { font-size: 15px; margin-bottom: 6px; opacity: 0.85; letter-spacing: 2px; color: """ + COLORS["electric_blue"] + """; }
        .fw-kpi-label { font-size: 10.5px; font-weight: 700; letter-spacing: 1.4px; color: """ + COLORS["text_muted"] + """; text-transform: uppercase; margin-bottom: 7px; }
        .fw-kpi-value { font-size: 28px; font-weight: 800; color: """ + COLORS["text_primary"] + """; line-height: 1.1; margin-bottom: 5px; }
        .fw-kpi-desc { font-size: 11px; color: """ + COLORS["text_muted"] + """; line-height: 1.35; letter-spacing: 0.3px; text-transform: uppercase; }

        .fw-section-label { font-size: 11px; font-weight: 800; letter-spacing: 2.2px; color: """ + COLORS["electric_blue"] + """; text-transform: uppercase; margin: 4px 0 10px 2px; }
        .fw-scene-caption { font-size: 10.5px; color: """ + COLORS["text_muted"] + """; letter-spacing: 0.9px; text-align: center; margin-top: 9px; text-transform: uppercase; }

        .fw-takeaway {
            border-radius: 14px; padding: 13px 16px;
            background: linear-gradient(100deg, rgba(76,201,240,0.09), rgba(139,107,247,0.07));
            border: 1px solid rgba(76,201,240,0.25); border-left: 3px solid """ + COLORS["electric_blue"] + """;
            font-size: 12.8px; line-height: 1.55; color: """ + COLORS["text_secondary"] + """; margin-top: 10px;
        }
        .fw-takeaway b { color: """ + COLORS["text_primary"] + """; }
        .fw-takeaway-label { font-size: 10.5px; font-weight: 800; letter-spacing: 1.6px; color: """ + COLORS["electric_blue"] + """; text-transform: uppercase; margin-bottom: 5px; display: block; }

        /* ---------- Recommendations ---------- */
        .fw-rec { display: flex; gap: 16px; padding: 16px 4px; border-bottom: 1px solid rgba(255,255,255,0.07); }
        .fw-rec:last-child { border-bottom: none; }
        .fw-rec-num { font-size: 26px; font-weight: 800; color: rgba(76,201,240,0.35); min-width: 46px; line-height: 1; }
        .fw-rec-title { font-size: 13.5px; font-weight: 800; color: """ + COLORS["text_primary"] + """; margin-bottom: 8px; }
        .fw-rec-block { font-size: 11px; font-weight: 800; letter-spacing: 1.4px; color: """ + COLORS["electric_blue"] + """; text-transform: uppercase; margin-top: 8px; margin-bottom: 2px; }
        .fw-rec-text { font-size: 12.3px; line-height: 1.55; color: """ + COLORS["text_secondary"] + """; }

        .fw-invest-header {
            display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-radius: 14px;
            background: linear-gradient(100deg, rgba(139,107,247,0.14), rgba(76,201,240,0.09));
            border: 1px solid rgba(139,107,247,0.32); margin-bottom: 16px;
        }
        .fw-pill { display: inline-block; padding: 5px 13px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }

        .fw-mini { background: """ + COLORS["glass_bg"] + """; border: 1px solid """ + COLORS["glass_border"] + """; border-radius: 12px; padding: 12px 14px; text-align: center; }
        .fw-mini-label { font-size: 10px; letter-spacing: 1.2px; color: """ + COLORS["text_muted"] + """; text-transform: uppercase; }
        .fw-mini-value { font-size: 19px; font-weight: 800; color: """ + COLORS["text_primary"] + """; margin-top: 3px; }

        .fw-disclaimer {
            font-size: 10.8px; color: """ + COLORS["text_muted"] + """; line-height: 1.6; text-align: center;
            padding: 14px 20px; border-top: 1px solid """ + COLORS["glass_border"] + """; margin-top: 6px;
        }

        .fw-footer { margin-top: 22px; padding: 18px 10px 8px 10px; text-align: center; border-top: 1px solid """ + COLORS["glass_border"] + """; }
        .fw-footer-brand { font-size: 13px; font-weight: 800; letter-spacing: 2.5px; color: """ + COLORS["text_secondary"] + """; }
        .fw-footer-line { font-size: 11px; color: """ + COLORS["text_muted"] + """; margin-top: 4px; }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(10,14,31,0.92), rgba(5,7,15,0.97));
            border-right: 1px solid """ + COLORS["glass_border"] + """;
        }
        .fw-status-row { display: flex; align-items: center; gap: 7px; font-size: 10.5px; color: """ + COLORS["text_secondary"] + """; margin-bottom: 6px; }
        .fw-status-dot { width: 6px; height: 6px; border-radius: 50%; background: """ + COLORS["green"] + """; box-shadow: 0 0 6px 1px rgba(61,220,151,0.7); flex-shrink: 0; }

        div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid """ + COLORS["glass_border"] + """; }

        /* ---------- Visual Intelligence panel ---------- */
        .fw-vi-panel {
            background: linear-gradient(160deg, rgba(139,107,247,0.07), rgba(76,201,240,0.04));
            border: 1px solid rgba(139,107,247,0.22); border-radius: 16px; padding: 16px 18px; margin-top: 12px;
        }
        .fw-vi-title { font-size: 11.5px; font-weight: 800; letter-spacing: 1.6px; color: """ + COLORS["violet"] + """; text-transform: uppercase; margin-bottom: 12px; }
        .fw-vi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 18px; margin-bottom: 4px; }
        .fw-vi-row { display: flex; flex-direction: column; gap: 2px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }
        .fw-vi-label { font-size: 9.5px; font-weight: 800; letter-spacing: 1px; color: """ + COLORS["text_muted"] + """; text-transform: uppercase; }
        .fw-vi-value { font-size: 12px; color: """ + COLORS["text_secondary"] + """; line-height: 1.4; }
        .fw-vi-block { margin-top: 10px; font-size: 12.3px; line-height: 1.55; color: """ + COLORS["text_secondary"] + """; }
        .fw-vi-block-label { display: block; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; color: """ + COLORS["electric_blue"] + """; text-transform: uppercase; margin-bottom: 4px; }
        .fw-vi-source { margin-top: 10px; font-size: 9.5px; letter-spacing: 0.6px; color: """ + COLORS["text_muted"] + """; text-transform: uppercase; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# 2. STATIC ASSET LOADING (local Three.js — no CDN)
# ============================================================================

@st.cache_data(show_spinner=False)
def load_static_assets():
    static_dir = os.path.join(BASE_DIR, "static")
    paths = {
        "three": os.path.join(static_dir, "three.min.js"),
        "harness": os.path.join(static_dir, "harness.js"),
        "scenes": os.path.join(static_dir, "scenes.js"),
    }
    out = {}
    missing = []
    for key, path in paths.items():
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                out[key] = f.read()
        else:
            out[key] = ""
            missing.append(os.path.relpath(path, BASE_DIR))
    return out, missing


# ============================================================================
# 3. DATA LOADING & CLEANING
# ============================================================================

def _to_numeric_safe(series: pd.Series) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    return out.replace([np.inf, -np.inf], np.nan)


def _clean_str(series: pd.Series) -> pd.Series:
    """Coerce to plain string, turning any NaN/None (including pandas' native
    'str' dtype, which does not auto-stringify missing values) into 'nan'."""
    return series.astype("object").fillna("nan").astype(str).str.strip()


def normalize_fraud_flag(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float) > 0
    s = series.astype("object").fillna("").astype(str).str.strip().str.lower()
    truthy = {"1", "yes", "y", "true", "fraud", "fraudulent"}
    return s.isin(truthy)


@st.cache_data(show_spinner=False)
def load_data():
    try:
        claims = pd.read_csv(CLAIMS_FILE)
    except FileNotFoundError:
        return None, None, "Required data file not found: 'claims.csv' (checked app folder and ./data/)."
    except pd.errors.EmptyDataError:
        return None, None, "'claims.csv' is empty."
    except Exception as e:  # noqa: BLE001
        return None, None, f"Could not read claims.csv: {e}"

    try:
        indicators = pd.read_csv(INDICATORS_FILE)
    except FileNotFoundError:
        return None, None, "Required data file not found: 'fraud_indicators.csv' (checked app folder and ./data/)."
    except pd.errors.EmptyDataError:
        return None, None, "'fraud_indicators.csv' is empty."
    except Exception as e:  # noqa: BLE001
        return None, None, f"Could not read fraud_indicators.csv: {e}"

    required_claim_cols = [
        "claim_id", "policy_id", "customer_id", "claim_date", "claim_type",
        "claim_amount", "settlement_amount", "status", "fraud_flag", "days_to_settle",
    ]
    required_ind_cols = ["indicator_id", "claim_id", "indicator_type", "indicator_value", "score", "review_status"]

    missing_c = [c for c in required_claim_cols if c not in claims.columns]
    missing_i = [c for c in required_ind_cols if c not in indicators.columns]
    if missing_c or missing_i:
        msg = []
        if missing_c:
            msg.append(f"claims.csv missing columns: {missing_c}")
        if missing_i:
            msg.append(f"fraud_indicators.csv missing columns: {missing_i}")
        return None, None, " | ".join(msg)

    claims = claims.copy()
    indicators = indicators.copy()

    try:
        claims["claim_id"] = _clean_str(claims["claim_id"])
        claims["claim_type"] = _clean_str(claims["claim_type"]).replace({"nan": "Unspecified"})
        claims["status"] = _clean_str(claims["status"]).replace({"nan": "Unknown"})
        claims["claim_date"] = pd.to_datetime(claims["claim_date"], errors="coerce")
        claims["claim_amount"] = _to_numeric_safe(claims["claim_amount"]).fillna(0.0)
        claims["settlement_amount"] = _to_numeric_safe(claims["settlement_amount"])
        claims["days_to_settle"] = _to_numeric_safe(claims["days_to_settle"])
        claims["fraud_flag_bool"] = normalize_fraud_flag(claims["fraud_flag"])
        claims = claims.dropna(subset=["claim_id"])
        claims = claims[claims["claim_id"] != "nan"]

        indicators["claim_id"] = _clean_str(indicators["claim_id"])
        indicators["indicator_type"] = _clean_str(indicators["indicator_type"]).replace({"nan": "Unspecified"})
        indicators["review_status"] = _clean_str(indicators["review_status"]).replace({"nan": "Pending"})
        indicators["score"] = _to_numeric_safe(indicators["score"])
        indicators = indicators.dropna(subset=["claim_id"])
        indicators = indicators[indicators["claim_id"] != "nan"]
    except Exception as e:  # noqa: BLE001
        return None, None, f"Data cleaning failed: {e}"

    return claims, indicators, None


@st.cache_data(show_spinner=False)
def aggregate_indicators(indicators: pd.DataFrame) -> pd.DataFrame:
    if indicators.empty:
        return pd.DataFrame(columns=["claim_id", "avg_score", "max_score", "indicator_count",
                                      "has_confirmed", "has_flagged", "has_pending"])

    def _has(status_series, needle):
        return status_series.str.lower().str.contains(needle).any()

    grouped = indicators.groupby("claim_id").agg(
        avg_score=("score", "mean"),
        max_score=("score", "max"),
        indicator_count=("indicator_id", "count"),
    ).reset_index()

    status_flags = indicators.groupby("claim_id")["review_status"].apply(
        lambda s: pd.Series({
            "has_confirmed": _has(s, "confirm"),
            "has_flagged": _has(s, "flag"),
            "has_pending": _has(s, "pend") or _has(s, "review"),
        })
    ).unstack().reset_index()

    out = grouped.merge(status_flags, on="claim_id", how="left")
    for c in ["has_confirmed", "has_flagged", "has_pending"]:
        out[c] = out[c].fillna(False).astype(bool)
    out["avg_score"] = out["avg_score"].fillna(0.0)
    out["max_score"] = out["max_score"].fillna(0.0)
    return out


def classify_claim(row) -> str:
    fraud = bool(row.get("fraud_flag_bool", False))
    confirmed = bool(row.get("has_confirmed", False))
    flagged_or_pending = bool(row.get("has_flagged", False)) or bool(row.get("has_pending", False))
    if fraud and confirmed:
        return "confirmed"
    if fraud:
        return "fraud"
    if flagged_or_pending:
        return "review"
    return "normal"


@st.cache_data(show_spinner=False)
def build_master(claims: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
    agg = aggregate_indicators(indicators)
    master = claims.merge(agg, on="claim_id", how="left")
    for c in ["avg_score", "max_score", "indicator_count"]:
        master[c] = master[c].fillna(0.0)
    for c in ["has_confirmed", "has_flagged", "has_pending"]:
        master[c] = master[c].fillna(False).astype(bool)
    master["risk_category"] = master.apply(classify_claim, axis=1)
    return master


def apply_filters(master: pd.DataFrame, indicators: pd.DataFrame, claim_types, review_statuses, date_range, fraud_only):
    filtered = master.copy()
    if claim_types:
        filtered = filtered[filtered["claim_type"].isin(claim_types)]
    if date_range and len(date_range) == 2 and all(date_range):
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        filtered = filtered[filtered["claim_date"].between(start, end)]
    if fraud_only:
        filtered = filtered[filtered["fraud_flag_bool"]]

    filtered_indicators = indicators[indicators["claim_id"].isin(filtered["claim_id"])]
    if review_statuses:
        filtered_indicators = filtered_indicators[filtered_indicators["review_status"].isin(review_statuses)]
        claims_with_any_indicator = set(indicators["claim_id"].unique())
        keep_ids = set(filtered_indicators["claim_id"].unique()) | (set(filtered["claim_id"]) - claims_with_any_indicator)
        filtered = filtered[filtered["claim_id"].isin(keep_ids)]

    return filtered, filtered_indicators


# ============================================================================
# 4. FORMATTING HELPERS
# ============================================================================

def fmt_num(n) -> str:
    try:
        return f"{int(round(n)):,}"
    except (ValueError, TypeError):
        return "\u2014"


def fmt_money(n) -> str:
    try:
        if pd.isna(n):
            return "\u2014"
        return f"\u20b9{n:,.0f}"
    except (ValueError, TypeError):
        return "\u2014"


def fmt_pct(n) -> str:
    try:
        if pd.isna(n):
            return "\u2014"
        return f"{n:.1f}%"
    except (ValueError, TypeError):
        return "\u2014"


def stable_hash(text: str) -> int:
    h = 0
    for ch in str(text):
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h


def safe_section(section_name, render_fn, *args, **kwargs):
    try:
        render_fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        st.error(f"\u26a0\ufe0f {section_name} encountered an error and could not render.")
        if st.session_state.get("debug_mode"):
            st.exception(e)
        else:
            st.caption("Enable Debug Mode in the sidebar for technical details.")


# ============================================================================
# 5. WEBGL COMPONENT WRAPPER
# ============================================================================

_ID_COUNTER = {"n": 0}


def _next_dom_id(prefix: str) -> str:
    _ID_COUNTER["n"] += 1
    return prefix + str(_ID_COUNTER["n"])


def webgl_component(mode: str, data: dict, height: int = 560, dom_id: str = None, chrome: bool = True):
    """Render a real Three.js WebGL scene. Falls back to a visible
    diagnostic panel (never a blank canvas) if WebGL is unavailable or a
    render call throws — see static/harness.js:bootstrapScene.

    chrome=True adds the floating camera toolbar + hover tooltip + click
    detail card (used by every analytical scene). chrome=False is used
    for the decorative cosmic backdrop, which has no toolbar or picking.
    """
    assets, missing = load_static_assets()
    dom_id = dom_id or _next_dom_id("fwscene")

    if missing:
        st.warning(
            "\u26a0\ufe0f Missing local asset(s): " + ", ".join(missing) +
            " — place them under static/ next to app.py. Showing a static placeholder instead."
        )
        st.markdown(
            '<div style="height:' + str(height) + 'px;border-radius:16px;border:1px dashed rgba(255,146,91,0.5);'
            'display:flex;align-items:center;justify-content:center;color:#ff9f5b;font-size:12px;'
            'letter-spacing:1px;text-transform:uppercase;background:rgba(255,146,91,0.06);">'
            'VISUAL ENGINE \u2014 STATIC ASSETS MISSING</div>',
            unsafe_allow_html=True,
        )
        return

    build_fn_map = {
        "city": "buildCityScene",
        "observatory": "buildObservatoryScene",
        "lab": "buildLabScene",
        "network": "buildNetworkScene",
        "cosmic": "buildCosmicScene",
    }
    build_fn = build_fn_map.get(mode)
    if build_fn is None:
        st.error(f"Unknown scene mode: {mode}")
        return

    json_data = json.dumps(data)

    parts = []
    parts.append(
        '<style>'
        '*{box-sizing:border-box;}'
        '.fw-scene-root{font-family:' + FONT_STACK + ';}'
        '.fw-cam-toolbar{position:absolute;top:10px;left:10px;right:10px;z-index:20;display:flex;'
        'flex-wrap:wrap;gap:5px;padding:7px 8px;border-radius:12px;background:rgba(10,14,31,0.62);'
        'border:1px solid rgba(255,255,255,0.10);backdrop-filter:blur(6px);}'
        '.fw-cam-btn{font-family:' + FONT_STACK + ';font-size:9.5px;font-weight:700;letter-spacing:0.6px;'
        'text-transform:uppercase;color:#9aa3c4;background:rgba(255,255,255,0.05);'
        'border:1px solid rgba(255,255,255,0.10);border-radius:7px;padding:5px 9px;cursor:pointer;'
        'transition:all 0.15s ease;}'
        '.fw-cam-btn:hover{color:#eef1fb;border-color:rgba(76,201,240,0.55);background:rgba(76,201,240,0.12);}'
        '.fw-cam-btn.active{color:#05070f;background:#4cc9f0;border-color:#4cc9f0;}'
        '.fw-cam-sep{width:1px;align-self:stretch;background:rgba(255,255,255,0.12);margin:2px 2px;}'
        '.fw-hover-tip{position:absolute;z-index:25;display:none;pointer-events:none;background:#131a30;'
        'border:1px solid rgba(76,201,240,0.4);border-radius:7px;padding:5px 9px;font-size:10.5px;'
        'color:#eef1fb;white-space:nowrap;box-shadow:0 8px 20px -8px rgba(0,0,0,0.7);}'
        '.fw-detail-card{position:absolute;right:12px;top:56px;z-index:26;display:none;width:240px;'
        'max-width:60%;background:rgba(10,14,31,0.92);border:1px solid rgba(139,107,247,0.4);'
        'border-radius:12px;padding:14px 14px 12px 14px;box-shadow:0 16px 40px -14px rgba(0,0,0,0.8);'
        'backdrop-filter:blur(8px);}'
        '.fw-detail-close{position:absolute;top:8px;right:10px;background:none;border:none;color:#6b7394;'
        'font-size:12px;cursor:pointer;}'
        '.fw-detail-close:hover{color:#eef1fb;}'
        '.fw-detail-title{font-size:12.5px;font-weight:800;color:#eef1fb;letter-spacing:0.4px;'
        'margin-bottom:8px;padding-right:14px;}'
        '.fw-detail-row{display:flex;justify-content:space-between;gap:10px;font-size:10.5px;'
        'color:#9aa3c4;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.06);}'
        '.fw-detail-row b{color:#eef1fb;font-weight:700;text-align:right;}'
        '.fw-detail-obs{font-size:10.5px;color:#c9bdfc;line-height:1.5;margin-top:8px;}'
        '.fw-detail-source{font-size:9px;color:#6b7394;letter-spacing:0.5px;text-transform:uppercase;'
        'margin-top:8px;}'
        '</style>'
    )
    parts.append('<div id="' + dom_id + '" class="fw-scene-root" style="position:relative;width:100%;'
                 'height:' + str(height) + 'px;border-radius:16px;overflow:hidden;'
                 'background:linear-gradient(180deg,#060a18 0%,#0a1330 55%,#0d1a3d 100%);'
                 'border:1px solid rgba(255,255,255,0.10);">')
    parts.append('<canvas style="width:100%;height:100%;display:block;touch-action:none;"></canvas>')
    parts.append(
        '<div class="fw-diag-panel" style="display:none;position:absolute;inset:0;flex-direction:column;'
        'align-items:center;justify-content:center;gap:10px;background:rgba(6,9,20,0.93);color:#eef1fb;'
        'padding:26px;text-align:center;">'
        '<div style="font-size:12px;font-weight:800;letter-spacing:2px;color:#ff9f5b;text-transform:uppercase;">'
        'VISUAL ENGINE \u2014 FALLBACK MODE</div>'
        '<div style="font-size:11px;color:#9aa3c4;max-width:460px;line-height:1.8;">'
        'WEBGL STATUS: <span class="fw-diag-webgl">checking\u2026</span><br>'
        'GPU STATUS: <span class="fw-diag-gpu">checking\u2026</span><br>'
        'RENDER STATUS: <span class="fw-diag-reason">\u2014</span><br>'
        'DATA STATUS: <span class="fw-diag-data">ready \u2014 KPIs and tables are unaffected</span></div>'
        '</div>'
    )
    parts.append(
        '<div class="fw-hud" style="position:absolute;left:12px;bottom:10px;font-size:9.5px;letter-spacing:1px;'
        'color:#6b7394;background:rgba(10,14,31,0.55);padding:4px 9px;border-radius:8px;text-transform:uppercase;'
        'z-index:20;">Initializing\u2026</div>'
    )
    if chrome:
        parts.append('<div class="fw-hover-tip"></div>')
        parts.append('<div class="fw-detail-card"></div>')
    parts.append('</div>')
    parts.append('<script>' + assets["three"] + '</script>')
    parts.append('<script>' + assets["harness"] + '</script>')
    parts.append('<script>' + assets["scenes"] + '</script>')
    parts.append(
        '<script>window.FW.bootstrapScene("' + dom_id + '", function(rootId, sceneData){ '
        'window.FW.' + build_fn + '(rootId, sceneData); }, ' + json_data + ');</script>'
    )
    html = "".join(parts)

    try:
        st.iframe(html, height=height + 6, width="stretch")
    except Exception as e:  # noqa: BLE001
        st.warning("\u26a0\ufe0f Visualization fallback active — this 3D scene could not be embedded.")
        if st.session_state.get("debug_mode"):
            st.caption(f"Debug: {e}")


def render_visual_intelligence(title, fields, observation, interpretation, source):
    """The 'VISUAL INTELLIGENCE' explanation panel required under every
    major 3D scene: what it shows, what each visual channel encodes,
    the key observation, the business read, and the data source."""
    rows_html = "".join(
        '<div class="fw-vi-row"><span class="fw-vi-label">' + label + '</span>'
        '<span class="fw-vi-value">' + value + '</span></div>'
        for label, value in fields
    )
    st.markdown(
        '<div class="fw-vi-panel">'
        '<div class="fw-vi-title">VISUAL INTELLIGENCE \u00b7 ' + title + '</div>'
        '<div class="fw-vi-grid">' + rows_html + '</div>'
        '<div class="fw-vi-block"><span class="fw-vi-block-label">KEY OBSERVATION</span>' + observation + '</div>'
        '<div class="fw-vi-block"><span class="fw-vi-block-label">BUSINESS INTERPRETATION</span>' + interpretation + '</div>'
        '<div class="fw-vi-source">SOURCE: ' + source + '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# 6. SCENE DATA PREPARATION (Python computes; Three.js only renders)
# ============================================================================

def prepare_claim_positions(df: pd.DataFrame, all_types, max_claims: int = MAX_SCENE_CLAIMS) -> pd.DataFrame:
    if df.empty:
        return df
    sample = df
    if len(df) > max_claims:
        risky = df[df["risk_category"].isin(["fraud", "confirmed", "review"])]
        normal = df[df["risk_category"] == "normal"]
        n_risky = min(len(risky), max_claims)
        risky_sample = risky.sample(n=n_risky, random_state=42) if n_risky < len(risky) else risky
        remaining = max_claims - len(risky_sample)
        normal_sample = normal.sample(n=min(remaining, len(normal)), random_state=42) if remaining > 0 else normal.iloc[0:0]
        sample = pd.concat([risky_sample, normal_sample], ignore_index=True)

    n_types = max(len(all_types), 1)
    max_amount = max(float(df["claim_amount"].max()), 1.0)

    def _pos(row):
        seed = stable_hash(row["claim_id"])
        type_idx = all_types.index(row["claim_type"]) if row["claim_type"] in all_types else 0
        angle = (type_idx / n_types) * 2 * np.pi
        cluster_r = 4.6
        cx = cluster_r * np.cos(angle)
        cz = cluster_r * np.sin(angle)
        jitter_r = (seed % 1000) / 1000.0 * 2.6
        jitter_a = ((seed // 1000) % 1000) / 1000.0 * 2 * np.pi
        x = cx + jitter_r * np.cos(jitter_a)
        z = cz + jitter_r * np.sin(jitter_a)
        return x, z

    positions = sample.apply(_pos, axis=1, result_type="expand")
    sample = sample.copy()
    sample["_x"], sample["_z"] = positions[0], positions[1]
    sample["_amount_rank"] = (sample["claim_amount"] / max_amount).clip(0, 1)
    return sample


def city_scene_payload(filtered_master: pd.DataFrame, terrain_only: bool = False, auto_rotate: bool = False) -> dict:
    if filtered_master.empty:
        return {"claims": [], "autoRotate": auto_rotate, "terrainOnly": terrain_only}
    all_types = sorted(filtered_master["claim_type"].unique().tolist())
    sample = prepare_claim_positions(filtered_master, all_types)
    claims = [
        {
            "x": round(float(r["_x"]), 3),
            "z": round(float(r["_z"]), 3),
            "risk": r["risk_category"],
            "amountRank": round(float(r["_amount_rank"]), 3),
        }
        for _, r in sample.iterrows()
    ]
    return {"claims": claims, "autoRotate": auto_rotate, "terrainOnly": terrain_only}


def observatory_scene_payload(filtered_master: pd.DataFrame, filtered_indicators: pd.DataFrame) -> dict:
    claim_types = []
    max_type_total = 1
    avg_fraud_rate = 0.0
    if not filtered_master.empty:
        grp = filtered_master.groupby("claim_type").agg(
            totalCount=("claim_id", "count"), fraudCount=("fraud_flag_bool", "sum")
        ).reset_index()
        grp["fraudRate"] = (grp["fraudCount"] / grp["totalCount"] * 100).round(2)
        grp = grp.sort_values("totalCount", ascending=False).head(8)
        max_type_total = max(int(grp["totalCount"].max()), 1)
        avg_fraud_rate = float(grp["fraudRate"].mean())
        claim_types = [
            {"name": row["claim_type"], "totalCount": int(row["totalCount"]),
             "fraudCount": int(row["fraudCount"]), "fraudRate": float(row["fraudRate"])}
            for _, row in grp.iterrows()
        ]

    pipeline = []
    if not filtered_indicators.empty:
        order = ["Pending", "Flagged", "Confirmed", "Cleared"]
        counts = filtered_indicators["review_status"].value_counts()
        ordered = [s for s in order if s in counts.index] + [s for s in counts.index if s not in order]
        pipeline = [{"name": s, "count": int(counts[s])} for s in ordered[:6]]

    indicators = []
    if not filtered_indicators.empty:
        grp2 = filtered_indicators.groupby("indicator_type").agg(
            count=("indicator_id", "count"), avgScore=("score", "mean")
        ).reset_index().sort_values("count", ascending=False).head(6)

        def _state(itype):
            sub = filtered_indicators[filtered_indicators["indicator_type"] == itype]["review_status"].str.lower()
            if sub.str.contains("confirm").any():
                return "confirmed"
            if sub.str.contains("flag").any():
                return "flagged"
            return "pending"

        indicators = [
            {"name": row["indicator_type"], "count": int(row["count"]),
             "avgScore": round(float(row["avgScore"]), 1), "state": _state(row["indicator_type"])}
            for _, row in grp2.iterrows()
        ]

    return {
        "claimTypes": claim_types, "maxTypeTotal": max_type_total, "avgFraudRate": avg_fraud_rate,
        "pipeline": pipeline, "indicators": indicators,
    }


def lab_scene_payload(filtered_master: pd.DataFrame, filtered_indicators: pd.DataFrame) -> dict:
    trend = []
    ts = filtered_master.dropna(subset=["claim_date"]) if not filtered_master.empty else filtered_master
    if ts is not None and not ts.empty:
        ts = ts.copy()
        ts["month"] = ts["claim_date"].dt.to_period("M").dt.to_timestamp()
        monthly = ts.groupby("month").agg(total=("claim_id", "count"), fraud=("fraud_flag_bool", "sum")).reset_index()
        monthly = monthly.sort_values("month").tail(18)
        trend = [
            {"label": row["month"].strftime("%b %y"), "total": int(row["total"]), "fraud": int(row["fraud"])}
            for _, row in monthly.iterrows()
        ]

    score_bins = []
    if not filtered_indicators.empty:
        bins = np.linspace(0, 100, 11)
        binned = pd.cut(filtered_indicators["score"].dropna(), bins=bins, include_lowest=True)
        counts = binned.value_counts().sort_index()
        score_bins = [
            {"label": f"{int(iv.left)}-{int(iv.right)}", "count": int(c)} for iv, c in counts.items()
        ]

    return {"trend": trend, "scoreBins": score_bins}


def network_scene_payload(row: pd.Series, claim_indicators: pd.DataFrame, risk_category: str) -> dict:
    n_ind = len(claim_indicators)
    avg_score = float(claim_indicators["score"].mean()) if n_ind else 0.0
    dominant_status = claim_indicators["review_status"].mode().iloc[0] if n_ind else "None"
    settlement_text = fmt_money(row["settlement_amount"]) if pd.notna(row.get("settlement_amount")) else "Pending"

    satellites = [
        {"label": "POLICY NODE", "value": str(row["policy_id"]), "color": COLORS["electric_blue"]},
        {"label": "FRAUD INDICATOR NODE", "value": f"{n_ind} signals \u00b7 avg {avg_score:.1f}", "color": COLORS["violet"]},
        {"label": "REVIEW STATUS NODE", "value": dominant_status, "color": COLORS["gold"]},
        {"label": "SETTLEMENT NODE", "value": settlement_text, "color": COLORS["teal"]},
    ]
    return {"claimId": str(row["claim_id"]), "riskCategory": risk_category, "satellites": satellites}


# ============================================================================
# 7. KPI COMPUTATION
# ============================================================================

def compute_kpis(filtered_master: pd.DataFrame, filtered_indicators: pd.DataFrame) -> dict:
    total = len(filtered_master)
    fraud = int(filtered_master["fraud_flag_bool"].sum()) if total else 0
    rate = (fraud / total * 100) if total else 0.0
    n_indicators = len(filtered_indicators)
    flagged = int(filtered_indicators["review_status"].str.lower().str.contains("flag|pend|review").sum()) if n_indicators else 0
    confirmed_claims = int((filtered_master["risk_category"] == "confirmed").sum()) if total else 0
    avg_score = float(filtered_indicators["score"].mean()) if n_indicators else 0.0
    high_score = int((filtered_indicators["score"] >= 75).sum()) if n_indicators else 0
    return dict(total=total, fraud=fraud, rate=rate, flagged=flagged, confirmed=confirmed_claims,
                n_indicators=n_indicators, avg_score=avg_score, high_score=high_score)


# ============================================================================
# 8. UI COMPONENT BUILDERS
# ============================================================================

def render_hero():
    st.markdown(
        """
        <div class="fw-hero">
            <div class="fw-eyebrow"><span class="fw-dot"></span> INTERNAL FRAUDWATCH \u00b7 NEBULA RISK INTELLIGENCE \u00b7 INTERNAL ASSESSMENT 2</div>
            <div class="fw-title">FRAUDWATCH</div>
            <div class="fw-subtitle">Insurance Fraud Intelligence Command Center</div>
            <div class="fw-divider"></div>
            <div class="fw-authorbar">
                <div>
                    <div class="fw-author-name">Devanshu Saha</div>
                    <div class="fw-author-role">MBA Financial Services \u00b7 Roll No. 25WU0203008</div>
                </div>
                <div class="fw-status-panel">
                    <div class="fw-status-line"><span class="fw-status-chip"></span> SYSTEM ONLINE</div>
                    <div class="fw-status-line"><span class="fw-status-chip"></span> DATA ENGINE: ACTIVE</div>
                    <div class="fw-status-line"><span class="fw-status-chip"></span> RISK ENGINE: ACTIVE</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_navigation():
    cols = st.columns(len(NAV_ITEMS))
    for col, (key, label, glyph) in zip(cols, NAV_ITEMS):
        active = st.session_state.active_page == key
        display_label = glyph + " " + label
        with col:
            if st.button(display_label, key="nav_" + key, width="stretch"):
                st.session_state.active_page = key
                st.rerun()
            if active:
                st.markdown('<div class="fw-nav-glow"></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


def kpi_card(icon, label, value, desc, accent, risk=False):
    risk_class = " fw-risk" if risk else ""
    return (
        '<div class="fw-kpi-outer"><div class="fw-kpi' + risk_class + '" style="--accent:' + accent + ';">'
        '<div class="fw-kpi-icon">' + icon + '</div>'
        '<div class="fw-kpi-label">' + label + '</div>'
        '<div class="fw-kpi-value">' + str(value) + '</div>'
        '<div class="fw-kpi-desc">' + desc + '</div>'
        '</div></div>'
    )


def render_kpi_row(cards):
    cols = st.columns(len(cards))
    for col, c in zip(cols, cards):
        with col:
            st.markdown(kpi_card(*c), unsafe_allow_html=True)


def panel_open(title, subtitle=None):
    sub_html = '<div class="fw-panel-sub">' + subtitle + '</div>' if subtitle else ""
    st.markdown('<div class="fw-panel"><div class="fw-panel-title">' + title + '</div>' + sub_html, unsafe_allow_html=True)


def panel_close():
    st.markdown("</div>", unsafe_allow_html=True)


def key_takeaway(text):
    st.markdown('<div class="fw-takeaway"><span class="fw-takeaway-label">Key Takeaway</span>' + text + '</div>', unsafe_allow_html=True)


def render_footer():
    st.markdown(
        """
        <div class="fw-disclaimer">
            AI was used for dashboard structuring, coding assistance and interface development.
            Data calculations, validation, interpretation and recommendations were reviewed against the source datasets.
        </div>
        <div class="fw-footer">
            <div class="fw-footer-brand">INTERNAL FRAUDWATCH</div>
            <div class="fw-footer-line">Nebula Risk Intelligence \u00b7 Insurance Fraud Intelligence Command Center</div>
            <div class="fw-footer-line">Devanshu Saha \u2022 25WU0203008 \u2022 MBA Financial Services</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# 9. SIDEBAR
# ============================================================================

def show_system_status():
    st.sidebar.markdown(
        """
        <div class="fw-status-row"><span class="fw-status-dot"></span> DATA ENGINE: ONLINE</div>
        <div class="fw-status-row"><span class="fw-status-dot"></span> RISK ENGINE: ONLINE</div>
        <div class="fw-status-row"><span class="fw-status-dot"></span> VISUAL ENGINE: REAL WEBGL (LOCAL)</div>
        """,
        unsafe_allow_html=True,
    )


def render_diagnostics(claims, indicators):
    with st.sidebar.expander("System Diagnostics"):
        import platform
        import sys
        st.caption(f"Python: {platform.python_version()}")
        st.caption(f"Streamlit: {st.__version__}")
        st.caption(f"Pandas: {pd.__version__}")
        st.caption(f"Platform: {sys.platform}")
        st.caption(f"Data loaded: {'Yes' if claims is not None else 'No'}")
        if claims is not None:
            st.caption(f"Claims rows: {len(claims):,}")
        if indicators is not None:
            st.caption(f"Indicator rows: {len(indicators):,}")
        _, missing = load_static_assets()
        st.caption(f"Local Three.js bundle: {'OK' if not missing else 'MISSING: ' + ', '.join(missing)}")
        st.caption("WebGL / renderer status is shown live under each 3D panel (client-side, per browser).")
        st.session_state.debug_mode = st.checkbox(
            "Debug Mode (show technical error detail)",
            value=st.session_state.get("debug_mode", False),
        )


def render_sidebar(master: pd.DataFrame, indicators: pd.DataFrame):
    st.sidebar.markdown(
        '<div style="font-size:13px;font-weight:800;letter-spacing:2px;color:#eef1fb;margin-bottom:2px;">RISK FILTERS</div>'
        '<div style="font-size:11px;color:#6b7394;margin-bottom:14px;">Cross-filter every 3D scene instantly</div>',
        unsafe_allow_html=True,
    )

    claim_types_all = sorted(master["claim_type"].dropna().unique().tolist())
    review_status_all = sorted(indicators["review_status"].dropna().unique().tolist())

    sel_types = st.sidebar.multiselect("Claim Type", claim_types_all, default=claim_types_all)
    sel_reviews = st.sidebar.multiselect("Review Status", review_status_all, default=review_status_all)

    valid_dates = master["claim_date"].dropna()
    if not valid_dates.empty:
        min_d, max_d = valid_dates.min().date(), valid_dates.max().date()
    else:
        min_d, max_d = date(2020, 1, 1), date.today()

    date_range = st.sidebar.date_input("Claim Date", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, (tuple, list)) and len(date_range) == 1:
        date_range = (date_range[0], date_range[0])
    elif not isinstance(date_range, (tuple, list)):
        date_range = (date_range, date_range)

    fraud_only = st.sidebar.checkbox("Fraud Flag = Yes only", value=False)

    filtered_master, filtered_indicators = apply_filters(master, indicators, sel_types, sel_reviews, date_range, fraud_only)

    st.sidebar.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div style="font-size:11px;font-weight:800;letter-spacing:1.6px;color:#4cc9f0;'
        'text-transform:uppercase;margin-bottom:8px;">Filtered Population</div>',
        unsafe_allow_html=True,
    )
    total_claims = len(filtered_master)
    fraud_claims = int(filtered_master["fraud_flag_bool"].sum()) if total_claims else 0
    fraud_rate = (fraud_claims / total_claims * 100) if total_claims else 0.0

    st.sidebar.markdown(
        '<div class="fw-mini" style="margin-bottom:8px;">'
        '<div class="fw-mini-label">Claims</div><div class="fw-mini-value">' + fmt_num(total_claims) + '</div></div>'
        '<div class="fw-mini" style="margin-bottom:8px;">'
        '<div class="fw-mini-label">Fraud Claims</div><div class="fw-mini-value" style="color:' + COLORS["coral"] + '">'
        + fmt_num(fraud_claims) + '</div></div>'
        '<div class="fw-mini"><div class="fw-mini-label">Fraud Rate</div><div class="fw-mini-value" style="color:'
        + COLORS["gold"] + '">' + fmt_pct(fraud_rate) + '</div></div>',
        unsafe_allow_html=True,
    )
    if total_claims > MAX_SCENE_CLAIMS:
        st.sidebar.caption(
            f"{total_claims:,} claims analyzed \u00b7 visual layer optimized to {MAX_SCENE_CLAIMS} sampled markers"
        )
    return filtered_master, filtered_indicators


# ============================================================================
# 10. PAGES
# ============================================================================

def page_command_center(filtered_master, filtered_indicators):
    k = compute_kpis(filtered_master, filtered_indicators)
    st.markdown('<div class="fw-section-label">Command Center \u00b7 Fraud Intelligence City</div>', unsafe_allow_html=True)

    safe_section("KPI row", render_kpi_row, [
        ("TOTAL", "Total Claims", fmt_num(k["total"]), "Filtered claim population", COLORS["electric_blue"], False),
        ("FRAUD", "Fraud Claims", fmt_num(k["fraud"]), "Flagged as fraudulent", COLORS["coral"], True),
        ("RATE", "Fraud Rate", fmt_pct(k["rate"]), "Share of filtered claims", COLORS["gold"], False),
        ("REVIEW", "Flagged / Under Review", fmt_num(k["flagged"]), "Indicator signals pending", COLORS["violet"], False),
        ("CONFIRM", "Confirmed Fraud", fmt_num(k["confirmed"]), "Fraud + confirmed indicator", COLORS["teal"], False),
    ])
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    panel_open("Nebula Cosmic Anchor", "Decorative WebGL backdrop \u2014 black hole, accretion disk, nebula \u00b7 mouse parallax, always auto-rotating")

    def _cosmic():
        webgl_component("cosmic", {}, height=260, dom_id="fwcc_cosmic", chrome=False)

    safe_section("Cosmic backdrop scene", _cosmic)
    panel_close()

    panel_open(
        "3D Fraud Intelligence City",
        "Real WebGL \u00b7 left-drag orbit \u00b7 right-drag/shift-drag pan \u00b7 wheel/pinch zoom \u00b7 "
        "toolbar for Front/Back/Left/Right/Top/Bottom/Isometric \u00b7 click any object for details"
    )

    def _render():
        payload = city_scene_payload(filtered_master, terrain_only=False, auto_rotate=False)
        if not payload["claims"]:
            st.info("No claims match the current filters — adjust Risk Filters to populate the city.")
        webgl_component("city", payload, height=580, dom_id="fwcc_city")

    safe_section("Fraud Intelligence City scene", _render)
    st.markdown(
        '<div class="fw-scene-caption">Fraud = orange beacon \u00b7 Confirmed = red beacon \u00b7 Review = gold \u00b7 '
        'Normal = cyan \u00b7 positions are visual coordinates, not geographic data</div>',
        unsafe_allow_html=True,
    )

    def _vi():
        top_type = filtered_master.groupby("claim_type")["fraud_flag_bool"].mean().idxmax() if k["fraud"] else "N/A"
        render_visual_intelligence(
            "Fraud Intelligence City",
            [
                ("What this shows", "A 3D analytical city where every claim in the filtered set is a positioned, coloured marker."),
                ("Height / elevation", "Terrain elevation + a risk lift for fraud/confirmed markers (screening emphasis)."),
                ("Size", "Marker size scales with the claim's amount percentile within the filtered set."),
                ("Colour", "Risk category \u2014 cyan normal, gold review, orange fraud-flagged, red confirmed fraud."),
                ("Glow / pulse", "Fraud and confirmed markers pulse; pulse rate is constant, not data-driven."),
                ("Position", "Claim type determines angular cluster; jitter within a cluster is deterministic per claim ID, not geographic."),
            ],
            f"{top_type} clusters show the densest concentration of high-risk beacons in the current filtered view.",
            "Use marker density and colour concentration per cluster to decide which claim-type zones warrant the next screening pass.",
            "claims.csv \u00b7 fraud_indicators.csv",
        )

    safe_section("Visual intelligence panel", _vi)
    panel_close()

    panel_open("Key Takeaway")
    if k["total"]:
        top_type = filtered_master.groupby("claim_type")["fraud_flag_bool"].mean().idxmax() if k["fraud"] else "N/A"
        key_takeaway(
            f"Of <b>{fmt_num(k['total'])}</b> filtered claims, <b>{fmt_num(k['fraud'])}</b> "
            f"(<b>{fmt_pct(k['rate'])}</b>) are flagged as fraudulent, with <b>{top_type}</b> showing the highest "
            f"fraud incidence in the current view. <b>{fmt_num(k['flagged'])}</b> indicator signals are flagged or "
            f"under review, and <b>{fmt_num(k['confirmed'])}</b> claims carry confirmed-fraud status."
        )
    else:
        key_takeaway("No claims match the current filter selection.")
    panel_close()

    panel_open("Fraud Response Command Panel", "3\u20135 quantified recommendations \u2014 OBSERVATION / EVIDENCE / ACTION")

    def _recs():
        if filtered_master.empty:
            st.info("No data available for recommendations under the current filters.")
            return
        by_type = filtered_master.groupby("claim_type").agg(
            total=("claim_id", "count"), fraud=("fraud_flag_bool", "sum")
        )
        by_type["rate"] = (by_type["fraud"] / by_type["total"] * 100).round(1)
        by_type = by_type.sort_values("rate", ascending=False)
        top_rate_type = by_type.index[0] if not by_type.empty else "N/A"
        top_rate_val = by_type["rate"].iloc[0] if not by_type.empty else 0.0
        overall_rate = k["rate"]

        pending_pipeline = int(filtered_indicators["review_status"].str.lower().str.contains("pend|flag").sum()) if len(filtered_indicators) else 0
        high_score_ct = k["high_score"]
        avg_score = k["avg_score"]

        recs = [
            ("Prioritise " + str(top_rate_type) + " claims for expedited screening",
             f"{top_rate_type} shows a {top_rate_val:.1f}% fraud rate versus an overall {overall_rate:.1f}% across the filtered population.",
             "Route new " + str(top_rate_type) + " claims through an accelerated indicator-review queue before standard processing."),
            ("Clear the flagged/pending indicator backlog",
             f"{fmt_num(pending_pipeline)} indicators currently sit in Pending or Flagged review status in this view.",
             "Assign investigator capacity against the Review Pipeline chamber heights on the Fraud Drivers page, oldest first."),
            ("Treat indicator score \u2265 75 as a triage trigger, not a verdict",
             f"{fmt_num(high_score_ct)} indicators score \u226575 (average score in view: {avg_score:.1f}); the score is a screening signal only.",
             "Route score \u226575 claims to manual investigation queues rather than auto-approving or auto-declining on score alone."),
            ("Monitor the monthly fraud trend for emerging shifts",
             "The Analytics laboratory's trend ridge shows fraud claim volume month over month for the filtered population.",
             "Review the ridge shape each reporting cycle; investigate any sustained upward run rather than isolated spikes."),
        ]
        for i, (title, evidence, action) in enumerate(recs, start=1):
            st.markdown(
                '<div class="fw-rec"><div class="fw-rec-num">' + f"{i:02d}" + '</div><div>'
                '<div class="fw-rec-title">' + title + '</div>'
                '<div class="fw-rec-block">Observation</div><div class="fw-rec-text">' + title + '.</div>'
                '<div class="fw-rec-block">Evidence</div><div class="fw-rec-text">' + evidence + '</div>'
                '<div class="fw-rec-block">Action</div><div class="fw-rec-text">' + action + '</div>'
                '</div></div>',
                unsafe_allow_html=True,
            )

    safe_section("Recommendations panel", _recs)
    panel_close()


def page_risk_terrain(filtered_master, filtered_indicators):
    st.markdown('<div class="fw-section-label">Risk Terrain \u00b7 Synthetic Risk Terrain</div>', unsafe_allow_html=True)

    k = compute_kpis(filtered_master, filtered_indicators)
    safe_section("KPI row", render_kpi_row, [
        ("SCORE", "Average Indicator Score", f"{k['avg_score']:.1f}", "Across filtered indicators", COLORS["electric_blue"], False),
        ("HIGH", "Score \u2265 75", fmt_num(k["high_score"]), "High-priority screening signals", COLORS["coral"], True),
        ("CONFIRM", "Confirmed", fmt_num(k["confirmed"]), "Confirmed-fraud claims", COLORS["violet"], False),
        ("FLAG", "Flagged", fmt_num(k["flagged"]), "Awaiting confirmation", COLORS["gold"], False),
    ])
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    panel_open("Insurance Risk Planet", "Rotating 3D terrain \u2014 real WebGL \u00b7 full free orbit + toolbar (Front/Back/Left/Right/Top/Bottom/Iso) \u00b7 auto-rotate is on by default here, toggle it off in the toolbar to inspect freely")

    def _render():
        payload = city_scene_payload(filtered_master, terrain_only=True, auto_rotate=True)
        if not payload["claims"]:
            st.info("No claims match the current filters — adjust Risk Filters to populate the terrain.")
        webgl_component("city", payload, height=640, dom_id="fwrt_planet")

    safe_section("Risk terrain scene", _render)
    st.markdown(
        '<div class="fw-scene-caption">SYNTHETIC RISK TERRAIN \u2014 ANALYTICAL VISUALIZATION \u00b7 '
        'not real geography, not real geographic claim coordinates</div>',
        unsafe_allow_html=True,
    )

    def _vi_rt():
        render_visual_intelligence(
            "Insurance Risk Planet",
            [
                ("What this shows", "The same claim-marker city rendered as a rotating analytical terrain, without buildings, for a cleaner risk-density read."),
                ("Height / elevation", "Base terrain undulation plus a risk lift on fraud/confirmed markers."),
                ("Size", "Marker size scales with claim amount percentile."),
                ("Colour", "Risk category \u2014 cyan normal, gold review, orange fraud-flagged, red confirmed fraud."),
                ("Position", "Visual coordinates by claim-type cluster \u2014 not geography."),
            ],
            f"Average indicator score in the filtered view is {k['avg_score']:.1f}, with {fmt_num(k['high_score'])} indicators scoring 75 or above.",
            "Score \u2265 75 should trigger prioritised manual review, not an automatic fraud determination.",
            "claims.csv \u00b7 fraud_indicators.csv",
        )

    safe_section("Visual intelligence panel", _vi_rt)
    panel_close()

    panel_open("Interpretation")
    key_takeaway(
        "Indicator scores are screening signals and should support investigation prioritisation rather than be "
        "treated as standalone proof of fraud. Beacon prominence in this environment reflects risk-signal "
        "concentration in the filtered data, not confirmed outcomes."
    )
    panel_close()


def page_claim_investigation(claims_full, indicators_full, filtered_master):
    st.markdown('<div class="fw-section-label">Claim Investigation \u00b7 3D Forensic Console</div>', unsafe_allow_html=True)

    available_ids = sorted(filtered_master["claim_id"].unique().tolist()) if not filtered_master.empty else sorted(claims_full["claim_id"].unique().tolist())
    if not available_ids:
        st.info("No claims available for the current filters.")
        return

    selected_id = st.selectbox("Select Claim ID", available_ids)
    row = claims_full[claims_full["claim_id"] == selected_id]
    if row.empty:
        st.warning("Selected claim could not be located in the dataset.")
        return
    row = row.iloc[0]
    claim_indicators = indicators_full[indicators_full["claim_id"] == selected_id]
    cat = classify_claim({
        "fraud_flag_bool": row["fraud_flag_bool"],
        "has_confirmed": claim_indicators["review_status"].str.lower().str.contains("confirm").any(),
        "has_flagged": claim_indicators["review_status"].str.lower().str.contains("flag").any(),
        "has_pending": claim_indicators["review_status"].str.lower().str.contains("pend|review").any(),
    })
    accent = CATEGORY_COLORS[cat]
    label_map = {"confirmed": "CONFIRMED FRAUD", "fraud": "FRAUD FLAGGED", "review": "UNDER REVIEW", "normal": "NORMAL"}

    st.markdown(
        '<div class="fw-invest-header"><div>'
        '<div style="font-size:11px;letter-spacing:1.5px;color:#9aa3c4;text-transform:uppercase;">Claim Under Investigation</div>'
        '<div style="font-size:20px;font-weight:800;color:#eef1fb;">' + str(row["claim_id"]) + '</div></div>'
        '<div class="fw-pill" style="background:rgba(255,255,255,0.06);border:1px solid ' + accent + '66;color:' + accent + ';">'
        + label_map[cat] + '</div></div>',
        unsafe_allow_html=True,
    )

    safe_section("KPI row", render_kpi_row, [
        ("TYPE", "Claim Type", str(row["claim_type"]), "Line of business", COLORS["electric_blue"], False),
        ("AMT", "Claim Amount", fmt_money(row["claim_amount"]), "Amount claimed", COLORS["gold"], False),
        ("STATUS", "Status", str(row["status"]), "Current pipeline stage", COLORS["violet"], False),
        ("FLAG", "Fraud Flag", "Yes" if row["fraud_flag_bool"] else "No", "Fraud determination", COLORS["coral"], cat in ("fraud", "confirmed")),
    ])

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    panel_open("3D Investigation Network", "Claim node connected to Policy / Fraud Indicator / Review Status / Settlement nodes \u2014 real WebGL \u00b7 orbit freely, click any node for its detail card")

    def _render():
        payload = network_scene_payload(row, claim_indicators, cat)
        webgl_component("network", payload, height=480, dom_id="fwci_net_" + str(selected_id).replace(" ", "_"))

    safe_section("Investigation network scene", _render)

    def _vi_net():
        render_visual_intelligence(
            "Investigation Network",
            [
                ("What this shows", "The selected claim as a central node, connected to its Policy, Fraud Indicator, Review Status and Settlement facets."),
                ("Colour", "Central node colour reflects the claim's risk category; satellite node colours are fixed per facet type."),
                ("Position", "Satellites are placed on a fixed ring around the claim node \u2014 angle carries no data meaning, only separation."),
                ("Glow", "Emissive intensity increases on hover to indicate the node is interactive."),
            ],
            f"This claim carries {len(claim_indicators)} recorded fraud indicator(s).",
            "Click the Fraud Indicator node for the exact signal count and average score behind this claim's classification.",
            "claims.csv \u00b7 fraud_indicators.csv",
        )

    safe_section("Visual intelligence panel", _vi_net)
    panel_close()

    panel_open("Detailed Claim Record")

    def _detail_table():
        detail = pd.DataFrame({
            "Field": ["Claim ID", "Policy ID", "Customer ID", "Claim Date", "Claim Type", "Claim Amount",
                      "Settlement Amount", "Status", "Fraud Flag", "Days to Settle"],
            "Value": [
                row["claim_id"], row["policy_id"], row["customer_id"],
                row["claim_date"].strftime("%d %b %Y") if pd.notna(row["claim_date"]) else "\u2014",
                row["claim_type"], fmt_money(row["claim_amount"]), fmt_money(row["settlement_amount"]),
                row["status"], "Yes" if row["fraud_flag_bool"] else "No",
                f"{row['days_to_settle']:.0f} days" if pd.notna(row["days_to_settle"]) else "Not yet settled",
            ],
        })
        st.dataframe(detail, width="stretch", hide_index=True, height=390)

    safe_section("Detailed claim record", _detail_table)
    panel_close()

    panel_open("Associated Fraud Indicators")

    def _indicator_table():
        ind_rows = claim_indicators[["indicator_type", "indicator_value", "score", "review_status"]].rename(columns={
            "indicator_type": "Indicator Type", "indicator_value": "Indicator Value",
            "score": "Score", "review_status": "Review Status",
        })
        if ind_rows.empty:
            st.info("No fraud indicators are recorded against this claim.")
        else:
            st.dataframe(ind_rows.sort_values("Score", ascending=False), width="stretch", hide_index=True)

    safe_section("Associated fraud indicators table", _indicator_table)
    panel_close()


def page_fraud_drivers(filtered_master, filtered_indicators):
    st.markdown('<div class="fw-section-label">Fraud Drivers \u00b7 3D Fraud Driver Observatory</div>', unsafe_allow_html=True)

    if filtered_master.empty:
        st.info("No data for current filters.")
        return

    panel_open(
        "Fraud Driver Observatory",
        "Fraud Towers (claim type) \u00b7 Review Pipeline (chambers + flowing particles) \u00b7 Indicator Orbital Network \u2014 "
        "real WebGL, one unified scene \u00b7 full free orbit + toolbar \u00b7 click any tower, chamber or node for its detail card"
    )

    def _render():
        payload = observatory_scene_payload(filtered_master, filtered_indicators)
        webgl_component("observatory", payload, height=580, dom_id="fwfd_obs")

    safe_section("Fraud Driver Observatory scene", _render)
    st.markdown(
        '<div class="fw-scene-caption">Glowing ring = fraud rate above the filtered-population average \u00b7 '
        'observed data only \u2014 no inferred relationships beyond what the dataset shows</div>',
        unsafe_allow_html=True,
    )

    def _vi_obs():
        render_visual_intelligence(
            "Fraud Driver Observatory",
            [
                ("What this shows", "Three linked analytical zones in one scene: fraud towers by claim type, the review pipeline, and the indicator orbital network."),
                ("Tower height", "Fraud claim count for that claim type."),
                ("Tower radius", "Total claim volume for that claim type (relative)."),
                ("Tower glow ring", "Shown only when that claim type's fraud rate exceeds the filtered-population average."),
                ("Chamber height", "Indicator count currently in that review-pipeline stage."),
                ("Particle flow", "Decorative motion representing throughput \u2014 not a literal claim-by-claim animation."),
                ("Orbit node size / height", "Indicator count and average score for that indicator type; colour reflects dominant review state."),
            ],
            "Observed data only \u2014 the scene does not infer causal relationships between claim type, pipeline stage and indicator type.",
            "Combine the highest fraud-rate tower with the busiest orbital node to prioritise which claim-type + indicator-type combination to screen first.",
            "claims.csv \u00b7 fraud_indicators.csv",
        )

    safe_section("Visual intelligence panel", _vi_obs)
    panel_close()

    panel_open("Key Takeaway")
    grp = filtered_master.groupby("claim_type").agg(total=("claim_id", "count"), fraud=("fraud_flag_bool", "sum"))
    grp["rate"] = (grp["fraud"] / grp["total"] * 100).round(1)
    top = grp.sort_values("rate", ascending=False).head(1)
    top_name = top.index[0] if not top.empty else "N/A"
    top_rate = top["rate"].iloc[0] if not top.empty else 0.0
    n_ind = len(filtered_indicators)
    top_ind = filtered_indicators["indicator_type"].value_counts().idxmax() if n_ind else "N/A"
    key_takeaway(
        f"<b>{top_name}</b> carries the highest fraud rate in the filtered population at <b>{fmt_pct(top_rate)}</b>. "
        f"<b>{top_ind}</b> is the most frequently triggered fraud indicator type. These are observed patterns in the "
        f"current data — not causal claims about why fraud occurs."
    )
    panel_close()


def page_analytics(filtered_master, filtered_indicators):
    st.markdown('<div class="fw-section-label">Analytics \u00b7 3D Analytics Laboratory</div>', unsafe_allow_html=True)

    if filtered_master.empty:
        st.info("No data for current filters.")
        return

    panel_open(
        "Analytics Laboratory",
        "Monthly Fraud Trend ridge \u00b7 Indicator Score Distribution columns \u2014 real WebGL \u00b7 full free orbit + toolbar \u00b7 click any bar/column for its exact values"
    )

    def _render():
        payload = lab_scene_payload(filtered_master, filtered_indicators)
        webgl_component("lab", payload, height=540, dom_id="fwan_lab")

    safe_section("Analytics Laboratory scene", _render)

    def _vi_lab():
        render_visual_intelligence(
            "Analytics Laboratory",
            [
                ("What this shows", "Two linked zones: a monthly fraud-trend ridge (left) and an indicator score distribution (right)."),
                ("Ridge bar height", "Fraud claim count for that month in the filtered set."),
                ("Ridge bar colour", "Interpolates from deep blue (low) to red (high) fraud volume for that month."),
                ("Score column height", "Number of indicators whose score falls in that 10-point bucket."),
                ("Score column colour", "Cyan-to-violet gradient across buckets \u2014 purely visual separation, not a risk scale."),
            ],
            "Monthly fraud volume and the indicator score distribution are shown side by side for the filtered population.",
            "The score histogram's shape \u2014 not a single threshold \u2014 is what should inform where a triage cut-off is set.",
            "claims.csv \u00b7 fraud_indicators.csv",
        )

    safe_section("Visual intelligence panel", _vi_lab)
    panel_close()

    panel_open("Key Takeaway")
    merged = filtered_indicators.merge(filtered_master[["claim_id", "fraud_flag_bool"]], on="claim_id", how="left")
    merged = merged.dropna(subset=["score"]) if not merged.empty else merged
    if not merged.empty:
        fraud_scores = merged[merged["fraud_flag_bool"] == True]["score"]  # noqa: E712
        not_fraud_scores = merged[merged["fraud_flag_bool"] == False]["score"]  # noqa: E712
        mean_fraud = fraud_scores.mean() if not fraud_scores.empty else float("nan")
        mean_not = not_fraud_scores.mean() if not not_fraud_scores.empty else float("nan")
        key_takeaway(
            f"Average indicator score for fraud-flagged claims is <b>{mean_fraud:.1f}</b> versus "
            f"<b>{mean_not:.1f}</b> for non-fraud claims in the filtered view. The indicator score shows only a "
            f"<b>weak relationship</b> with the fraud flag in this dataset — it is a screening/prioritisation "
            f"signal, not proof of fraud."
        )
    else:
        key_takeaway("No matched claim/indicator records for the current filters.")
    panel_close()


# ============================================================================
# 11. MAIN
# ============================================================================

def main():
    configure_page()
    inject_css()

    if "active_page" not in st.session_state:
        st.session_state.active_page = "command_center"
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False

    render_hero()

    claims, indicators, error = load_data()

    show_system_status()
    render_diagnostics(claims, indicators)

    if error:
        st.error(f"\u26a0\ufe0f {error}")
        st.info(
            "Place **claims.csv** and **fraud_indicators.csv** either next to app.py or in a **./data/** "
            "subfolder, then reload the dashboard."
        )
        render_footer()
        return

    if claims.empty:
        st.warning("claims.csv was loaded but contains no usable rows after cleaning.")
        render_footer()
        return

    master = build_master(claims, indicators)

    render_navigation()
    filtered_master, filtered_indicators = render_sidebar(master, indicators)

    page = st.session_state.active_page
    if page == "command_center":
        safe_section("Command Center", page_command_center, filtered_master, filtered_indicators)
    elif page == "risk_terrain":
        safe_section("Risk Terrain", page_risk_terrain, filtered_master, filtered_indicators)
    elif page == "claim_investigation":
        safe_section("Claim Investigation", page_claim_investigation, master, indicators, filtered_master)
    elif page == "fraud_drivers":
        safe_section("Fraud Drivers", page_fraud_drivers, filtered_master, filtered_indicators)
    elif page == "analytics":
        safe_section("Analytics", page_analytics, filtered_master, filtered_indicators)

    render_footer()


if __name__ == "__main__":
    main()
