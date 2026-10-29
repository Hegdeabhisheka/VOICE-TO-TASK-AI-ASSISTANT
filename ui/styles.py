"""Global CSS: dark glassmorphism, neon accents and the fixed 3D-background layer."""
from __future__ import annotations

_CSS = r"""
<style>
:root { --neon:#00e5ff; --violet:#8b5cf6; --pink:#ff3df2; --amber:#ffb300; --red:#ff3b5c; --green:#39ff14;
  --blue:#3b82f6; --glass:rgba(14,18,44,.55); --glass-strong:rgba(14,18,44,.78);
  --border:rgba(255,255,255,.12); --text:#e6ebff; --muted:#93a0c8; }

/* ---- transparent Streamlit surfaces so the 3D layer shows through */
html, body { background:#04050d !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMainBlockContainer"], .main, section.main { background:transparent !important; color:var(--text); }
[data-testid="stSidebar"] { background:var(--glass-strong) !important; backdrop-filter:blur(16px); }

/* ---- hide default chrome */
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { visibility:hidden !important; height:0 !important; display:none !important; }
.block-container { position:relative; z-index:1; max-width:1250px; padding-top:1.2rem; }

/* ---- 3D background: the iframe holding build_background_html() sits fixed behind everything.
   Matched by a marker inside its srcdoc, or by a wrapper container created with st.container(key="bg3d"). */
iframe[srcdoc*="vtai-bg3d"], .st-key-bg3d iframe {
  position:fixed !important; inset:0 !important; width:100vw !important; height:100vh !important;
  z-index:-1 !important; pointer-events:none !important; border:0 !important; background:transparent !important; }
.st-key-bg3d, [data-testid="stElementContainer"]:has(> iframe[srcdoc*="vtai-bg3d"]),
[data-testid="stElementContainer"]:has(iframe[srcdoc*="vtai-bg3d"]) {
  position:absolute !important; width:0 !important; height:0 !important; min-height:0 !important;
  margin:0 !important; padding:0 !important; overflow:visible !important; }

/* ---- headings and text */
.neon-title, h1, h2, h3 { background:linear-gradient(90deg,#00e5ff,#8b5cf6 55%,#ff3df2);
  -webkit-background-clip:text; background-clip:text; color:transparent !important;
  -webkit-text-fill-color:transparent; font-weight:800; letter-spacing:.01em; }
.neon-title { font-size:2.5rem; line-height:1.1; filter:drop-shadow(0 0 14px rgba(0,229,255,.35)); }
.subtitle { color:var(--muted); margin:.2rem 0 1rem; }

/* ---- glass panels: any container created with st.container(key="panel_...") or a .glass block */
[class*="st-key-panel"], .glass { background:var(--glass); backdrop-filter:blur(14px) saturate(140%);
  -webkit-backdrop-filter:blur(14px) saturate(140%); border:1px solid var(--border); border-radius:20px;
  padding:1rem 1.2rem; box-shadow:0 10px 40px rgba(0,0,0,.4), 0 0 0 1px rgba(0,229,255,.07),
  inset 0 0 30px rgba(0,229,255,.05); transition:border-color .25s ease, box-shadow .25s ease, transform .25s ease; }
[class*="st-key-panel"]:hover, .glass:hover { border-color:rgba(0,229,255,.45);
  box-shadow:0 14px 48px rgba(0,0,0,.45), 0 0 26px rgba(0,229,255,.18), inset 0 0 30px rgba(0,229,255,.06); }

[data-testid="stMetric"] { background:rgba(255,255,255,.04); border:1px solid var(--border); border-radius:14px; padding:.5rem .8rem; }
[data-testid="stMetricValue"] { color:var(--neon); }
[data-testid="stAudioInput"] { border-radius:16px; border:1px solid rgba(0,229,255,.25); background:rgba(255,255,255,.03); }
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div { background:rgba(255,255,255,.05) !important;
  border:1px solid var(--border) !important; border-radius:12px !important; color:var(--text) !important; }
.stTextInput input:focus { border-color:var(--neon) !important; box-shadow:0 0 14px rgba(0,229,255,.3) !important; }

.stButton > button, .stDownloadButton > button { border-radius:12px; color:var(--text);
  border:1px solid rgba(0,229,255,.45); background:rgba(0,229,255,.08); transition:all .2s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--neon); color:#fff;
  box-shadow:0 0 18px rgba(0,229,255,.45); transform:translateY(-1px); }
.stTabs [data-baseweb="tab-list"] { gap:.4rem; }
.stTabs [data-baseweb="tab"] { background:rgba(255,255,255,.04); border-radius:12px 12px 0 0; padding:.5rem 1rem; transition:background .2s ease; }
.stTabs [data-baseweb="tab"]:hover { background:rgba(0,229,255,.1); }
.stTabs [aria-selected="true"] { background:rgba(0,229,255,.14); color:var(--neon); }

/* ---- scrollbar */
* { scrollbar-width:thin; scrollbar-color:rgba(0,229,255,.45) rgba(255,255,255,.04); }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:rgba(255,255,255,.03); }
::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#00e5ff,#8b5cf6); border-radius:10px; border:2px solid rgba(4,5,13,.8); }

/* ---- pulsing mic badge (components.mic_badge) */
.mic-badge { --ring:#00e5ff; position:relative; display:inline-flex; align-items:center; justify-content:center;
  width:64px; height:64px; border-radius:50%; font-size:1.7rem; border:1px solid var(--ring);
  background:radial-gradient(circle at 30% 30%, rgba(0,229,255,.32), rgba(139,92,246,.25));
  box-shadow:0 0 22px color-mix(in srgb, var(--ring) 45%, transparent); transition:all .3s ease; }
.mic-badge::before, .mic-badge::after { content:""; position:absolute; inset:0; border-radius:50%;
  border:2px solid var(--ring); opacity:0; animation:micRing 2.6s ease-out infinite; }
.mic-badge::after { animation-delay:1.3s; }
.mic-badge.listening { --ring:#00ff9d; } .mic-badge.processing { --ring:#ffb300; }
.mic-badge.success { --ring:#39ff14; } .mic-badge.error { --ring:#ff3b5c; }
.mic-badge.listening::before, .mic-badge.listening::after { animation-duration:1.2s; }
.mic-badge.processing::before, .mic-badge.processing::after { animation-duration:.9s; }
.mic-label { margin-left:.8rem; color:var(--muted); letter-spacing:.14em; text-transform:uppercase; font-size:.75rem; }
.mic-row { display:flex; align-items:center; margin:.3rem 0 .6rem; }
@keyframes micRing { 0% { transform:scale(1); opacity:.7; } 100% { transform:scale(1.9); opacity:0; } }
@keyframes fadeUp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }

/* ---- priority chips and task cards */
.chip { display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.06em; padding:.12rem .6rem;
  border-radius:999px; color:var(--muted); background:rgba(255,255,255,.07); border:1px solid transparent; }
.chip.pr-low { color:#bfdbfe; background:rgba(59,130,246,.22); border-color:rgba(59,130,246,.6); }
.chip.pr-medium { color:#a5f3fc; background:rgba(0,229,255,.16); border-color:rgba(0,229,255,.55); }
.chip.pr-high { color:#fde68a; background:rgba(255,179,0,.18); border-color:rgba(255,179,0,.65); }
.chip.pr-urgent { color:#fecdd3; background:rgba(255,59,92,.22); border-color:rgba(255,59,92,.75); }
.chip.due-late { color:#fecdd3; background:rgba(255,59,92,.2); border-color:rgba(255,59,92,.5); }
.chip.done { color:#bbf7d0; background:rgba(57,255,20,.14); border-color:rgba(57,255,20,.4); }

.task-card { background:rgba(255,255,255,.045); border:1px solid var(--border); border-left:4px solid var(--neon);
  border-radius:14px; padding:.65rem .9rem; margin:.3rem 0; backdrop-filter:blur(8px);
  animation:fadeUp .35s ease both; transition:transform .2s ease, box-shadow .2s ease, background .2s ease; }
.task-card:hover { transform:translateX(3px); background:rgba(255,255,255,.07); box-shadow:0 0 18px rgba(0,229,255,.18); }
.task-card.pr-low { border-left-color:#3b82f6; } .task-card.pr-medium { border-left-color:#00e5ff; }
.task-card.pr-high { border-left-color:#ffb300; } .task-card.pr-urgent { border-left-color:#ff3b5c; box-shadow:0 0 16px rgba(255,59,92,.22); }
.task-card.overdue { background:rgba(255,59,92,.10); } .task-card.done { opacity:.55; }
.task-title { font-weight:650; font-size:1.02rem; color:var(--text); }
.task-card.done .task-title { text-decoration:line-through; }
.task-meta { margin-top:.4rem; display:flex; flex-wrap:wrap; gap:.4rem; align-items:center; }

/* ---- KPI cards, result banner, transcript bubble */
.kpi { background:var(--glass); border:1px solid var(--border); border-radius:16px; padding:.7rem .5rem; text-align:center;
  backdrop-filter:blur(10px); transition:transform .2s ease, border-color .2s ease; }
.kpi:hover { transform:translateY(-2px); border-color:rgba(0,229,255,.5); }
.kpi .kpi-icon { font-size:1.1rem; } .kpi .kpi-value { font-size:1.7rem; font-weight:800; color:var(--neon); line-height:1.15; }
.kpi .kpi-label { font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.kpi.late .kpi-value { color:var(--red); }

.banner { display:flex; gap:.6rem; align-items:flex-start; padding:.7rem 1rem; border-radius:14px; margin:.4rem 0;
  line-height:1.45; border:1px solid var(--border); backdrop-filter:blur(8px); animation:fadeUp .3s ease both; }
.banner.ok { background:rgba(0,255,157,.10); border-color:rgba(0,255,157,.45); }
.banner.err { background:rgba(255,59,92,.10); border-color:rgba(255,59,92,.45); }
.banner .icon { font-size:1.2rem; }

.bubble { padding:.55rem .85rem; border-radius:14px; margin:.3rem 0; max-width:96%; line-height:1.4;
  background:rgba(139,92,246,.18); border:1px solid rgba(139,92,246,.4); animation:fadeUp .3s ease both; }
.bubble .meta { display:flex; align-items:center; gap:.5rem; margin-top:.35rem; font-size:.7rem; color:var(--muted); }
.meter { flex:0 0 90px; height:5px; border-radius:99px; background:rgba(255,255,255,.1); overflow:hidden; }
.meter > span { display:block; height:100%; border-radius:99px; transition:width .5s ease; }
.hint { color:var(--muted); font-style:italic; padding:.4rem 0; }

@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation:none !important; transition:none !important; } }
</style>
"""


def get_css() -> str:
    """Return the global stylesheet as an HTML <style> block: st.markdown(get_css(), unsafe_allow_html=True)."""
    return _CSS