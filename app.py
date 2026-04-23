#!/usr/bin/env python3
"""
Strava Running Coach — Interface Web para Streamlit Community Cloud
Design system: Apple-inspired · Bento Grid · Inter font
Cloud-adapted: session_state para tudo, st.secrets opcional como pré-preenchimento, OAuth via query params
"""

import json, re, time, warnings
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import requests
import streamlit as st

# ══════════════════════════════════════════════
# CONSTANTS & CLOUD CONFIG
# ══════════════════════════════════════════════
SCOPE        = "activity:read_all"
RUN_TYPES    = {"Run", "VirtualRun", "TrailRun", "Treadmill"}
WALK_TYPES   = {"Walk", "Hike"}
DIAS_SEMANA  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# OAuth redirect URI — tenta secrets, senão session_state (preenchido pelo usuário)
def _get_secret(key, default=""):
    """Busca em st.secrets com fallback seguro (sem erro se secrets vazio)."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def _get_secret_section(section, default=None):
    """Busca seção de secrets (ex: [athlete]) com fallback seguro."""
    try:
        return dict(st.secrets.get(section, default or {}))
    except Exception:
        return default or {}

# ══════════════════════════════════════════════
# DESIGN SYSTEM — Apple + Strava
# ══════════════════════════════════════════════
# Fonte: Inter (substituto SF Pro) via Google Fonts
# Cores: #F5F5F7 bg · #FFFFFF surface · #1D1D1F text · #FC4C02 accent
# Bento grid: radius 18px · shadow 0 2px 20px rgba(0,0,0,0.06)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Reset & Base ───────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif !important;
    background-color: #F5F5F7 !important;
}
#MainMenu, footer, .stDeployButton { visibility: hidden !important; display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container {
    padding: 2.5rem 2.5rem 4rem !important;
    max-width: 980px !important;
    margin: 0 auto !important;
}

/* Mobile responsive */
@media (max-width: 768px) {
    .block-container { padding: 1rem 1rem 3rem !important; }
    .metric-chip { padding: 0.8rem 1rem; }
    .metric-value { font-size: 1.3rem !important; }
    .page-title { font-size: 1.8rem !important; }
}

/* ── Cards ─────────────────────────────────── */
.card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 2px 20px rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.04);
    height: 100%;
    box-sizing: border-box;
}
.card-sm {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 16px rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.04);
}
.card-accent {
    background: linear-gradient(135deg, #FC4C02 0%, #FF6B35 100%);
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 4px 24px rgba(252,76,2,0.28);
}

/* ── Forçar colunas do Streamlit com mesma altura ── */
[data-testid="stHorizontalBlock"] {
    align-items: stretch !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    display: flex !important;
    flex-direction: column !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div {
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
}

/* ── Metric Cards (Bento) ───────────────────── */
.metric-chip {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 16px rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.04);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.metric-chip:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 28px rgba(0,0,0,0.10);
}
.metric-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #6E6E73;
    margin-bottom: 0.45rem;
    display: block;
}
.metric-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1D1D1F;
    line-height: 1;
    display: block;
    letter-spacing: -0.02em;
}
.metric-sub {
    font-size: 0.75rem;
    color: #6E6E73;
    margin-top: 0.3rem;
    display: block;
    font-weight: 400;
}
.metric-badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    margin-top: 0.4rem;
}
.badge-green { background: rgba(52,199,89,0.12); color: #34C759; }
.badge-orange { background: rgba(252,76,2,0.10); color: #FC4C02; }
.badge-yellow { background: rgba(255,204,0,0.15); color: #B8860B; }
.badge-red { background: rgba(255,59,48,0.10); color: #FF3B30; }

/* ── Typography ─────────────────────────────── */
.page-title {
    font-size: 2rem;
    font-weight: 800;
    color: #1D1D1F;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 0;
}
.page-subtitle {
    font-size: 0.9rem;
    color: #6E6E73;
    font-weight: 400;
    margin-top: 0.3rem;
}
.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1D1D1F;
    letter-spacing: -0.01em;
    margin: 0 0 0.8rem;
}
.body-text {
    font-size: 0.92rem;
    color: #3A3A3C;
    line-height: 1.6;
}

/* ── Buttons ────────────────────────────────── */
.stButton > button {
    background: #FC4C02 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.18s ease !important;
    box-shadow: 0 2px 10px rgba(252,76,2,0.22) !important;
    letter-spacing: -0.01em !important;
}
.stButton > button:hover {
    background: #E03400 !important;
    box-shadow: 0 4px 18px rgba(252,76,2,0.35) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Download Button ────────────────────────── */
.stDownloadButton > button {
    background: #1D1D1F !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 0.6rem 1.5rem !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15) !important;
    transition: all 0.18s ease !important;
}
.stDownloadButton > button:hover {
    background: #3A3A3C !important;
    transform: translateY(-1px) !important;
}

/* ── Inputs ─────────────────────────────────── */
.stTextInput input, .stNumberInput input {
    background: #FFFFFF !important;
    border: 1.5px solid rgba(0,0,0,0.12) !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
    padding: 0.55rem 0.85rem !important;
    transition: border-color 0.15s !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #FC4C02 !important;
    box-shadow: 0 0 0 3px rgba(252,76,2,0.12) !important;
    background: #FFFFFF !important;
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
}
/* Labels dos campos */
.stTextInput label, .stNumberInput label,
.stSelectbox label, .stTextArea label,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
}
/* Texto dentro do selectbox */
.stSelectbox [data-baseweb="select"] span,
.stSelectbox [data-baseweb="select"] div {
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
}
.stSelectbox > div > div {
    background: #FFFFFF !important;
    border: 1.5px solid rgba(0,0,0,0.12) !important;
    border-radius: 10px !important;
    font-size: 0.9rem !important;
    color: #1D1D1F !important;
}
/* Placeholder */
.stTextInput input::placeholder, .stNumberInput input::placeholder {
    color: #AEAEB2 !important;
    -webkit-text-fill-color: #AEAEB2 !important;
}
.stSlider > div { padding: 0 0.2rem; }

/* ── Tabs ───────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    gap: 0 !important;
    border-bottom: 1.5px solid rgba(0,0,0,0.08) !important;
    padding-bottom: 0 !important;
    margin-bottom: 1.5rem !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #6E6E73 !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    padding: 0.65rem 1.1rem !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -1.5px !important;
}
.stTabs [aria-selected="true"] {
    color: #1D1D1F !important;
    font-weight: 700 !important;
    border-bottom: 2px solid #FC4C02 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 0 !important; }

/* ── Expander ───────────────────────────────── */
.streamlit-expanderHeader,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary div,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"],
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
    background: #FFFFFF !important;
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}
[data-testid="stExpander"] > details {
    border-radius: 12px !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
    background: #FFFFFF !important;
}
[data-testid="stExpander"] summary {
    padding: 0.8rem 1rem !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] svg {
    fill: #1D1D1F !important;
    stroke: #1D1D1F !important;
}

/* ── Status pills ───────────────────────────── */
.pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.3rem 0.75rem;
    border-radius: 20px;
}
.pill-green { background: rgba(52,199,89,0.12); color: #1A7A35; }
.pill-red { background: rgba(255,59,48,0.10); color: #D70015; }

/* ── Form sections ──────────────────────────── */
.form-section {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 1px 12px rgba(0,0,0,0.05);
    border: 1px solid rgba(0,0,0,0.04);
    margin-bottom: 1rem;
}
.form-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6E6E73;
    margin-bottom: 0.8rem;
    display: block;
}

/* ── Result sections ────────────────────────── */
.result-section {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.6rem 1.8rem;
    box-shadow: 0 2px 20px rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.04);
    margin-bottom: 1rem;
}
.result-section h2 {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #1D1D1F !important;
    margin-bottom: 0.9rem !important;
    padding-bottom: 0.6rem !important;
    border-bottom: 1.5px solid #F5F5F7 !important;
}

/* ── Table / DataFrame ──────────────────────── */
.stDataFrame { border-radius: 14px !important; overflow: hidden !important; }
[data-testid="stDataFrameContainer"] { border-radius: 14px !important; }

/* Forçar cor preta em todas as células do AG Grid (dataframe interno do Streamlit) */
[data-testid="stDataFrame"] .ag-cell,
[data-testid="stDataFrame"] .ag-cell-value,
[data-testid="stDataFrame"] .ag-header-cell-label,
[data-testid="stDataFrame"] .ag-header-cell-text,
[data-testid="stDataFrame"] span,
[data-testid="stDataFrame"] div,
[data-testid="stDataFrame"] p,
.dvn-scroller *,
.glide-data-grid canvas ~ div,
[class*="dvn"] span,
[class*="DataGrid"] span {
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
}
/* Header do AG Grid */
[data-testid="stDataFrame"] .ag-header-cell {
    background: #F5F5F7 !important;
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
}

/* ── Alerts ─────────────────────────────────── */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 12px !important;
    font-size: 0.88rem !important;
}

/* ── Checkbox ───────────────────────────────── */
.stCheckbox label { font-size: 0.9rem !important; font-weight: 500 !important; }
.stCheckbox [data-baseweb="checkbox"] { accent-color: #FC4C02; }

/* ── Spinner ────────────────────────────────── */
.stSpinner > div { border-top-color: #FC4C02 !important; }

/* ── Divider ────────────────────────────────── */
hr { border: none !important; border-top: 1.5px solid rgba(0,0,0,0.06) !important; margin: 1.2rem 0 !important; }
"""

# ══════════════════════════════════════════════
# SESSION STATE HELPERS (Cloud-adapted)
# ══════════════════════════════════════════════

def init_session_state():
    """Inicializa session_state com valores padrão.
       secrets.toml é 100% opcional — tudo pode ser preenchido pelo app."""
    defaults = {
        "strava_tokens": None,
        "athlete": {
            "nome": "Nikola",
            "nivel": "intermediário",
            "objetivo": "Completar meia maratona em 30 dias",
            "treinos_semana": 3,
            "fc_max": 185,
            "fc_repouso": 50,
            "pace_limiar": "06:00",
            "dias_descanso": [0, 2],
        },
        "suggestion": None,
        "_atl": None,
        "_ctl": None,
        "_tsb": None,
        # Credenciais via st.secrets (configuradas no painel do Streamlit Cloud)
        "client_id": _get_secret("client_id", ""),
        "client_secret": _get_secret("client_secret", ""),
        "anthropic_key": _get_secret("anthropic_key", ""),
        "redirect_uri": _get_secret("redirect_uri",
            "https://stravarunningcoach.streamlit.app"),
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def get_athlete_profile():
    """Retorna perfil do atleta de session_state."""
    return st.session_state.athlete or {}

def get_credentials():
    """Retorna credenciais de session_state."""
    return (st.session_state.client_id,
            st.session_state.client_secret,
            st.session_state.anthropic_key)

def save_athlete_profile(athlete_dict):
    """Salva perfil do atleta em session_state."""
    st.session_state.athlete = athlete_dict

def get_strava_tokens():
    """Retorna tokens do Strava armazenados em session_state."""
    return st.session_state.strava_tokens

def save_strava_tokens(tokens):
    """Salva tokens do Strava em session_state."""
    st.session_state.strava_tokens = tokens

# ══════════════════════════════════════════════
# STRAVA AUTH (Cloud-adapted)
# ══════════════════════════════════════════════

def _req(method, url, **kw):
    return getattr(requests, method)(url, verify=False, timeout=15, **kw)

def exchange_code(cid, cs, code):
    r = _req("post", "https://www.strava.com/oauth/token",
             data={"client_id": cid, "client_secret": cs,
                   "code": code, "grant_type": "authorization_code"})
    r.raise_for_status()
    return r.json()

def refresh_strava_token(cid, cs, rt):
    r = _req("post", "https://www.strava.com/oauth/token",
             data={"client_id": cid, "client_secret": cs,
                   "refresh_token": rt, "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()

def get_valid_token(cid, cs):
    """Retorna token válido do Strava, refreshando se necessário."""
    t = get_strava_tokens()
    if not t:
        return None
    if time.time() > t.get("expires_at", 0) - 300:
        data = refresh_strava_token(cid, cs, t["refresh_token"])
        t.update({"access_token": data["access_token"],
                  "refresh_token": data["refresh_token"],
                  "expires_at": data["expires_at"]})
        save_strava_tokens(t)
    return t["access_token"]

def _detect_app_url():
    """Tenta detectar a URL do app automaticamente via query params."""
    # Se o usuário já preencheu, usa isso
    stored = st.session_state.get("redirect_uri", "")
    if stored:
        return stored
    # Fallback: tenta montar a partir do host (funciona no Streamlit Cloud)
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        if headers and headers.get("Host"):
            host = headers["Host"]
            return f"https://{host}"
    except Exception:
        pass
    return "http://localhost"

def build_auth_url(cid):
    """Constrói URL de autorização do Strava."""
    redirect = _detect_app_url()
    return (f"https://www.strava.com/oauth/authorize?client_id={cid}"
            f"&response_type=code&redirect_uri={redirect}"
            f"&approval_prompt=force&scope={SCOPE}")

def handle_oauth_callback():
    """Detecta e processa callback do OAuth via query params."""
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        try:
            cid = st.session_state.get("client_id", "")
            cs  = st.session_state.get("client_secret", "")
            if not cid or not cs:
                st.error("Client ID e Secret não configurados. Preencha na aba Configurações.")
                return False
            data = exchange_code(cid, cs, code)
            save_strava_tokens({
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": data["expires_at"]
            })
            st.query_params.clear()
            st.success(f"Conectado! Bem-vindo, {data.get('athlete', {}).get('firstname', 'Atleta')}!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro na autenticação: {e}")
            return False
    return True

# ══════════════════════════════════════════════
# STRAVA DATA
# ══════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def fetch_runs(token, days=28):
    """Cache de 5 min — evita chamar Strava em cada rerender do Streamlit."""
    after = int((datetime.now() - timedelta(days=days)).timestamp())
    r = _req("get", "https://www.strava.com/api/v3/athlete/activities",
             headers={"Authorization": f"Bearer {token}"},
             params={"after": after, "per_page": 50})
    r.raise_for_status()
    all_types = RUN_TYPES | WALK_TYPES
    activities = [a for a in r.json() if (a.get("sport_type") or a.get("type")) in all_types]
    for a in activities:
        a["_is_walk"] = (a.get("sport_type") or a.get("type", "")) in WALK_TYPES
    activities.sort(key=lambda x: x["start_date"], reverse=True)
    return activities

# ══════════════════════════════════════════════
# FORMATAÇÃO
# ══════════════════════════════════════════════

def fmt_pace(spd):
    if not spd: return "—"
    m, s = divmod(int(1000 / spd), 60)
    return f"{m}:{s:02d} /km"

def fmt_dist(m): return f"{m/1000:.2f} km"
def fmt_dur(s):
    h, r = divmod(int(s), 3600)
    m, _ = divmod(r, 60)
    return f"{h}h{m:02d}min" if h else f"{m}min"

def week_num(ds):
    return datetime.fromisoformat(ds.replace("Z", "+00:00")).isocalendar()[1]

# ══════════════════════════════════════════════
# MÉTRICAS
# ══════════════════════════════════════════════

def pace_secs(p):
    try:
        a, b = p.split(":")
        return int(a)*60 + int(b)
    except: return None

def run_load(run, ath):
    dur = run.get("moving_time", 0) / 60
    if not dur: return 0.0
    fc_max, fc_rep = ath.get("fc_max", 185), ath.get("fc_repouso", 50)
    hr = run.get("average_heartrate")
    if hr:
        d = max(0.0, min((hr - fc_rep) / max(fc_max - fc_rep, 1), 1.0))
        load = dur * d * 0.64 * (2.71828 ** (1.92 * d))
        if run.get("_is_walk"):
            load *= 0.5   # caminhada = carga regenerativa
        return round(load, 1)
    dist = run.get("distance", 0) / 1000
    spd  = run.get("average_speed", 0)
    if run.get("_is_walk"):
        return round(dist * 0.3, 1)   # caminhada sem HR → carga mínima
    if spd:
        return round(dist * (pace_secs(ath.get("pace_limiar","5:30")) or 330) / (1000/spd), 1)
    return round(dist * 0.8, 1)

def loads_by_day(runs, ath):
    r = {}
    for x in runs:
        d = x["start_date"][:10]
        r[d] = r.get(d, 0) + run_load(x, ath)
    return r

def atl_ctl_tsb(lbd):
    today = datetime.now().date()
    a = sum(lbd.get((today-timedelta(days=i)).isoformat(),0) for i in range(7)) / 7
    c = sum(lbd.get((today-timedelta(days=i)).isoformat(),0) for i in range(28)) / 28
    return round(a,1), round(c,1), round(c-a,1)

def tsb_label(tsb):
    if tsb > 10:   return "Descansado", "badge-green"
    if tsb >= 0:   return "Em forma", "badge-green"
    if tsb >= -10: return "Leve fadiga", "badge-yellow"
    return "Fadiga alta", "badge-red"

def hr_zones(runs, fc_max, fc_rep):
    z = {1:0., 2:0., 3:0., 4:0., 5:0.}
    for r in runs:
        hr = r.get("average_heartrate")
        if not hr: continue
        dur = r.get("moving_time",0)/60
        p = (hr-fc_rep)/max(fc_max-fc_rep,1)
        for lim,zn in [(0.60,1),(0.70,2),(0.80,3),(0.90,4),(1.01,5)]:
            if p < lim: z[zn] += dur; break
    tot = sum(z.values())
    return {f"Z{k}": f"{round(v/tot*100)}%" for k,v in z.items()} if tot else None

def pace_trend(runs):
    v = [r for r in runs if r.get("average_speed")]
    if len(v) < 4: return None
    h = len(v)//2
    old = sum(1000/r["average_speed"] for r in v[h:]) / (len(v)-h)
    new = sum(1000/r["average_speed"] for r in v[:h]) / h
    d = old - new
    if d > 5:  return f"↑ {d:.0f}s/km mais rápido"
    if d < -5: return f"↓ {abs(d):.0f}s/km mais lento"
    return "→ Estável"

def days_off(runs):
    if not runs: return None
    last = datetime.fromisoformat(runs[0]["start_date"].replace("Z","+00:00"))
    return (datetime.now(tz=last.tzinfo) - last).days

# ══════════════════════════════════════════════
# GERAÇÃO IA
# ══════════════════════════════════════════════

def generate(runs, ath, api_key):
    lbd = loads_by_day(runs, ath)
    atl, ctl, tsb = atl_ctl_tsb(lbd)

    run_only  = [r for r in runs if not r.get("_is_walk")]
    walk_only = [r for r in runs if r.get("_is_walk")]

    wk = {}
    for r in run_only:
        k = f"Sem {week_num(r['start_date'])}"
        wk[k] = round(wk.get(k,0) + r["distance"]/1000, 1)
    vol_str = " | ".join(f"{k}: {v} km" for k,v in list(wk.items())[-4:])

    zones = hr_zones(run_only or runs, ath.get("fc_max",185), ath.get("fc_repouso",50))
    doff  = days_off(runs)
    trend = pace_trend(run_only or runs)

    dias_pt_full = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"]

    recent = []
    for r in (run_only or runs)[:15]:
        dt = datetime.strptime(r["start_date"][:10], "%Y-%m-%d")
        recent.append({
            "data": r["start_date"][:10],
            "dia_semana": dias_pt_full[dt.weekday()],
            "distancia_km": round(r["distance"]/1000, 2),
            "duracao": fmt_dur(r.get("moving_time",0)),
            "pace": fmt_pace(r.get("average_speed")),
            "fc_media_bpm": round(r["average_heartrate"]) if r.get("average_heartrate") else None,
            "elevacao_m": round(r.get("total_elevation_gain",0)),
            "carga": run_load(r, ath),
        })

    recent_walks = []
    for w in walk_only[:8]:
        dt = datetime.strptime(w["start_date"][:10], "%Y-%m-%d")
        recent_walks.append({
            "data": w["start_date"][:10],
            "dia_semana": dias_pt_full[dt.weekday()],
            "distancia_km": round(w["distance"]/1000, 2),
            "duracao": fmt_dur(w.get("moving_time",0)),
            "fc_media_bpm": round(w["average_heartrate"]) if w.get("average_heartrate") else None,
            "carga_regenerativa": run_load(w, ath),
        })

    dias_pt = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]
    hoje = datetime.now()
    dia  = dias_pt[hoje.weekday()]
    desc_idx = ath.get("dias_descanso",[0,2])
    eh_desc  = hoje.weekday() in desc_idx
    nms_desc = [dias_pt[i] for i in desc_idx]
    dias_tr  = [d for i,d in enumerate(dias_pt) if i not in desc_idx]

    nota_dia = (f"{dia} — DIA DE DESCANSO. Sugira recuperação ativa ou descanso total."
                if eh_desc else f"{dia} — dia de treino disponível.")

    race = ""
    if ath.get("prova_alvo") and ath.get("data_prova"):
        try:
            dd = (datetime.fromisoformat(ath["data_prova"]).date() - hoje.date()).days
            race = f"\n- Prova: {ath['prova_alvo']} em {dd} dias"
        except: pass
    elif ath.get("objetivo"):
        race = f"\n- Objetivo: {ath['objetivo']}"

    zstr = f"\n- Zonas FC: {zones} (ref: 80% Z1-Z2 / 20% Z3-Z5)" if zones else ""
    tstr = f"\n- Tendência de pace: {trend}" if trend else ""

    if doff == 0: rec = "Já treinou hoje."
    elif doff == 1: rec = "Treinou ontem."
    elif doff == 2: rec = "2 dias de descanso."
    elif doff and doff >= 3: rec = f"{doff} dias sem treinar."
    else: rec = "Não identificado."

    tsb_txt, _ = tsb_label(tsb)

    prompt = f"""Você é um treinador de corrida de alto rendimento. Seu estilo: direto, sem elogios vazios, baseado em dados reais. Você diz a verdade mesmo quando dói. Seu objetivo é extrair o máximo do atleta dentro dos limites fisiológicos seguros.

REGRAS DE TREINAMENTO QUE VOCÊ APLICA:
- Progressão máxima: +10% volume/semana (regra de ouro anti-lesão)
- Polarização: 80% do volume em Z1-Z2 (aeróbico leve), 20% em Z3-Z5 (intensidade)
- TSB ideal para treino duro: entre -5 e +5 (forma ótima); acima de +15 = atleta descansado demais
- TSB < -15: risco real de overtraining — recuo obrigatório
- Dias de descanso: sagrados. Nas folgas, no máximo recuperação ativa (caminhada leve)
- Se o atleta está abaixo do potencial: aumentar volume ou intensidade sem piedade
- Se está em fadiga elevada: reduzir sem hesitar, mesmo que o atleta não queira

## PERFIL
- Nome: {ath.get('nome','Atleta')} | Nível: {ath.get('nivel','intermediário')}
- {ath.get('treinos_semana',3)} treinos/sem ({', '.join(dias_tr)}) | Descanso: {', '.join(nms_desc)}
- Pace limiar: {ath.get('pace_limiar','5:30')}/km | FC max: {ath.get('fc_max',185)} bpm | FC rep: {ath.get('fc_repouso',50)} bpm{race}

## DIA ATUAL
- {nota_dia}

## CARGA (TRIMP — Banister 1991)
- ATL 7d: {atl} (fadiga aguda) | CTL 28d: {ctl} (condicionamento) | TSB: {tsb:+.1f} → {tsb_txt}
- Recuperação desde último treino: {rec}{tstr}{zstr}

## VOLUMES POR SEMANA
{vol_str or "Sem dados suficientes — atleta iniciante ou com pouco histórico"}

## CORRIDAS RECENTES (até 15)
{json.dumps(recent, ensure_ascii=False, indent=2)}

## CAMINHADAS REGENERATIVAS (último mês)
{json.dumps(recent_walks, ensure_ascii=False, indent=2) if recent_walks else "Nenhuma caminhada registrada."}

---
INSTRUÇÕES DE RESPOSTA — siga EXATAMENTE este formato markdown, sem introduções, sem "Olá":

## 📊 Análise honesta
(Seja direto. Aponte o que está bom E o que está ruim nos dados. Mencione o TSB exato, tendência de pace, distribuição de zonas se disponível. Se o atleta está andando devagar demais para o objetivo, diga. Se está treinando pouco, diga. Máx 6 linhas.)

## 🏃 Treino de hoje
- **Tipo:** (seja específico: Intervalado, Progressivo, Longo, Regenerativo, Fartlek, Tempo Run, etc.)
- **Distância total:** X,X km
- **Pace alvo:** X:XX – X:XX /km por zona/bloco
- **Estrutura detalhada:** (descreva cada bloco com distância/tempo, pace exato e FC alvo se disponível — ex: "2 km aquecimento Z1 a 6:30/km → 5x1000m a 4:15/km com 90s de trote → 1 km desaquecimento Z1")
- **Por que este treino:** (justifique com os dados reais de TSB, fadiga e objetivo)

## 📅 Semana completa
Distribua os {ath.get('treinos_semana',3)} treinos nos dias disponíveis ({', '.join(dias_tr)}) com descanso em {', '.join(nms_desc)}. Seja agressivo mas inteligente: alterne intensidade alta / baixa, nunca dois treinos duros seguidos.
Formato: Seg: ... | Ter: ... | Qua: ... | Qui: ... | Sex: ... | Sáb: ... | Dom: ...

## ⚠️ Alerta do treinador
(Se houver algo preocupante nos dados — fadiga acumulada, queda de pace, falta de Z1-Z2, volume baixo para o objetivo — escreva aqui sem suavizar. Se estiver tudo bem, escreva "Sem alertas críticos.")"""

    # Tenta claude-sonnet-4-6; se o modelo não existir na conta, usa versão anterior
    for model in ["claude-sonnet-4-6", "claude-3-5-sonnet-20241022"]:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": model, "max_tokens": 2048,
                  "messages": [{"role": "user", "content": prompt}]},
            verify=False, timeout=90,
        )
        if r.status_code == 404:
            continue   # modelo não disponível nesta conta → tenta o próximo
        if not r.ok:
            try:
                detail = r.json().get("error", {}).get("message", r.text[:400])
            except Exception:
                detail = r.text[:400]
            raise Exception(f"API Anthropic {r.status_code}: {detail}")
        data = r.json()
        if "content" not in data:
            raise Exception(f"Resposta inesperada da API: {str(data)[:300]}")
        return data["content"][0]["text"], atl, ctl, tsb
    raise Exception("Nenhum modelo disponível para esta API Key. Verifique o plano da sua conta Anthropic.")

# ══════════════════════════════════════════════
# PDF
# ══════════════════════════════════════════════

def make_pdf(suggestion, ath, runs, atl, ctl, tsb):
    import io, locale
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable, KeepTogether)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    PAGE_W, PAGE_H = A4
    ML, MR, MT, MB = 22*mm, 22*mm, 38*mm, 22*mm
    CONTENT_W = PAGE_W - ML - MR

    # ── Paleta ────────────────────────────────────────────
    ORANGE  = colors.HexColor("#FC4C02")
    ORANGE2 = colors.HexColor("#FF6B35")
    DARK    = colors.HexColor("#1D1D1F")
    MID     = colors.HexColor("#3A3A3C")
    GREY    = colors.HexColor("#6E6E73")
    LIGHT   = colors.HexColor("#F5F5F7")
    DIVIDER = colors.HexColor("#E5E5EA")
    GREEN   = colors.HexColor("#1A8A3A")
    YELLOW  = colors.HexColor("#B85C00")
    RED     = colors.HexColor("#D70015")
    WHITE   = colors.white

    hoje = datetime.now()
    nome = ath.get("nome", "Atleta")
    nivel = ath.get("nivel", "intermediário").capitalize()
    objetivo = ath.get("objetivo", "")

    # ── Decoração de página (header + footer em todas) ──
    def draw_page(cv, doc):
        cv.saveState()
        # Banda laranja no topo
        cv.setFillColor(ORANGE)
        cv.rect(0, PAGE_H - 26*mm, PAGE_W, 26*mm, fill=1, stroke=0)
        # Listra de acento
        cv.setFillColor(colors.HexColor("#D94000"))
        cv.rect(0, PAGE_H - 27.5*mm, PAGE_W, 1.5*mm, fill=1, stroke=0)
        # Texto do header
        cv.setFillColor(WHITE)
        cv.setFont("Helvetica-Bold", 13)
        cv.drawString(ML, PAGE_H - 14*mm, "RUNNING COACH")
        cv.setFont("Helvetica", 8.5)
        cv.setFillColor(colors.HexColor("#FFD0B8"))
        cv.drawString(ML, PAGE_H - 21*mm, f"Powered by Strava + Claude AI")
        cv.setFillColor(WHITE)
        cv.setFont("Helvetica", 9)
        cv.drawRightString(PAGE_W - MR, PAGE_H - 14*mm,
                           f"{nome}  ·  {hoje.strftime('%d/%m/%Y')}")
        # Footer
        cv.setFillColor(DIVIDER)
        cv.rect(ML, MB - 6*mm, CONTENT_W, 0.4, fill=1, stroke=0)
        cv.setFont("Helvetica", 7.5)
        cv.setFillColor(GREY)
        cv.drawString(ML, MB - 10*mm, "Strava Running Coach  ·  Análise gerada por Claude AI")
        cv.drawRightString(PAGE_W - MR, MB - 10*mm, f"Página {doc.page}")
        cv.restoreState()

    # ── Estilos ───────────────────────────────────────────
    S = {
        "title":   ParagraphStyle("title",  fontName="Helvetica-Bold", fontSize=28,
                                  textColor=DARK, spaceAfter=1*mm, leading=32),
        "sub":     ParagraphStyle("sub",    fontName="Helvetica",      fontSize=11,
                                  textColor=GREY, spaceAfter=6*mm),
        "section": ParagraphStyle("section",fontName="Helvetica-Bold", fontSize=11,
                                  textColor=ORANGE, spaceBefore=4*mm, spaceAfter=2.5*mm),
        "body":    ParagraphStyle("body",   fontName="Helvetica",      fontSize=9.5,
                                  textColor=MID, spaceAfter=2*mm, leading=14),
        "bullet":  ParagraphStyle("bullet", fontName="Helvetica",      fontSize=9.5,
                                  textColor=MID, leftIndent=5*mm, spaceAfter=2*mm, leading=14),
        "lbl":     ParagraphStyle("lbl",    fontName="Helvetica",      fontSize=7,
                                  textColor=WHITE, alignment=1),
        "val":     ParagraphStyle("val",    fontName="Helvetica-Bold", fontSize=16,
                                  textColor=WHITE, alignment=1, leading=18),
        "val_sub": ParagraphStyle("val_sub",fontName="Helvetica",      fontSize=7.5,
                                  textColor=colors.HexColor("#FFD0B8"), alignment=1),
        "th":      ParagraphStyle("th",     fontName="Helvetica-Bold", fontSize=7.5,
                                  textColor=WHITE, alignment=1),
        "td":      ParagraphStyle("td",     fontName="Helvetica",      fontSize=8.5,
                                  textColor=DARK,  alignment=0),
        "td_c":    ParagraphStyle("td_c",   fontName="Helvetica",      fontSize=8.5,
                                  textColor=DARK,  alignment=1),
        "td_run":  ParagraphStyle("td_run", fontName="Helvetica-Bold", fontSize=8,
                                  textColor=ORANGE, alignment=1),
        "td_walk": ParagraphStyle("td_walk",fontName="Helvetica-Bold", fontSize=8,
                                  textColor=GREEN,  alignment=1),
    }

    # ── Dados ─────────────────────────────────────────────
    run_only_pdf  = [r for r in runs if not r.get("_is_walk")]
    walk_only_pdf = [r for r in runs if r.get("_is_walk")]
    ref_pdf = run_only_pdf if run_only_pdf else runs
    total_km = sum(r["distance"] for r in run_only_pdf) / 1000
    avg_pace = fmt_pace(sum(r.get("average_speed",0) for r in ref_pdf) / len(ref_pdf)) if ref_pdf else "—"
    tsb_txt, _ = tsb_label(tsb)
    tsb_bg = GREEN if tsb >= 0 else (colors.HexColor("#FF9500") if tsb >= -10 else RED)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=MT, bottomMargin=MB)
    story = []

    # ── Cabeçalho hero ────────────────────────────────────
    story.append(Paragraph(nome, S["title"]))
    sub_parts = [nivel]
    if objetivo: sub_parts.append(objetivo)
    sub_parts.append(hoje.strftime("%d de %B de %Y"))
    story.append(Paragraph("  ·  ".join(sub_parts), S["sub"]))

    # ── Cards de métricas ─────────────────────────────────
    def mcard(lbl, val, sub, bg=ORANGE):
        inner = Table([
            [Paragraph(lbl, S["lbl"])],
            [Paragraph(str(val), S["val"])],
            [Paragraph(sub, S["val_sub"])],
        ], colWidths=[CONTENT_W/4 - 2*mm])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), bg),
            ("ALIGN",      (0,0), (-1,-1), "CENTER"),
            ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ]))
        return inner

    cw = CONTENT_W / 4
    metrics = Table([[
        mcard("VOLUME 28 DIAS", f"{total_km:.1f} km",
              f"{len(run_only_pdf)} corridas"),
        mcard("PACE MÉDIO",     avg_pace,
              "corridas"),
        mcard("ATL / CTL",      f"{atl} / {ctl}",
              "fadiga / condicionamento"),
        mcard("FORMA (TSB)",    f"{tsb:+.1f}",
              tsb_txt, bg=tsb_bg),
    ]], colWidths=[cw]*4, rowHeights=22*mm)
    metrics.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 1),
        ("RIGHTPADDING",(0,0), (-1,-1), 1),
    ]))
    story.append(metrics)
    story.append(Spacer(1, 5*mm))

    # ── Função de separador de seção ─────────────────────
    def sec(title):
        tbl = Table(
            [[Paragraph(title, S["section"])]],
            colWidths=[CONTENT_W],
            rowHeights=[8*mm],
            style=[
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("TOPPADDING",    (0,0), (-1,-1), 0),
                ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                ("LINEBELOW",     (0,0), (-1,-1), 0.4, DIVIDER),
                ("LINEBEFORE",    (0,0), (0,-1),  2.5, ORANGE),
            ],
        )
        return tbl

    # ── Tabela de atividades ──────────────────────────────
    lbl_a = (f"Histórico de Atividades — {len(run_only_pdf)} corridas" +
             (f" + {len(walk_only_pdf)} caminhadas" if walk_only_pdf else ""))
    story.append(sec(lbl_a))

    col_w = [22*mm, 22*mm, 25*mm, 21*mm, 25*mm, 19*mm]
    hdr = [Paragraph(h, S["th"]) for h in
           ["DATA", "TIPO", "DISTÂNCIA", "DURAÇÃO", "PACE", "CARGA"]]
    act_rows = [hdr]
    for r in runs[:12]:
        is_w = r.get("_is_walk", False)
        carga_str = f"{run_load(r,ath):.0f}" + (" ♻" if is_w else "")
        act_rows.append([
            Paragraph(r["start_date"][:10],               S["td_c"]),
            Paragraph("Caminhada" if is_w else "Corrida",
                      S["td_walk"] if is_w else S["td_run"]),
            Paragraph(fmt_dist(r["distance"]),             S["td_c"]),
            Paragraph(fmt_dur(r.get("moving_time",0)),     S["td_c"]),
            Paragraph(fmt_pace(r.get("average_speed")),    S["td_c"]),
            Paragraph(carga_str,                           S["td_c"]),
        ])
    act_tbl = Table(act_rows, colWidths=col_w, repeatRows=1)
    act_tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0),  DARK),
        ("TEXTCOLOR",      (0,0), (-1,0),  WHITE),
        ("ALIGN",          (0,0), (-1,0),  "CENTER"),
        ("TOPPADDING",     (0,0), (-1,0),  5),
        ("BOTTOMPADDING",  (0,0), (-1,0),  5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
        ("LINEBELOW",      (0,0), (-1,-1), 0.3, DIVIDER),
        ("BOX",            (0,0), (-1,-1), 0.5, DIVIDER),
        ("TOPPADDING",     (0,1), (-1,-1), 4),
        ("BOTTOMPADDING",  (0,1), (-1,-1), 4),
        ("LEFTPADDING",    (0,0), (-1,-1), 5),
        ("RIGHTPADDING",   (0,0), (-1,-1), 5),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
        ("FONTSIZE",       (0,0), (-1,-1), 8.5),
    ]))
    story.append(act_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Análise da IA ─────────────────────────────────────
    strip = lambda t: "".join(c for c in t if ord(c) < 0x2500)
    for line in suggestion.splitlines():
        c = strip(line.rstrip()).strip()
        if not c:
            story.append(Spacer(1, 1.5*mm)); continue
        if c.startswith("## "):
            story.append(sec(c[3:].strip()))
        elif c.startswith("- "):
            fmt = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', c[2:])
            story.append(Paragraph("• " + fmt, S["bullet"]))
        elif not (c.startswith("(") and c.endswith(")")):
            fmt = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', c)
            story.append(Paragraph(fmt, S["body"]))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf.read()

# ══════════════════════════════════════════════
# COMPONENTES UI
# ══════════════════════════════════════════════

def metric_card(label, value, sub=None, badge=None, badge_cls="badge-green"):
    sub_html  = f'<span class="metric-sub">{sub}</span>' if sub else ""
    bdg_html  = f'<span class="metric-badge {badge_cls}">{badge}</span>' if badge else ""
    return f"""<div class="metric-chip">
        <span class="metric-label">{label}</span>
        <span class="metric-value">{value}</span>
        {sub_html}{bdg_html}
    </div>"""

def render_results(suggestion):
    """Renderiza cada seção da sugestão num card separado."""
    sections = re.split(r'\n(?=## )', suggestion.strip())
    for sec in sections:
        lines = sec.strip().splitlines()
        if not lines: continue
        header = lines[0].replace("## ", "").strip()
        body_lines = lines[1:]
        # Converter markdown simples para HTML
        body_html = ""
        for ln in body_lines:
            ln = ln.strip()
            if not ln: body_html += "<br>"; continue
            # Bold
            ln = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ln)
            if ln.startswith("- "):
                body_html += f'<li style="margin-bottom:0.4rem;color:#3A3A3C;font-size:0.9rem">{ln[2:]}</li>'
            else:
                body_html += f'<p style="margin:0 0 0.4rem;color:#3A3A3C;font-size:0.9rem;line-height:1.65">{ln}</p>'

        if any(ln.startswith("- ") for ln in body_lines):
            body_html = f'<ul style="padding-left:1.2rem;margin:0">{body_html}</ul>'

        st.markdown(f"""<div class="result-section">
            <h2>{header}</h2>
            {body_html}
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# APP PRINCIPAL
# ══════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Strava Running Coach",
        page_icon="🏃",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

    # Inicializa session state
    init_session_state()

    # Processa OAuth callback
    if not handle_oauth_callback():
        return

    # Carrega credenciais de session_state (preenchidas pelo app ou via secrets)
    cid, cs, akey = get_credentials()

    # Carrega dados de session_state
    tokens = get_strava_tokens()
    ath    = get_athlete_profile()

    connected = bool(tokens)

    # ── Header ───────────────────────────────
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.markdown("""<div>
            <p class="page-title">Running Coach</p>
            <p class="page-subtitle">Powered by Strava + Claude AI</p>
        </div>""", unsafe_allow_html=True)
    with col_status:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if connected:
            nome = ath.get("nome", "")
            st.markdown(f'<span class="pill pill-green">● Conectado{" · "+nome if nome else ""}</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<span class="pill pill-red">● Desconectado</span>', unsafe_allow_html=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Tabs ─────────────────────────────────
    tab_home, tab_config = st.tabs(["  🏃  Treino  ", "  ⚙️  Configurações  "])

    # ══════════════════════════════════════════
    # TAB: CONFIGURAÇÕES
    # ══════════════════════════════════════════
    with tab_config:

        # Credenciais (editáveis — salvas em session_state)
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Credenciais de API</span>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            client_id_v = st.text_input("Strava Client ID", value=cid,
                                        placeholder="214364")
        with c2:
            client_secret_v = st.text_input("Strava Client Secret", value=cs,
                                            type="password", placeholder="••••••••")
        anthropic_v = st.text_input("Anthropic API Key", value=akey,
                                    type="password", placeholder="sk-ant-...")
        redirect_v = st.text_input("URL do App (para OAuth)",
                                   value=st.session_state.get("redirect_uri", ""),
                                   placeholder="https://seu-app.streamlit.app",
                                   help="Cole aqui a URL do seu app no Streamlit Cloud")
        if st.button("Salvar credenciais", key="save_creds"):
            st.session_state.client_id = client_id_v
            st.session_state.client_secret = client_secret_v
            st.session_state.anthropic_key = anthropic_v
            st.session_state.redirect_uri = redirect_v
            st.success("Credenciais salvas na sessão.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Perfil do Atleta (editável em session_state)
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Perfil do Atleta</span>', unsafe_allow_html=True)
        p = ath
        pc1, pc2 = st.columns(2)
        with pc1:
            nome_v  = st.text_input("Nome", value=p.get("nome",""), placeholder="Seu nome")
            obj_v   = st.text_input("Objetivo", value=p.get("objetivo",""),
                                    placeholder="ex: completar meia maratona")
            prova_v = st.text_input("Prova alvo (opcional)", value=p.get("prova_alvo",""),
                                    placeholder="ex: Maratona de SP")
            data_v  = st.text_input("Data da prova (opcional)", value=p.get("data_prova",""),
                                    placeholder="AAAA-MM-DD")
        with pc2:
            nivel_v   = st.selectbox("Nível", ["iniciante","intermediário","avançado"],
                                     index=["iniciante","intermediário","avançado"].index(
                                         p.get("nivel","intermediário")))
            treinos_v = st.slider("Treinos por semana", 2, 6, value=p.get("treinos_semana",3))
            fc_max_v  = st.number_input("FC máxima (bpm)", 140, 220,
                                        value=p.get("fc_max",185),
                                        help="Estimativa: 220 − sua idade")
            fc_rep_v  = st.number_input("FC repouso (bpm)", 30, 80,
                                        value=p.get("fc_repouso",50))
        pace_v = st.text_input("Pace limiar (mm:ss /km)", value=p.get("pace_limiar","5:30"),
                               placeholder="ex: 5:30",
                               help="Pace que você sustenta por ~1 hora no máximo")
        if st.button("Salvar perfil", key="save_profile"):
            new_ath = {
                "nome": nome_v, "nivel": nivel_v, "objetivo": obj_v,
                "prova_alvo": prova_v, "data_prova": data_v,
                "treinos_semana": treinos_v, "fc_max": fc_max_v,
                "fc_repouso": fc_rep_v, "pace_limiar": pace_v,
                "dias_descanso": ath.get("dias_descanso",[0,2]),
            }
            save_athlete_profile(new_ath)
            st.success("Perfil salvo na sessão.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Dias de descanso
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Dias de Descanso Fixos</span>', unsafe_allow_html=True)
        desc_cfg = ath.get("dias_descanso", [0, 2])
        cols_dias = st.columns(7)
        selecionados = []
        for i, (col, dia) in enumerate(zip(cols_dias, DIAS_SEMANA)):
            with col:
                if st.checkbox(dia[:3], value=(i in desc_cfg), key=f"d{i}"):
                    selecionados.append(i)
        if st.button("Salvar dias", key="save_days"):
            new_ath = ath.copy()
            new_ath["dias_descanso"] = selecionados
            save_athlete_profile(new_ath)
            st.success("Dias de descanso salvos na sessão.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Conexão Strava
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Conexão Strava</span>', unsafe_allow_html=True)
        if connected:
            st.markdown('<span class="pill pill-green">● Strava conectado</span>',
                        unsafe_allow_html=True)
            st.markdown("<div style='height:0.7rem'></div>", unsafe_allow_html=True)
            if st.button("Desconectar Strava", key="disconnect"):
                save_strava_tokens(None)
                st.rerun()
        else:
            if cid:
                auth_url = build_auth_url(cid)
                st.markdown(
                    f'<a href="{auth_url}" target="_self" style="display:inline-block;'
                    f'background:#FC4C02;color:white;padding:0.55rem 1.2rem;border-radius:10px;'
                    f'font-weight:600;font-size:0.88rem;text-decoration:none;'
                    f'box-shadow:0 2px 10px rgba(252,76,2,0.25)">'
                    f'Autorizar no Strava →</a>',
                    unsafe_allow_html=True)
                st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
                st.caption("Após autorizar, você será redirecionado automaticamente.")
                # Fallback manual caso o redirect automático não funcione
                with st.expander("Não redirecionou? Conectar manualmente"):
                    st.markdown(
                        '<p style="font-size:0.85rem;color:#6E6E73">'
                        '1. Clique em "Autorizar no Strava" acima<br>'
                        '2. Autorize o acesso<br>'
                        '3. Copie a URL completa da barra de endereços<br>'
                        '4. Cole abaixo e clique "Conectar"</p>',
                        unsafe_allow_html=True)
                    rurl = st.text_input("URL de redirecionamento",
                                         placeholder="https://seu-app.streamlit.app/?code=...")
                    if st.button("Conectar", key="connect_strava_manual"):
                        if rurl:
                            with st.spinner("Autenticando..."):
                                try:
                                    qs   = parse_qs(urlparse(rurl).query)
                                    code = qs.get("code", [rurl])[0]
                                    data = exchange_code(cid, cs, code)
                                    save_strava_tokens({
                                        "access_token": data["access_token"],
                                        "refresh_token": data["refresh_token"],
                                        "expires_at": data["expires_at"]
                                    })
                                    st.success(f"Conectado! Bem-vindo, "
                                               f"{data.get('athlete',{}).get('firstname','Atleta')}!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
            else:
                st.info("Preencha o Client ID do Strava acima para conectar.")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── CTA: gerar treino direto da aba Configurações ──
        if connected and all([cid, cs, akey]) and ath.get("nome"):
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            st.markdown("""<div class="card-sm" style="text-align:center;padding:1.6rem;
                background:linear-gradient(135deg,rgba(252,76,2,0.06),rgba(252,76,2,0.02));
                border:1.5px solid rgba(252,76,2,0.15)">
                <span style="font-size:1.4rem">✅</span>
                <p style="font-weight:700;color:#1D1D1F;margin:0.5rem 0 0.25rem;font-size:1rem">
                Tudo configurado!</p>
                <p style="color:#6E6E73;font-size:0.85rem;margin:0">
                Você pode gerar seu plano de treino agora.</p>
            </div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            if st.button("🏃 Gerar treino semanal", key="gen_from_config", use_container_width=True):
                prog_box = st.empty()
                prog_bar = st.progress(0)
                try:
                    prog_box.markdown(
                        '<div style="padding:0.5rem 0;color:#6E6E73;font-size:0.88rem">'
                        '🔄 Buscando atividades do Strava...</div>', unsafe_allow_html=True)
                    prog_bar.progress(15)
                    token_cfg = get_valid_token(cid, cs)
                    runs_cfg = fetch_runs(token_cfg)
                    if not runs_cfg:
                        st.warning("Nenhuma atividade encontrada nos últimos 28 dias.")
                    else:
                        prog_box.markdown(
                            '<div style="padding:0.5rem 0;color:#6E6E73;font-size:0.88rem">'
                            '🧠 Gerando plano com o treinador IA...</div>', unsafe_allow_html=True)
                        prog_bar.progress(30)
                        sug, a, c, t = generate(runs_cfg, ath, akey)
                        prog_bar.progress(95)
                        st.session_state.update({"suggestion": sug,
                                                 "_atl": a, "_ctl": c, "_tsb": t})
                        prog_bar.progress(100)
                        st.success("Plano gerado! Veja os resultados na aba 🏃 Treino.")
                except Exception as e:
                    st.error(f"Erro ao gerar plano: {e}")
                finally:
                    prog_box.empty()
                    prog_bar.empty()

    # ══════════════════════════════════════════
    # TAB: TREINO
    # ══════════════════════════════════════════
    with tab_home:

        # ── Onboarding (não configurado) ──────
        if not all([cid, cs, akey]):
            st.markdown("""<div class="card" style="text-align:center;padding:3rem 2rem">
                <div style="font-size:3rem;margin-bottom:1rem">🏃</div>
                <p class="section-title" style="font-size:1.4rem">Bem-vindo ao Running Coach</p>
                <p class="body-text" style="color:#6E6E73;max-width:420px;margin:0 auto 1.5rem">
                Para começar, configure suas credenciais na aba
                <strong>Configurações</strong> — são necessários apenas 2 minutos.
                </p>
            </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            for col, n, icon, txt in [
                (c1, "1", "🔑", "Configure suas credenciais do Strava e da API Anthropic"),
                (c2, "2", "🔗", "Conecte sua conta Strava com um clique"),
                (c3, "3", "✨", "Gere sua sugestão de treino personalizada"),
            ]:
                with col:
                    st.markdown(f"""<div class="card-sm" style="text-align:center;padding:1.6rem 1rem">
                        <div style="font-size:1.8rem;margin-bottom:0.6rem">{icon}</div>
                        <div style="font-size:0.72rem;font-weight:700;color:#FC4C02;
                             text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem">
                             Passo {n}</div>
                        <p style="font-size:0.82rem;color:#6E6E73;margin:0;line-height:1.5">{txt}</p>
                    </div>""", unsafe_allow_html=True)
            return

        # ── Não conectado ──────────────────────
        if not connected:
            st.markdown("""<div class="card" style="text-align:center;padding:2.5rem 2rem">
                <div style="font-size:2.5rem;margin-bottom:0.8rem">🔗</div>
                <p class="section-title">Conecte seu Strava</p>
                <p class="body-text" style="color:#6E6E73;margin-bottom:1.2rem">
                Autorize o acesso à sua conta para buscar suas atividades.</p>
            </div>""", unsafe_allow_html=True)
            st.caption("→ Vá até a aba **Configurações** para conectar.")
            return

        # ── Dashboard ─────────────────────────
        try:
            token = get_valid_token(cid, cs)
        except Exception as e:
            st.error(f"Erro de autenticação: {e}")
            return

        with st.spinner("Carregando atividades do Strava..."):
            try:
                runs = fetch_runs(token)
            except Exception as e:
                st.error(f"Erro ao buscar atividades: {e}")
                return

        run_only  = [r for r in runs if not r.get("_is_walk")]
        walk_only = [r for r in runs if r.get("_is_walk")]

        if not runs:
            st.markdown("""<div class="card" style="text-align:center;padding:2rem">
                <p style="font-size:2rem">😴</p>
                <p class="body-text">Nenhuma atividade encontrada nos últimos 28 dias.</p>
            </div>""", unsafe_allow_html=True)
            return

        # Calcular métricas — volume/pace apenas corridas; carga inclui caminhadas
        ref = run_only if run_only else runs
        total_km = sum(r["distance"] for r in run_only) / 1000
        avg_pace = fmt_pace(sum(r.get("average_speed",0) for r in ref) / len(ref))
        lbd      = loads_by_day(runs, ath)          # inclui caminhadas na carga
        atl, ctl, tsb = atl_ctl_tsb(lbd)
        tsb_txt, tsb_cls = tsb_label(tsb)
        trend    = pace_trend(run_only or runs)
        doff     = days_off(runs)
        doff_txt = (f"Ativo {'' if doff==0 else f'há {doff}d'}" if doff is not None else "—")

        # ── Bento Grid de métricas ─────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(metric_card("Volume 28 dias", f"{total_km:.1f}", "km",
                                    f"{len(run_only)} corridas" + (f" · {len(walk_only)} caminhadas" if walk_only else ""),
                                    "badge-orange"),
                        unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Pace médio", avg_pace, sub=trend or ""),
                        unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("ATL / CTL", f"{atl} / {ctl}",
                                    sub="fadiga / condicionamento"),
                        unsafe_allow_html=True)
        with c4:
            st.markdown(metric_card("Forma (TSB)", f"{tsb:+.1f}",
                                    sub=doff_txt, badge=tsb_txt, badge_cls=tsb_cls),
                        unsafe_allow_html=True)

        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

        # ── Últimas corridas ───────────────────
        lbl_count = f"{len(run_only)} corridas" + (f" + {len(walk_only)} caminhadas" if walk_only else "")
        with st.expander(f"  📋  Atividades recentes  ({lbl_count})", expanded=False):
            rows_html = ""
            headers = ["Data", "Tipo", "Nome", "Distância", "Duração", "Pace", "FC", "Carga"]
            head_cells = "".join(
                f'<th style="padding:9px 12px;background:#1D1D1F !important;'
                f'color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF !important;'
                f'font-size:0.74rem;font-weight:600;text-align:left;'
                f'white-space:nowrap;letter-spacing:0.04em">{h}</th>'
                for h in headers
            )
            for i, r in enumerate(runs):
                is_w = r.get("_is_walk", False)
                bg   = "#FFFFFF" if i % 2 == 0 else "#F5F5F7"
                tipo_color = "#1A8A3A" if is_w else "#FC4C02"
                tipo_txt   = "🚶 Caminhada" if is_w else "🏃 Corrida"
                vals = [
                    r["start_date"][:10],
                    f'<span style="color:{tipo_color};font-weight:600;font-size:0.82rem">{tipo_txt}</span>',
                    r.get("name",""),
                    fmt_dist(r["distance"]),
                    fmt_dur(r.get("moving_time",0)),
                    fmt_pace(r.get("average_speed")),
                    f'{round(r["average_heartrate"])} bpm' if r.get("average_heartrate") else "—",
                    f'{run_load(r,ath):.0f}' + (" ♻️" if is_w else ""),
                ]
                cells = "".join(
                    f'<td style="padding:8px 12px;color:#1D1D1F;font-size:0.84rem;'
                    f'border-bottom:1px solid #E5E5EA;white-space:nowrap">{v}</td>'
                    for v in vals
                )
                rows_html += f'<tr style="background:{bg}">{cells}</tr>'

            st.markdown(
                f'<div style="overflow-x:auto;border-radius:12px;'
                f'border:1px solid #E5E5EA;box-shadow:0 1px 8px rgba(0,0,0,0.04);'
                f'font-family:Inter,-apple-system,sans-serif">'
                f'<table style="width:100%;border-collapse:collapse">'
                f'<thead><tr>{head_cells}</tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table></div>',
                unsafe_allow_html=True
            )

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

        # ── Botão principal ────────────────────
        # Verificar dia de treino/descanso
        desc_idx = ath.get("dias_descanso", [0,2])
        dias_pt  = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]
        hoje_idx = datetime.now().weekday()
        hoje_nome = dias_pt[hoje_idx]
        eh_desc  = hoje_idx in desc_idx

        if eh_desc:
            st.markdown(f"""<div class="card-sm" style="text-align:center;padding:1.2rem;
                background:#F5F5F7;border:1.5px solid rgba(0,0,0,0.07)">
                <span style="font-size:0.9rem;color:#6E6E73;font-weight:500">
                🌙  Hoje é <strong>{hoje_nome}</strong> — dia de descanso programado</span>
            </div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        btn_label = "🧘 Ver sugestão de recuperação" if eh_desc else "🏃 Gerar sugestão de treino"

        col_btn, col_sp = st.columns([1, 2])
        with col_btn:
            gerar = st.button(btn_label, use_container_width=True)

        if gerar:
            if not ath.get("nome"):
                st.warning("Preencha seu perfil em Configurações antes de gerar o treino.")
            elif not akey:
                st.warning("Configure sua Anthropic API Key em Configurações.")
            else:
                progress_box = st.empty()
                progress_bar = st.progress(0)
                try:
                    progress_box.markdown(
                        '<div style="padding:0.6rem 0;color:#6E6E73;font-size:0.88rem;font-weight:500">'
                        '📊 Calculando métricas de carga (TRIMP, ATL, CTL, TSB)...</div>',
                        unsafe_allow_html=True)
                    progress_bar.progress(15)
                    import time as _t; _t.sleep(0.3)

                    progress_box.markdown(
                        '<div style="padding:0.6rem 0;color:#6E6E73;font-size:0.88rem;font-weight:500">'
                        '🧠 Enviando dados para o treinador IA...</div>',
                        unsafe_allow_html=True)
                    progress_bar.progress(30)

                    sug, a, c, t = generate(runs, ath, akey)

                    progress_box.markdown(
                        '<div style="padding:0.6rem 0;color:#6E6E73;font-size:0.88rem;font-weight:500">'
                        '✅ Plano de treino recebido! Montando visualização...</div>',
                        unsafe_allow_html=True)
                    progress_bar.progress(90)
                    _t.sleep(0.2)

                    st.session_state.update({"suggestion": sug,
                                             "_atl": a, "_ctl": c, "_tsb": t})
                    progress_bar.progress(100)
                    _t.sleep(0.3)
                except Exception as e:
                    st.error(f"Erro ao gerar sugestão: {e}")
                finally:
                    progress_box.empty()
                    progress_bar.empty()

        # ── Resultados ─────────────────────────
        if st.session_state.suggestion:
            st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
            render_results(st.session_state.suggestion)

            # ── Download PDF ───────────────────
            st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
            col_pdf, _ = st.columns([1, 2])
            with col_pdf:
                with st.spinner("Preparando PDF..."):
                    try:
                        pdf = make_pdf(st.session_state.suggestion, ath, runs,
                                       st.session_state._atl,
                                       st.session_state._ctl,
                                       st.session_state._tsb)
                        st.download_button(
                            "↓  Baixar PDF",
                            data=pdf,
                            file_name=f"treino_{datetime.now().strftime('%Y-%m-%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF: {e}")


if __name__ == "__main__":
    import pandas  # validar dependência
    main()
