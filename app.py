#!/usr/bin/env python3
"""
Strava Running Coach — Interface Web para Streamlit Community Cloud
Design system: Apple-inspired · Bento Grid · Inter font
Cloud-adapted: session_state para tudo, st.secrets opcional como pré-preenchimento, OAuth via query params
"""

import html as html_mod
import json, logging, re, time, uuid, warnings
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests
import streamlit as st

try:
    from supabase import create_client, Client as SupabaseClient
    _HAS_SUPABASE = True
except ImportError:
    _HAS_SUPABASE = False
    SupabaseClient = None

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

/* ── Tabs em grid 2×2 ─────────────────────── */

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

/* ── Buttons (primary = orange filled) ──────── */
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-primary"]:link,
button[data-testid="baseButton-primary"]:visited,
button[data-testid="baseButton-primary"]:active,
button[data-testid="baseButton-primary"]:focus,
button[data-testid="baseButton-primary"]:focus-visible,
button[data-testid="baseButton-primary"]:focus-within,
button[data-testid="baseButton-primary"][disabled],
.stButton > button:not([data-testid="baseButton-secondary"]) {
    background: #FC4C02 !important;
    background-color: #FC4C02 !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    border: none !important;
    border-color: transparent !important;
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 0.6rem 1.5rem !important;
    transition: none !important;
    box-shadow: 0 2px 10px rgba(252,76,2,0.22) !important;
    letter-spacing: -0.01em !important;
    outline: none !important;
    opacity: 1 !important;
}
button[data-testid="baseButton-primary"] *,
.stButton > button:not([data-testid="baseButton-secondary"]) * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    opacity: 1 !important;
}
button[data-testid="baseButton-primary"]:hover,
.stButton > button:not([data-testid="baseButton-secondary"]):hover {
    background: #E03400 !important;
    background-color: #E03400 !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    box-shadow: 0 4px 18px rgba(252,76,2,0.35) !important;
    transform: translateY(-1px) !important;
}
button[data-testid="baseButton-primary"]:hover *,
.stButton > button:not([data-testid="baseButton-secondary"]):hover * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Buttons (secondary = outlined, for inactive tabs) ── */
button[data-testid="baseButton-secondary"],
button[data-testid="baseButton-secondary"]:link,
button[data-testid="baseButton-secondary"]:visited,
button[data-testid="baseButton-secondary"]:active,
button[data-testid="baseButton-secondary"]:focus,
button[data-testid="baseButton-secondary"]:focus-visible,
button[data-testid="baseButton-secondary"]:focus-within,
button[data-testid="baseButton-secondary"][disabled] {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
    border: 1.5px solid rgba(0,0,0,0.12) !important;
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.65rem 1rem !important;
    box-shadow: none !important;
    transition: none !important;
    letter-spacing: -0.01em !important;
    outline: none !important;
    opacity: 1 !important;
}
button[data-testid="baseButton-secondary"] *,
button[data-testid="baseButton-secondary"]:active *,
button[data-testid="baseButton-secondary"]:focus *,
button[data-testid="baseButton-secondary"]:visited * {
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
    opacity: 1 !important;
}
button[data-testid="baseButton-secondary"]:hover {
    background: #F5F5F7 !important;
    background-color: #F5F5F7 !important;
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
    transform: none !important;
    box-shadow: none !important;
}
button[data-testid="baseButton-secondary"]:hover * {
    color: #1D1D1F !important;
    -webkit-text-fill-color: #1D1D1F !important;
}

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

/* ── Tab button grid spacing ──────────────── */
.tab-grid-row { margin-bottom: 0.35rem; }

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

/* ── Day cards (weekly plan) ────────────────── */
.day-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    border: 1px solid rgba(0,0,0,0.04);
    margin-bottom: 0.5rem;
    border-left: 4px solid #FC4C02;
}
.day-card-rest {
    background: #F5F5F7;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    border: 1px solid rgba(0,0,0,0.04);
    margin-bottom: 0.5rem;
    border-left: 4px solid #E5E5EA;
    opacity: 0.75;
}
.day-card-strength {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    border: 1px solid rgba(0,0,0,0.04);
    margin-bottom: 0.5rem;
    border-left: 4px solid #007AFF;
}
"""

# ══════════════════════════════════════════════
# SUPABASE CLIENT
# ══════════════════════════════════════════════
#
# Tabela necessária no Supabase (executar no SQL Editor):
#
# create table public.user_profiles (
#   id uuid references auth.users on delete cascade primary key,
#   email text,
#   nome text default '',
#   athlete_profile jsonb default '{}',
#   strava_client_id text,
#   strava_client_secret text,
#   strava_tokens jsonb,
#   suggestion text,
#   atl real,
#   ctl real,
#   tsb real,
#   created_at timestamptz default now(),
#   updated_at timestamptz default now()
# );
#
# alter table public.user_profiles enable row level security;
# create policy "Users can view own profile"
#   on public.user_profiles for select using (auth.uid() = id);
# create policy "Users can update own profile"
#   on public.user_profiles for update using (auth.uid() = id);
# create policy "Users can insert own profile"
#   on public.user_profiles for insert with check (auth.uid() = id);
#
# Para auto-confirmação de email (desenvolvimento), vá em:
# Authentication → Settings → desabilitar "Enable email confirmations"

@st.cache_resource
def _get_supabase_client():
    """Cria client Supabase singleton a partir de st.secrets."""
    if not _HAS_SUPABASE:
        return None
    url = _get_secret("supabase_url", "")
    key = _get_secret("supabase_anon_key", "")
    if not url or not key:
        return None
    return create_client(url, key)

def _supabase_available():
    """Retorna True se Supabase está instalado e configurado."""
    if not _HAS_SUPABASE:
        return False
    return _get_supabase_client() is not None


# ── Auth helpers ─────────────────────────────
# O Supabase Auth exige email, mas o usuário só informa nome + Strava Client ID + senha.
# Internamente criamos um email fictício: {strava_client_id}@coach.local

def _make_internal_email(strava_id: str) -> str:
    """Gera email interno a partir do Strava Client ID (o usuário nunca vê)."""
    return f"{strava_id.strip()}@coach.local"

def supabase_register(strava_id: str, password: str, nome: str):
    """Registra novo usuário usando Strava Client ID como identificador."""
    sb = _get_supabase_client()
    if not sb:
        return None, "Supabase não configurado."
    email = _make_internal_email(strava_id)
    try:
        res = sb.auth.sign_up({"email": email, "password": password})
        if res.user:
            # Criar registro no user_profiles
            sb.table("user_profiles").insert({
                "id": res.user.id,
                "email": email,
                "nome": nome,
                "strava_client_id": strava_id.strip(),
                "athlete_profile": json.dumps({
                    "nome": nome,
                    "nivel": "intermediário",
                    "objetivo": "",
                    "treinos_semana": 3,
                    "fc_max": 185,
                    "fc_repouso": 50,
                    "pace_limiar": "06:00",
                    "dias_descanso": [],
                    "dias_fortalecimento": [],
                }),
            }).execute()
            return res.session, None
        return None, "Erro ao criar conta. Tente novamente."
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "already been registered" in msg.lower():
            return None, "Este Strava ID já está cadastrado. Faça login."
        logging.exception("Erro no registro Supabase")
        return None, "Erro ao criar conta. Verifique os dados e tente novamente."

def supabase_login(strava_id: str, password: str):
    """Faz login usando Strava Client ID + senha."""
    sb = _get_supabase_client()
    if not sb:
        return None, "Supabase não configurado."
    email = _make_internal_email(strava_id)
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        if res.session:
            return res.session, None
        return None, "Credenciais inválidas."
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower():
            return None, "Strava ID ou senha incorretos."
        logging.exception("Erro no login Supabase")
        return None, "Erro ao fazer login. Tente novamente."

def supabase_logout():
    """Faz logout e limpa session_state."""
    sb = _get_supabase_client()
    if sb:
        try:
            sb.auth.sign_out()
        except Exception:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ── Supabase CRUD ────────────────────────────

def supabase_load_user_data(user_id: str) -> dict:
    """Carrega todos os dados do usuário do Supabase."""
    sb = _get_supabase_client()
    if not sb:
        return {}
    try:
        res = sb.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return res.data or {}
    except Exception:
        logging.exception("Erro ao carregar dados do Supabase")
        return {}

def supabase_save_field(user_id: str, **fields):
    """Salva campos específicos no Supabase (merge parcial)."""
    sb = _get_supabase_client()
    if not sb or not user_id:
        return
    try:
        fields["updated_at"] = datetime.now().isoformat()
        sb.table("user_profiles").update(fields).eq("id", user_id).execute()
    except Exception:
        logging.exception("Erro ao salvar no Supabase")

def supabase_save_training(user_id: str, suggestion: str, atl: float, ctl: float, tsb: float):
    """Salva treino gerado."""
    supabase_save_field(user_id, suggestion=suggestion, atl=atl, ctl=ctl, tsb=tsb)

def supabase_save_athlete_profile(user_id: str, profile: dict):
    """Salva perfil do atleta."""
    supabase_save_field(user_id,
                        athlete_profile=json.dumps(profile, ensure_ascii=False),
                        nome=profile.get("nome", ""))

def supabase_save_strava_credentials(user_id: str, client_id: str, client_secret: str):
    """Salva credenciais Strava."""
    supabase_save_field(user_id, strava_client_id=client_id, strava_client_secret=client_secret)

def supabase_save_strava_tokens(user_id: str, tokens):
    """Salva tokens OAuth do Strava."""
    supabase_save_field(user_id,
                        strava_tokens=json.dumps(tokens) if tokens else None)


# ══════════════════════════════════════════════
# PERSISTENT IN-MEMORY STORE (fallback se Supabase não configurado)
# ══════════════════════════════════════════════

@st.cache_resource
def _get_all_stores():
    """Dict global de stores por sessão."""
    return {}

def _get_persistent_store():
    """Store isolado por sessão (fallback in-memory se sem Supabase)."""
    if "_session_id" not in st.session_state:
        st.session_state._session_id = uuid.uuid4().hex
    sid = st.session_state._session_id
    stores = _get_all_stores()
    if sid not in stores:
        stores[sid] = {
            "strava_tokens": None, "suggestion": None,
            "_atl": None, "_ctl": None, "_tsb": None,
            "athlete_objetivo": None, "athlete_dias_descanso": None,
            "athlete_dias_fortalecimento": None, "athlete_treinos_semana": None,
            "client_id": None, "client_secret": None,
        }
    return stores[sid]

# ══════════════════════════════════════════════
# SESSION STATE HELPERS (Cloud-adapted)
# ══════════════════════════════════════════════

def init_session_state():
    """Inicializa session_state com valores padrão.
       secrets.toml é 100% opcional — tudo pode ser preenchido pelo app."""
    defaults = {
        "strava_tokens": None,
        "athlete": {
            "nome": "",
            "nivel": "intermediário",
            "objetivo": "",
            "treinos_semana": 3,
            "fc_max": 185,
            "fc_repouso": 50,
            "pace_limiar": "06:00",
            "dias_descanso": [],
            "dias_fortalecimento": [],
        },
        "suggestion": None,
        "_atl": None,
        "_ctl": None,
        "_tsb": None,
        "active_tab": 0,
        # Credenciais via st.secrets (configuradas no painel do Streamlit Cloud)
        "client_id": _get_secret("client_id", ""),
        "client_secret": _get_secret("client_secret", ""),
        # anthropic_key is accessed ONLY via st.secrets — never stored in session_state
        "redirect_uri": _get_secret("redirect_uri",
            "https://stravarunningcoach.streamlit.app"),
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
    # Ensure dias_fortalecimento exists in athlete profile (migration)
    if "dias_fortalecimento" not in st.session_state.athlete:
        st.session_state.athlete["dias_fortalecimento"] = []

    # Sync training cache from persistent store (survives screen lock / tab switch)
    store = _get_persistent_store()
    for pkey in ("suggestion", "_atl", "_ctl", "_tsb"):
        if store.get(pkey) is not None and st.session_state.get(pkey) is None:
            st.session_state[pkey] = store[pkey]
    # Sync athlete settings from persistent store
    if store.get("athlete_objetivo") is not None and not st.session_state.athlete.get("objetivo"):
        st.session_state.athlete["objetivo"] = store["athlete_objetivo"]
    if store.get("athlete_dias_descanso") is not None and not st.session_state.athlete.get("dias_descanso"):
        st.session_state.athlete["dias_descanso"] = store["athlete_dias_descanso"]
    if store.get("athlete_dias_fortalecimento") is not None and not st.session_state.athlete.get("dias_fortalecimento"):
        st.session_state.athlete["dias_fortalecimento"] = store["athlete_dias_fortalecimento"]
    if store.get("athlete_treinos_semana") is not None:
        st.session_state.athlete["treinos_semana"] = store["athlete_treinos_semana"]
    # Sync Strava credentials from persistent store
    if store.get("client_id") and not st.session_state.get("client_id"):
        st.session_state.client_id = store["client_id"]
    if store.get("client_secret") and not st.session_state.get("client_secret"):
        st.session_state.client_secret = store["client_secret"]

def get_athlete_profile():
    """Retorna perfil do atleta de session_state."""
    return st.session_state.athlete or {}

def get_credentials():
    """Retorna credenciais. Anthropic key vem SOMENTE de st.secrets (nunca session_state)."""
    return (st.session_state.client_id,
            st.session_state.client_secret,
            _get_secret("anthropic_key", ""))

def save_athlete_profile(athlete_dict):
    """Salva perfil do atleta em session_state."""
    st.session_state.athlete = athlete_dict

def get_strava_tokens():
    """Retorna tokens do Strava — busca em persistent store primeiro."""
    store = _get_persistent_store()
    if store.get("strava_tokens"):
        # Sincroniza com session_state
        st.session_state.strava_tokens = store["strava_tokens"]
        return store["strava_tokens"]
    return st.session_state.strava_tokens

def save_strava_tokens(tokens):
    """Salva tokens no persistent store, session_state, e Supabase."""
    store = _get_persistent_store()
    store["strava_tokens"] = tokens
    st.session_state.strava_tokens = tokens
    # Persist to Supabase
    _uid = st.session_state.get("sb_user_id")
    if _uid:
        supabase_save_strava_tokens(_uid, tokens)

# ══════════════════════════════════════════════
# STRAVA AUTH (Cloud-adapted)
# ══════════════════════════════════════════════

class StravaLimitError(Exception):
    """Erro quando o app Strava excede o limite de atletas conectados."""
    pass

def _render_strava_limit_help():
    """Mostra instruções para o usuário criar seu próprio app Strava."""
    st.markdown(f"""<div class="card" style="border-left:4px solid #FF9500;margin-top:1rem">
        <p class="section-title" style="color:#FF9500;font-size:1rem">
        ⚠️ Limite de atletas excedido</p>
        <p class="body-text" style="margin-bottom:0.8rem">
        O app Strava compartilhado atingiu o número máximo de atletas permitidos.
        Para continuar, crie seu próprio app Strava (leva 2 minutos):</p>
        <p class="body-text" style="margin-bottom:0.3rem">
        <strong>1.</strong> Acesse
        <a href="https://www.strava.com/settings/api" target="_blank"
           style="color:#FC4C02;font-weight:600">strava.com/settings/api</a></p>
        <p class="body-text" style="margin-bottom:0.3rem">
        <strong>2.</strong> Preencha: nome do app (qualquer um), categoria "Training",
        website e callback = <code style="background:#F5F5F7;padding:0.15rem 0.4rem;
        border-radius:4px;font-size:0.82rem">https://stravarunningcoach.streamlit.app</code></p>
        <p class="body-text" style="margin-bottom:0.3rem">
        <strong>3.</strong> Copie o <strong>Client ID</strong> e o <strong>Client Secret</strong></p>
        <p class="body-text">
        <strong>4.</strong> Cole na aba <strong>🔧 Config App</strong> deste aplicativo e salve</p>
    </div>""", unsafe_allow_html=True)

def _req(method, url, **kw):
    return getattr(requests, method)(url, timeout=15, **kw)

def _check_strava_limit(response):
    """Verifica se a resposta do Strava indica limite de atletas excedido."""
    if response.status_code == 403:
        body = ""
        try:
            body = response.text.lower()
        except Exception:
            pass
        if "athlete" in body or "limit" in body or response.status_code == 403:
            raise StravaLimitError(
                "O app Strava atingiu o limite de atletas conectados. "
                "Crie seu próprio app em strava.com/settings/api e insira "
                "seu Client ID e Secret na aba ⚙️ Config App."
            )

def exchange_code(cid, cs, code):
    r = _req("post", "https://www.strava.com/oauth/token",
             data={"client_id": cid, "client_secret": cs,
                   "code": code, "grant_type": "authorization_code"})
    _check_strava_limit(r)
    r.raise_for_status()
    return r.json()

def refresh_strava_token(cid, cs, rt):
    r = _req("post", "https://www.strava.com/oauth/token",
             data={"client_id": cid, "client_secret": cs,
                   "refresh_token": rt, "grant_type": "refresh_token"})
    _check_strava_limit(r)
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

def _validate_redirect_uri(uri):
    """Valida que a redirect_uri é HTTPS e pertence a um domínio confiável."""
    if not uri:
        return False
    parsed = urlparse(uri)
    # Permitir localhost para dev e *.streamlit.app para produção
    allowed = (
        parsed.hostname == "localhost"
        or (parsed.hostname and parsed.hostname.endswith(".streamlit.app"))
    )
    if not allowed:
        return False
    # Em produção, exigir HTTPS
    if parsed.hostname != "localhost" and parsed.scheme != "https":
        return False
    return True

def build_auth_url(cid):
    """Constrói URL de autorização do Strava com state anti-CSRF."""
    redirect = _detect_app_url()
    if not _validate_redirect_uri(redirect):
        st.error("URL de redirecionamento inválida. Use um domínio *.streamlit.app com HTTPS.")
        return ""
    # Generate a random state token to prevent CSRF attacks
    state = uuid.uuid4().hex
    st.session_state._oauth_state = state
    return (f"https://www.strava.com/oauth/authorize?client_id={cid}"
            f"&response_type=code&redirect_uri={redirect}"
            f"&approval_prompt=force&scope={SCOPE}&state={state}")

def handle_oauth_callback():
    """Detecta e processa callback do OAuth via query params.
       Valida state parameter para prevenir ataques CSRF."""
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        # Validate state parameter (CSRF protection)
        received_state = query_params.get("state", "")
        expected_state = st.session_state.get("_oauth_state", "")
        if expected_state and received_state != expected_state:
            st.error("Erro de segurança: state inválido. Tente autorizar novamente.")
            st.query_params.clear()
            return False
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
            # Clear the state token after successful auth
            st.session_state.pop("_oauth_state", None)
            firstname = html_mod.escape(data.get('athlete', {}).get('firstname', 'Atleta'))
            st.success(f"Conectado! Bem-vindo, {firstname}!")
            st.rerun()
        except StravaLimitError as e:
            st.query_params.clear()
            st.error(str(e))
            _render_strava_limit_help()
            return False
        except Exception as e:
            st.error("Erro na autenticação. Verifique suas credenciais e tente novamente.")
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
    _check_strava_limit(r)
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
    desc_idx = ath.get("dias_descanso",[])
    eh_desc  = hoje.weekday() in desc_idx
    nms_desc = [dias_pt[i] for i in desc_idx]
    dias_tr  = [d for i,d in enumerate(dias_pt) if i not in desc_idx]

    # Dias de fortalecimento de pernas
    fort_idx = ath.get("dias_fortalecimento", [])
    nms_fort = [dias_pt[i] for i in fort_idx] if fort_idx else []
    fort_info = ""
    if nms_fort:
        fort_info = f"\n- Dias de fortalecimento de pernas: {', '.join(nms_fort)} (marcar como 'Fortalecimento de pernas' na semana completa)"
    else:
        fort_info = "\n- Dias de fortalecimento de pernas: nenhum configurado"

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
- Pace limiar: {ath.get('pace_limiar','5:30')}/km | FC max: {ath.get('fc_max',185)} bpm | FC rep: {ath.get('fc_repouso',50)} bpm{race}{fort_info}

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
REGRA OBRIGATÓRIA: O atleta deseja fazer EXATAMENTE {ath.get('treinos_semana',3)} treinos de corrida por semana. Distribua esses {ath.get('treinos_semana',3)} treinos nos dias disponíveis ({', '.join(dias_tr)}) com descanso em {', '.join(nms_desc) if nms_desc else 'nenhum dia fixo definido'}.{' Dias de fortalecimento de pernas: ' + ', '.join(nms_fort) + '.' if nms_fort else ''} Os demais dias disponíveis que não tiverem treino de corrida devem ser marcados como "Descanso" ou "Fortalecimento de pernas" conforme configurado. Seja agressivo mas inteligente: alterne intensidade alta / baixa, nunca dois treinos duros seguidos.

IMPORTANTE: Após a descrição textual da semana, inclua OBRIGATORIAMENTE um bloco estruturado parseável com EXATAMENTE este formato (uma linha por dia, começando com a abreviação do dia seguida de dois-pontos). Use | como separador de campos. Para dias de descanso escreva apenas "Descanso". Para dias de fortalecimento escreva apenas "Fortalecimento de pernas":

```
SEG: Descanso
TER: Intervalado | 8km | Pace 4:30-5:00 | 4x1000m a 4:15 com 90s trote + aquecimento e desaquecimento
QUA: Descanso
QUI: Tempo Run | 10km | Pace 5:00-5:20 | 3km aquecimento + 5km ritmo forte + 2km desaquecimento
SEX: Regenerativo | 5km | Pace 6:30-7:00 | Corrida leve zona 1
SAB: Longo | 16km | Pace 5:40-6:00 | Ritmo constante com últimos 3km progressivo
DOM: Fortalecimento de pernas
```

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
            timeout=90,
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
    """Generates a clean, Apple-inspired PDF mirroring the Treinos tab view.
    Shows: header, weekly plan with full day-card details, análise honesta, alerta."""
    import io
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, KeepTogether)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    PAGE_W, PAGE_H = A4
    ML, MR, MT, MB = 20*mm, 20*mm, 18*mm, 16*mm
    CONTENT_W = PAGE_W - ML - MR

    # ── Paleta ────────────────────────────────────────────
    ORANGE  = colors.HexColor("#FC4C02")
    DARK    = colors.HexColor("#1D1D1F")
    MID     = colors.HexColor("#3A3A3C")
    GREY    = colors.HexColor("#86868B")
    LIGHT   = colors.HexColor("#F5F5F7")
    DIVIDER = colors.HexColor("#E5E5EA")
    BLUE    = colors.HexColor("#007AFF")
    WHITE   = colors.white

    hoje = datetime.now()
    nome = ath.get("nome", "Atleta")

    # ── Page decoration — minimal footer only ────────────
    def draw_page(cv, doc):
        cv.saveState()
        # Thin top accent line
        cv.setFillColor(ORANGE)
        cv.rect(0, PAGE_H - 2.5*mm, PAGE_W, 2.5*mm, fill=1, stroke=0)
        # Footer
        cv.setFont("Helvetica", 7)
        cv.setFillColor(GREY)
        cv.drawString(ML, 8*mm,
                      f"Strava Running Coach  ·  {nome}  ·  {hoje.strftime('%d/%m/%Y')}")
        cv.drawRightString(PAGE_W - MR, 8*mm, f"{doc.page}")
        cv.restoreState()

    # ── Styles ────────────────────────────────────────────
    S = {
        "hero":     ParagraphStyle("hero", fontName="Helvetica-Bold", fontSize=24,
                                   textColor=DARK, leading=28, spaceAfter=1*mm),
        "hero_sub": ParagraphStyle("hero_sub", fontName="Helvetica", fontSize=10,
                                   textColor=GREY, spaceAfter=6*mm),
        "sec":      ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=12,
                                   textColor=DARK, spaceBefore=5*mm, spaceAfter=3*mm,
                                   leading=14),
        "day_name": ParagraphStyle("day_name", fontName="Helvetica-Bold", fontSize=10,
                                   textColor=DARK, leading=13),
        "day_type": ParagraphStyle("day_type", fontName="Helvetica-Bold", fontSize=8,
                                   textColor=ORANGE, leading=10),
        "day_type_rest": ParagraphStyle("day_type_rest", fontName="Helvetica", fontSize=8,
                                        textColor=GREY, leading=10),
        "day_type_str": ParagraphStyle("day_type_str", fontName="Helvetica-Bold", fontSize=8,
                                       textColor=BLUE, leading=10),
        "day_meta": ParagraphStyle("day_meta", fontName="Helvetica", fontSize=8.5,
                                   textColor=GREY, leading=12),
        "day_desc": ParagraphStyle("day_desc", fontName="Helvetica", fontSize=8.5,
                                   textColor=MID, leading=13, spaceAfter=1*mm),
        "seg_lbl":  ParagraphStyle("seg_lbl", fontName="Helvetica-Bold", fontSize=7.5,
                                   textColor=GREY, leading=10),
        "seg_item": ParagraphStyle("seg_item", fontName="Helvetica", fontSize=8.5,
                                   textColor=MID, leftIndent=3*mm, leading=12),
        "body":     ParagraphStyle("body", fontName="Helvetica", fontSize=9,
                                   textColor=MID, leading=13.5, spaceAfter=1.5*mm),
        "bullet":   ParagraphStyle("bullet", fontName="Helvetica", fontSize=9,
                                   textColor=MID, leftIndent=4*mm, leading=13.5,
                                   spaceAfter=1.5*mm),
    }

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=MT, bottomMargin=MB)
    story = []

    # ── Hero header ──────────────────────────────────────
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("Plano da Semana", S["hero"]))
    sub_parts = [nome]
    obj = ath.get("objetivo", "")
    if obj:
        sub_parts.append(obj)
    sub_parts.append(hoje.strftime("%d de %B de %Y"))
    story.append(Paragraph("  ·  ".join(sub_parts), S["hero_sub"]))

    # ── Thin divider ─────────────────────────────────────
    story.append(Table(
        [[""]], colWidths=[CONTENT_W], rowHeights=[0.4*mm],
        style=[("BACKGROUND", (0,0), (-1,-1), DIVIDER)]
    ))
    story.append(Spacer(1, 2*mm))

    # ── Extract "Treino de hoje" detail from AI ──────────
    hoje_detail = None
    sections_ai = re.split(r'\n(?=## )', suggestion.strip())
    for sec_ai in sections_ai:
        if "Treino de hoje" in sec_ai:
            lns = sec_ai.strip().splitlines()[1:]
            hoje_detail = "\n".join(lns).strip()
            break

    dias_pt = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    hoje_nome = dias_pt[hoje.weekday()] if hoje.weekday() < 7 else ""

    # ── Day cards ────────────────────────────────────────
    plan = parse_weekly_plan(suggestion)
    HALF_W = CONTENT_W / 2 - 1.5*mm

    def _build_day_card(entry):
        """Build a list of flowables for a single day card."""
        card_items = []
        dia = entry["dia_nome"]
        is_today = (dia == hoje_nome)

        if entry["is_rest"]:
            # Rest day — simple minimal card
            row = Table(
                [[Paragraph(dia, S["day_name"]),
                  Paragraph("DESCANSO", S["day_type_rest"])]],
                colWidths=[HALF_W * 0.55, HALF_W * 0.45],
                style=[
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("LEFTPADDING", (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                    ("TOPPADDING", (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                    ("ALIGN", (1,0), (1,0), "RIGHT"),
                ]
            )
            card_items.append(row)
            desc = entry.get("descricao", "Dia de descanso")
            card_items.append(Spacer(1, 1.5*mm))
            card_items.append(Paragraph(desc, S["day_desc"]))

        elif entry["is_strength"]:
            row = Table(
                [[Paragraph(dia, S["day_name"]),
                  Paragraph("FORTALECIMENTO", S["day_type_str"])]],
                colWidths=[HALF_W * 0.55, HALF_W * 0.45],
                style=[
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("LEFTPADDING", (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                    ("TOPPADDING", (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                    ("ALIGN", (1,0), (1,0), "RIGHT"),
                ]
            )
            card_items.append(row)
            card_items.append(Spacer(1, 1.5*mm))
            card_items.append(Paragraph("Fortalecimento de pernas", S["day_desc"]))

        else:
            # Workout day — full detail
            tipo = entry.get("tipo", "Treino")
            day_type_s = ParagraphStyle("dt", parent=S["day_type"],
                                        textColor=ORANGE)
            row = Table(
                [[Paragraph(dia + (" · hoje" if is_today else ""), S["day_name"]),
                  Paragraph(tipo.upper(), day_type_s)]],
                colWidths=[HALF_W * 0.55, HALF_W * 0.45],
                style=[
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("LEFTPADDING", (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                    ("TOPPADDING", (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                    ("ALIGN", (1,0), (1,0), "RIGHT"),
                ]
            )
            card_items.append(row)

            # Distance + Pace meta line
            meta_parts = []
            if entry.get("distancia"):
                meta_parts.append(entry["distancia"])
            if entry.get("pace"):
                meta_parts.append(entry["pace"])
            if meta_parts:
                card_items.append(Spacer(1, 1.5*mm))
                card_items.append(Paragraph("  ·  ".join(meta_parts), S["day_meta"]))

            # If this is today and we have full AI detail, use it
            if is_today and hoje_detail:
                card_items.append(Spacer(1, 2*mm))
                for ln in hoje_detail.splitlines():
                    ln = _strip_emoji(ln.strip())
                    if not ln:
                        continue
                    ln = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', ln)
                    if ln.startswith("- "):
                        card_items.append(Paragraph(
                            '<font color="#FC4C02">&#8226;</font>  ' + ln[2:],
                            S["bullet"]))
                    else:
                        card_items.append(Paragraph(ln, S["body"]))
            else:
                # Use structured description
                desc = entry.get("descricao", "")
                if desc:
                    card_items.append(Spacer(1, 2*mm))
                    segments = [s.strip() for s in desc.split("+") if s.strip()]
                    if len(segments) > 1:
                        card_items.append(Paragraph("ESTRUTURA", S["seg_lbl"]))
                        card_items.append(Spacer(1, 1*mm))
                        for seg in segments:
                            card_items.append(Paragraph(
                                '<font color="#FC4C02">&#8250;</font>  ' + seg,
                                S["seg_item"]))
                    else:
                        card_items.append(Paragraph(desc, S["day_desc"]))

        return card_items

    # Helper to strip emojis (Helvetica can't render them) — used in cards + sections
    _strip_emoji = lambda t: re.sub(
        r'[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0000FE00-\U0000FE0F'
        r'\U0000200D\U00002600-\U000026FF\U00002700-\U000027BF]+', '', t).strip()

    if plan:
        story.append(Paragraph("Plano da semana", S["sec"]))

        for entry in plan:
            card_items = _build_day_card(entry)

            # Card border color
            if entry["is_rest"]:
                border_color = DIVIDER
                bg = LIGHT
            elif entry["is_strength"]:
                border_color = BLUE
                bg = WHITE
            else:
                border_color = ORANGE
                bg = WHITE

            # Wrap card content in a table that acts as a card container
            inner_tbl = Table(
                [[item] for item in card_items],
                colWidths=[CONTENT_W - 8*mm],
                style=[
                    ("LEFTPADDING",   (0,0), (-1,-1), 0),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 0),
                    ("TOPPADDING",    (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 0.5*mm),
                ]
            )

            card_wrapper = Table(
                [[inner_tbl]],
                colWidths=[CONTENT_W],
                style=[
                    ("BACKGROUND",    (0,0), (-1,-1), bg),
                    ("ROUNDEDCORNERS", [3*mm, 3*mm, 3*mm, 3*mm]),
                    ("LEFTPADDING",   (0,0), (-1,-1), 4*mm),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 4*mm),
                    ("TOPPADDING",    (0,0), (-1,-1), 3*mm),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 3*mm),
                    ("LINEBEFORE",    (0,0), (0,-1), 2.5, border_color),
                    ("BOX",           (0,0), (-1,-1), 0.3, DIVIDER),
                ]
            )

            story.append(KeepTogether([card_wrapper, Spacer(1, 2.5*mm)]))

    # ── AI Analysis sections (Análise honesta + Alerta) ──
    for sec_ai in sections_ai:
        lines = sec_ai.strip().splitlines()
        if not lines:
            continue
        header = lines[0].replace("## ", "").strip()

        # Only include Análise honesta and Alerta do treinador
        include = False
        if "nálise" in header.lower():
            include = True
        elif "lerta" in header.lower():
            include = True
        if not include:
            continue

        body_lines = lines[1:]
        clean_header = _strip_emoji(header)

        # Section header
        story.append(Spacer(1, 2*mm))
        story.append(Table(
            [[""]], colWidths=[CONTENT_W], rowHeights=[0.3*mm],
            style=[("BACKGROUND", (0,0), (-1,-1), DIVIDER)]
        ))
        story.append(Spacer(1, 1*mm))
        story.append(Paragraph(clean_header, S["sec"]))

        for ln in body_lines:
            ln = ln.strip()
            if not ln:
                continue
            ln = _strip_emoji(ln)
            if not ln:
                continue
            ln = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', ln)
            if ln.startswith("- "):
                story.append(Paragraph(
                    '<font color="#FC4C02">&#8226;</font>  ' + ln[2:],
                    S["bullet"]))
            elif not (ln.startswith("(") and ln.endswith(")")):
                story.append(Paragraph(ln, S["body"]))

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

def render_results(suggestion, skip_sections=None):
    """Renderiza cada seção da sugestão num card separado.
    skip_sections: set of section header keywords to skip entirely.
    For 'Semana completa', only show text before the ``` code block."""
    skip_sections = skip_sections or set()
    sections = re.split(r'\n(?=## )', suggestion.strip())
    for sec_text in sections:
        lines = sec_text.strip().splitlines()
        if not lines: continue
        header = lines[0].replace("## ", "").strip()

        # Skip sections that are already rendered elsewhere
        if any(skip in header for skip in skip_sections):
            continue

        body_lines = lines[1:]

        # For "Semana completa" — only keep text before the ``` code block
        if "Semana completa" in header or "semana completa" in header.lower():
            filtered = []
            for ln in body_lines:
                if ln.strip().startswith("```"):
                    break
                filtered.append(ln)
            body_lines = filtered

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

        if any(ln.strip().startswith("- ") for ln in body_lines):
            body_html = f'<ul style="padding-left:1.2rem;margin:0">{body_html}</ul>'

        if not body_html.strip() or body_html.strip() == "<br>":
            continue

        st.markdown(f"""<div class="result-section">
            <h2>{header}</h2>
            {body_html}
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# WEEKLY PLAN PARSER & RENDERER
# ══════════════════════════════════════════════

DAY_ABBREVS = {
    "SEG": "Segunda", "TER": "Terça", "QUA": "Quarta",
    "QUI": "Quinta", "SEX": "Sexta", "SAB": "Sábado",
    "SÁB": "Sábado", "DOM": "Domingo",
}

def parse_weekly_plan(suggestion):
    """Extrai o plano semanal estruturado da resposta da IA.
    Retorna lista de dicts: [{"dia": "SEG", "dia_nome": "Segunda",
    "tipo": "Intervalado", "distancia": "8km", "pace": "4:30-5:00",
    "descricao": "...", "is_rest": False, "is_strength": False}, ...]
    """
    plan = []
    # Look for the structured block after "## 📅 Semana completa"
    # The structured block has lines like "SEG: ..." "TER: ..." etc.
    lines = suggestion.splitlines()
    in_block = False
    for line in lines:
        stripped = line.strip()
        # Skip code fence markers
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        # Match day lines: "SEG: ...", "TER: ...", etc.
        m = re.match(r'^(SEG|TER|QUA|QUI|SEX|S[AÁ]B|DOM)\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            abbrev = m.group(1).upper()
            if abbrev == "SÁB":
                abbrev = "SAB"
            content = m.group(2).strip()
            dia_nome = DAY_ABBREVS.get(abbrev, abbrev)
            entry = {
                "dia": abbrev,
                "dia_nome": dia_nome,
                "tipo": "",
                "distancia": "",
                "pace": "",
                "descricao": "",
                "is_rest": False,
                "is_strength": False,
            }
            content_lower = content.lower()
            if content_lower in ("descanso", "descanso total", "descanso ativo", "descanso completo"):
                entry["tipo"] = "Descanso"
                entry["is_rest"] = True
                entry["descricao"] = content
            elif "fortalecimento" in content_lower:
                entry["tipo"] = "Fortalecimento"
                entry["is_strength"] = True
                entry["descricao"] = content
            else:
                parts = [p.strip() for p in content.split("|")]
                if len(parts) >= 1:
                    entry["tipo"] = parts[0]
                if len(parts) >= 2:
                    entry["distancia"] = parts[1]
                if len(parts) >= 3:
                    entry["pace"] = parts[2]
                if len(parts) >= 4:
                    entry["descricao"] = parts[3]
                elif len(parts) < 4:
                    entry["descricao"] = content
            plan.append(entry)
    return plan


def render_day_card(entry):
    """Renders a single day card as HTML."""
    dia = entry["dia_nome"]
    if entry["is_rest"]:
        return f"""<div class="day-card-rest">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:700;color:#6E6E73;font-size:0.95rem">{dia}</span>
                <span style="font-size:0.78rem;font-weight:600;color:#AEAEB2;text-transform:uppercase;letter-spacing:0.05em">Descanso</span>
            </div>
            <p style="margin:0.4rem 0 0;color:#AEAEB2;font-size:0.85rem">{entry.get('descricao','Dia de descanso')}</p>
        </div>"""
    elif entry["is_strength"]:
        return f"""<div class="day-card-strength">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:700;color:#1D1D1F;font-size:0.95rem">{dia}</span>
                <span style="font-size:0.78rem;font-weight:600;color:#007AFF;text-transform:uppercase;letter-spacing:0.05em">Fortalecimento</span>
            </div>
            <p style="margin:0.4rem 0 0;color:#3A3A3C;font-size:0.85rem">Fortalecimento de pernas</p>
        </div>"""
    else:
        # Build metric chips for distance and pace
        chips_html = ""
        if entry["distancia"]:
            chips_html += (
                f'<span style="display:inline-block;font-size:0.78rem;font-weight:600;'
                f'color:#FC4C02;background:rgba(252,76,2,0.08);padding:0.2rem 0.55rem;'
                f'border-radius:8px;margin-right:0.4rem">{entry["distancia"]}</span>'
            )
        if entry["pace"]:
            chips_html += (
                f'<span style="display:inline-block;font-size:0.78rem;font-weight:600;'
                f'color:#6E6E73;background:#F5F5F7;padding:0.2rem 0.55rem;'
                f'border-radius:8px">{entry["pace"]}</span>'
            )
        # Parse description for segment breakdown (e.g. "3km aquecimento + 5km ritmo forte + 2km desaquecimento")
        desc = entry.get("descricao", "")
        desc_html = ""
        if desc:
            # Try to split on "+" to show structured segments
            segments = [s.strip() for s in desc.split("+") if s.strip()]
            if len(segments) > 1:
                seg_items = ""
                for seg in segments:
                    seg_items += (
                        f'<div style="display:flex;align-items:center;gap:0.4rem;'
                        f'padding:0.25rem 0;border-bottom:1px solid rgba(0,0,0,0.04)">'
                        f'<span style="color:#FC4C02;font-size:0.75rem">●</span>'
                        f'<span style="font-size:0.83rem;color:#3A3A3C">{seg}</span></div>'
                    )
                desc_html = (
                    f'<div style="margin-top:0.5rem;padding:0.5rem 0.6rem;'
                    f'background:#FAFAFA;border-radius:8px;border:1px solid rgba(0,0,0,0.04)">'
                    f'<span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;'
                    f'letter-spacing:0.05em;color:#AEAEB2;margin-bottom:0.25rem;display:block">Estrutura</span>'
                    f'{seg_items}</div>'
                )
            else:
                desc_html = f'<p style="margin:0.4rem 0 0;color:#3A3A3C;font-size:0.85rem;line-height:1.5">{desc}</p>'
        return f"""<div class="day-card">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:700;color:#1D1D1F;font-size:0.95rem">{dia}</span>
                <span style="font-size:0.78rem;font-weight:600;color:#FC4C02;text-transform:uppercase;letter-spacing:0.05em">{entry['tipo']}</span>
            </div>
            <div style="margin-top:0.4rem">{chips_html}</div>
            {desc_html}
        </div>"""


def extract_day_detail_from_suggestion(suggestion, day_abbrev):
    """Extracts detailed AI text for a specific day from the full suggestion.
    Looks for content in the '## 🏃 Treino de hoje' section if it matches,
    or content between day mentions in the '## 📅 Semana completa' section."""
    if not suggestion:
        return None
    # Try to find dedicated detail in the Semana completa prose (before ``` block)
    sections = re.split(r'\n(?=## )', suggestion.strip())
    for sec in sections:
        if "Semana completa" in sec or "semana completa" in sec.lower():
            # Get text before ``` block
            prose_lines = []
            for line in sec.splitlines()[1:]:  # skip header
                if line.strip().startswith("```"):
                    break
                prose_lines.append(line)
            return "\n".join(prose_lines).strip() if prose_lines else None
    return None


def render_weekly_cards(plan, suggestion=None):
    """Renders the full weekly plan as day cards in a 2-column grid.
    Cards are clickable expanders showing detailed info."""
    if not plan:
        return

    # Extract the "Treino de hoje" detail section from AI response
    hoje_detail = None
    if suggestion:
        sections = re.split(r'\n(?=## )', suggestion.strip())
        for sec in sections:
            if "Treino de hoje" in sec:
                lines = sec.strip().splitlines()[1:]  # skip header
                hoje_detail = "\n".join(lines).strip()
                break

    dias_pt = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    hoje_idx = datetime.now().weekday()
    hoje_nome = dias_pt[hoje_idx] if hoje_idx < len(dias_pt) else ""

    col1, col2 = st.columns(2)
    for i, entry in enumerate(plan):
        with col1 if i % 2 == 0 else col2:
            # Render the card visually
            st.markdown(render_day_card(entry), unsafe_allow_html=True)
            # Add clickable detail expander for non-rest days
            if not entry["is_rest"]:
                is_today = (entry["dia_nome"] == hoje_nome)
                with st.expander("Ver detalhes" + (" · hoje" if is_today else ""), expanded=False):
                    if is_today and hoje_detail:
                        # Show the full "Treino de hoje" AI detail
                        detail_html = ""
                        for ln in hoje_detail.splitlines():
                            ln = ln.strip()
                            if not ln: continue
                            ln = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ln)
                            if ln.startswith("- "):
                                detail_html += f'<li style="margin-bottom:0.35rem;color:#3A3A3C;font-size:0.85rem">{ln[2:]}</li>'
                            else:
                                detail_html += f'<p style="margin:0 0 0.35rem;color:#3A3A3C;font-size:0.85rem;line-height:1.55">{ln}</p>'
                        if any(ln.strip().startswith("- ") for ln in hoje_detail.splitlines()):
                            detail_html = f'<ul style="padding-left:1rem;margin:0">{detail_html}</ul>'
                        st.markdown(detail_html, unsafe_allow_html=True)
                    else:
                        # Build detail from entry data
                        detail_parts = []
                        if entry.get("tipo"):
                            detail_parts.append(f'<p style="margin:0 0 0.3rem"><strong style="color:#FC4C02">Tipo:</strong> <span style="color:#3A3A3C;font-size:0.88rem">{entry["tipo"]}</span></p>')
                        if entry.get("distancia"):
                            detail_parts.append(f'<p style="margin:0 0 0.3rem"><strong style="color:#FC4C02">Distância:</strong> <span style="color:#3A3A3C;font-size:0.88rem">{entry["distancia"]}</span></p>')
                        if entry.get("pace"):
                            detail_parts.append(f'<p style="margin:0 0 0.3rem"><strong style="color:#FC4C02">Pace alvo:</strong> <span style="color:#3A3A3C;font-size:0.88rem">{entry["pace"]}</span></p>')
                        if entry.get("descricao"):
                            desc = entry["descricao"]
                            segments = [s.strip() for s in desc.split("+") if s.strip()]
                            if len(segments) > 1:
                                detail_parts.append('<p style="margin:0.4rem 0 0.2rem"><strong style="color:#FC4C02">Estrutura detalhada:</strong></p>')
                                for seg in segments:
                                    detail_parts.append(f'<p style="margin:0 0 0.2rem;padding-left:0.8rem;color:#3A3A3C;font-size:0.85rem">▸ {seg}</p>')
                            else:
                                detail_parts.append(f'<p style="margin:0.3rem 0 0"><strong style="color:#FC4C02">Descrição:</strong> <span style="color:#3A3A3C;font-size:0.88rem">{desc}</span></p>')
                        st.markdown("".join(detail_parts), unsafe_allow_html=True)


def compute_weekly_km(runs):
    """Always returns exactly 4 weeks (current week + 3 prior), filling 0 for weeks with no activity.
    Each dict: {"week_label": "13/04 - 19/04", "km": 42.5}
    """
    run_only = [r for r in runs if not r.get("_is_walk")]
    # Build km totals by ISO week key
    week_data = {}
    for r in run_only:
        dt = datetime.fromisoformat(r["start_date"].replace("Z", "+00:00"))
        iso_year, iso_week, _ = dt.isocalendar()
        key = (iso_year, iso_week)
        week_data[key] = week_data.get(key, 0) + r["distance"] / 1000
    # Always generate exactly 4 weeks: current week and 3 prior
    today = datetime.now()
    result = []
    for weeks_ago in range(3, -1, -1):
        ref_day = today - timedelta(weeks=weeks_ago)
        iso_year, iso_week, _ = ref_day.isocalendar()
        key = (iso_year, iso_week)
        monday = datetime.strptime(f"{iso_year}-W{iso_week:02d}-1", "%G-W%V-%u")
        sunday = monday + timedelta(days=6)
        label = f"{monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')}"
        result.append({"week_label": label, "km": round(week_data.get(key, 0), 1)})
    return result


def render_weekly_km_chart(weekly_data):
    """Renders weekly km as a styled HTML bar chart matching the app design system."""
    if not weekly_data:
        st.info("Dados insuficientes para o gráfico semanal.")
        return
    max_km = max((w["km"] for w in weekly_data), default=1) or 1

    bars_html = ""
    for w in weekly_data:
        pct = (w["km"] / max_km) * 100 if max_km > 0 else 0
        km_label = f'{w["km"]:.1f}' if w["km"] > 0 else "0"
        bar_color = "#3A3A3C" if w["km"] > 0 else "#E5E5EA"
        bars_html += f'''
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:0.3rem">
            <span style="font-size:0.72rem;font-weight:600;color:#1D1D1F">{km_label}</span>
            <div style="width:100%;height:120px;display:flex;align-items:flex-end;justify-content:center">
                <div style="width:70%;min-height:4px;height:{max(pct, 3):.0f}%;
                    background:{bar_color};border-radius:6px 6px 2px 2px;
                    transition:height 0.3s ease"></div>
            </div>
            <span style="font-size:0.68rem;color:#6E6E73;text-align:center;line-height:1.2">{w["week_label"]}</span>
        </div>'''

    st.markdown(
        f'<p style="font-size:0.72rem;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.06em;color:#6E6E73;margin-bottom:0.8rem">'
        f'Volume semanal (km)</p>'
        f'<div style="display:flex;gap:0.5rem;align-items:flex-end;padding:0 0.2rem">'
        f'{bars_html}</div>',
        unsafe_allow_html=True)


# ══════════════════════════════════════════════
# APP PRINCIPAL
# ══════════════════════════════════════════════

def _render_auth_screen():
    """Renderiza tela de login/registro com design Apple-inspired.
       Usa nome + Strava Client ID + senha (sem email)."""
    st.markdown("""<div style="max-width:420px;margin:3rem auto;text-align:center">
        <div style="font-size:3rem;margin-bottom:0.5rem">🏃</div>
        <p class="page-title" style="font-size:1.8rem;margin-bottom:0.3rem">Running Coach</p>
        <p class="page-subtitle" style="margin-bottom:2rem">Faça login para acessar seus treinos</p>
    </div>""", unsafe_allow_html=True)

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    mode = st.session_state.auth_mode

    st.markdown('<div class="form-section" style="max-width:420px;margin:0 auto">', unsafe_allow_html=True)

    if mode == "login":
        st.markdown('<span class="form-label">Entrar na sua conta</span>', unsafe_allow_html=True)
        strava_id = st.text_input("Strava Client ID", placeholder="ex: 214364",
                                  key="auth_strava_id")
        password = st.text_input("Senha", type="password", placeholder="••••••••",
                                 key="auth_pass")

        if st.button("Entrar", use_container_width=True, key="btn_login"):
            if not strava_id or not password:
                st.warning("Preencha o Strava Client ID e a senha.")
            else:
                with st.spinner("Autenticando..."):
                    session, err = supabase_login(strava_id.strip(), password)
                if err:
                    st.error(err)
                else:
                    st.session_state.sb_session = session
                    st.session_state.sb_user_id = session.user.id
                    st.session_state.sb_strava_id = strava_id.strip()
                    st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Não tem conta? Criar agora", use_container_width=True,
                     key="switch_register", type="secondary"):
            st.session_state.auth_mode = "register"
            st.rerun()

    else:  # register
        st.markdown('<span class="form-label">Criar nova conta</span>', unsafe_allow_html=True)
        nome = st.text_input("Seu nome", placeholder="ex: João", key="auth_nome")
        strava_id = st.text_input("Strava Client ID", placeholder="ex: 214364",
                                  key="auth_reg_strava_id",
                                  help="Encontre em strava.com/settings/api")
        password = st.text_input("Senha (mín. 6 caracteres)", type="password",
                                 placeholder="••••••••", key="auth_reg_pass")

        st.markdown(
            '<p style="font-size:0.78rem;color:#6E6E73;margin-top:0.5rem">'
            'Não tem um Strava Client ID? '
            '<a href="https://www.strava.com/settings/api" target="_blank" '
            'style="color:#FC4C02;font-weight:600">Crie seu app no Strava</a> '
            '(leva 2 minutos)</p>',
            unsafe_allow_html=True)

        if st.button("Criar conta", use_container_width=True, key="btn_register"):
            if not nome or not strava_id or not password:
                st.warning("Preencha todos os campos.")
            elif len(password) < 6:
                st.warning("A senha deve ter pelo menos 6 caracteres.")
            elif not strava_id.strip().isdigit():
                st.warning("O Strava Client ID deve conter apenas números.")
            else:
                with st.spinner("Criando conta..."):
                    session, err = supabase_register(
                        strava_id.strip(), password, nome.strip())
                if err:
                    st.error(err)
                else:
                    if session:
                        st.session_state.sb_session = session
                        st.session_state.sb_user_id = session.user.id
                        st.session_state.sb_strava_id = strava_id.strip()
                        st.success("Conta criada com sucesso!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.info("Conta criada! Faça login para continuar.")
                        st.session_state.auth_mode = "login"
                        time.sleep(1.5)
                        st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Já tem conta? Fazer login", use_container_width=True,
                     key="switch_login", type="secondary"):
            st.session_state.auth_mode = "login"
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def _load_supabase_data_into_session():
    """Carrega dados do Supabase para session_state na primeira vez após login."""
    if st.session_state.get("_sb_loaded"):
        return  # já carregou nesta sessão
    user_id = st.session_state.get("sb_user_id")
    if not user_id:
        return
    data = supabase_load_user_data(user_id)
    if not data:
        st.session_state._sb_loaded = True
        return

    # Restaurar perfil do atleta
    profile_raw = data.get("athlete_profile")
    if profile_raw:
        try:
            profile = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
            st.session_state.athlete.update(profile)
        except Exception:
            pass

    # Restaurar credenciais Strava
    if data.get("strava_client_id"):
        st.session_state.client_id = data["strava_client_id"]
    if data.get("strava_client_secret"):
        st.session_state.client_secret = data["strava_client_secret"]

    # Restaurar tokens Strava
    if data.get("strava_tokens"):
        try:
            tokens = json.loads(data["strava_tokens"]) if isinstance(data["strava_tokens"], str) else data["strava_tokens"]
            save_strava_tokens(tokens)
        except Exception:
            pass

    # Restaurar treino e métricas
    if data.get("suggestion"):
        st.session_state.suggestion = data["suggestion"]
    if data.get("atl") is not None:
        st.session_state._atl = data["atl"]
    if data.get("ctl") is not None:
        st.session_state._ctl = data["ctl"]
    if data.get("tsb") is not None:
        st.session_state._tsb = data["tsb"]

    st.session_state._sb_loaded = True


def main():
    st.set_page_config(
        page_title="Strava Running Coach",
        page_icon="🏃",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

    # ── Autenticação via Supabase ──
    if _supabase_available():
        if not st.session_state.get("sb_session"):
            _render_auth_screen()
            return

    # Inicializa session state
    init_session_state()

    # Se logado via Supabase, carregar dados do banco
    if _supabase_available() and st.session_state.get("sb_user_id"):
        _load_supabase_data_into_session()

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
            nome = html_mod.escape(ath.get("nome", ""))
            st.markdown(f'<span class="pill pill-green">● Conectado{" · "+nome if nome else ""}</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<span class="pill pill-red">● Desconectado</span>', unsafe_allow_html=True)
        # Logout button (se logado via Supabase)
        if st.session_state.get("sb_session"):
            if st.button("Sair", key="btn_logout", type="secondary"):
                supabase_logout()
                st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Flags para estado do app
    needs_setup = not all([cid, cs, akey])
    needs_connect = not connected

    # ── Tab navigation (custom button grid 2×2) ──
    TAB_LABELS = ["🏃 Treinos", "📊 Resumo 30d", "⚙️ Config Treino", "🔧 Config App"]
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        _typ = "primary" if st.session_state.active_tab == 0 else "secondary"
        if st.button(TAB_LABELS[0], key="tab_0", use_container_width=True, type=_typ):
            st.session_state.active_tab = 0; st.rerun()
    with r1c2:
        _typ = "primary" if st.session_state.active_tab == 1 else "secondary"
        if st.button(TAB_LABELS[1], key="tab_1", use_container_width=True, type=_typ):
            st.session_state.active_tab = 1; st.rerun()
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        _typ = "primary" if st.session_state.active_tab == 2 else "secondary"
        if st.button(TAB_LABELS[2], key="tab_2", use_container_width=True, type=_typ):
            st.session_state.active_tab = 2; st.rerun()
    with r2c2:
        _typ = "primary" if st.session_state.active_tab == 3 else "secondary"
        if st.button(TAB_LABELS[3], key="tab_3", use_container_width=True, type=_typ):
            st.session_state.active_tab = 3; st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    active_tab = st.session_state.active_tab

    # ══════════════════════════════════════════
    # TAB 1: TREINOS DA SEMANA
    # ══════════════════════════════════════════
    if active_tab == 0:

        if needs_setup or needs_connect:
            st.markdown(f"""<div class="card" style="text-align:center;padding:3rem 2rem">
                <div style="font-size:3rem;margin-bottom:1rem">{'🔑' if needs_setup else '🔗'}</div>
                <p class="section-title" style="font-size:1.2rem">
                {'Configure suas credenciais' if needs_setup else 'Conecte seu Strava'}</p>
                <p class="body-text" style="color:#6E6E73;max-width:420px;margin:0 auto">
                {'Vá na aba <strong>🔧 Configurações app</strong> para inserir suas credenciais de API.' if needs_setup
                 else 'Vá na aba <strong>🔧 Configurações app</strong> para autorizar o acesso ao Strava.'}</p>
            </div>""", unsafe_allow_html=True)

        # Show weekly plan cards if a suggestion exists
        elif st.session_state.suggestion:
            plan = parse_weekly_plan(st.session_state.suggestion)
            if plan:
                st.markdown('<p class="section-title" style="margin-bottom:1rem">Plano da semana</p>',
                            unsafe_allow_html=True)
                render_weekly_cards(plan, suggestion=st.session_state.suggestion)
                st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

            # Full AI analysis (skip "Treino de hoje" — it's shown in the day card detail)
            st.markdown("<hr>", unsafe_allow_html=True)
            render_results(st.session_state.suggestion, skip_sections={"Treino de hoje"})

            # PDF download
            st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
            col_pdf, _ = st.columns([1, 2])
            with col_pdf:
                with st.spinner("Preparando PDF..."):
                    try:
                        # Need runs for PDF — fetch them
                        try:
                            token = get_valid_token(cid, cs)
                            runs_for_pdf = fetch_runs(token)
                        except Exception:
                            runs_for_pdf = []
                        pdf = make_pdf(st.session_state.suggestion, ath, runs_for_pdf,
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
                        logging.exception("Erro ao gerar PDF")
                        st.error("Erro ao gerar PDF. Tente novamente.")
        elif not needs_setup and not needs_connect:
            # Onboarding message — connected but no training generated yet
            st.markdown("""<div class="card" style="text-align:center;padding:2.5rem 2rem">
                <div style="font-size:2.5rem;margin-bottom:0.8rem">📋</div>
                <p class="section-title" style="font-size:1.2rem">Nenhum treino gerado ainda</p>
                <p class="body-text" style="color:#6E6E73;max-width:400px;margin:0 auto">
                Clique no botão abaixo para gerar seu plano de treino semanal personalizado
                com base nas suas atividades recentes do Strava.</p>
            </div>""", unsafe_allow_html=True)

        if not needs_setup and not needs_connect:
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # ── Rest day indicator + Generate button (só se conectado) ──
        gerar = False
        if not needs_setup and not needs_connect:
            desc_idx = ath.get("dias_descanso", [])
            dias_pt  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
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

            # ── Generate button at BOTTOM ──
            btn_label = "🧘 Ver sugestão de recuperação" if eh_desc else "🏃 Gerar treino semanal"

            col_btn, col_sp = st.columns([1, 2])
            with col_btn:
                gerar = st.button(btn_label, use_container_width=True, key="gen_treino")

        if gerar:
            if not ath.get("nome"):
                st.warning("Preencha seu perfil em Configurações treino antes de gerar o treino.")
            elif not ath.get("objetivo", "").strip():
                st.warning("Preencha o **Objetivo** na aba ⚙️ Config Treino antes de gerar o treino.")
            elif not akey:
                st.warning("Anthropic API Key não encontrada. Configure via st.secrets no painel do Streamlit Cloud.")
            else:
                progress_box = st.empty()
                progress_bar = st.progress(0)
                try:
                    progress_box.markdown(
                        '<div style="padding:0.6rem 0;color:#6E6E73;font-size:0.88rem;font-weight:500">'
                        '🔄 Buscando atividades do Strava...</div>',
                        unsafe_allow_html=True)
                    progress_bar.progress(15)
                    token = get_valid_token(cid, cs)
                    runs = fetch_runs(token)
                    if not runs:
                        st.warning("Nenhuma atividade encontrada nos últimos 28 dias.")
                    else:
                        progress_box.markdown(
                            '<div style="padding:0.6rem 0;color:#6E6E73;font-size:0.88rem;font-weight:500">'
                            '🧠 Enviando dados para o treinador IA...</div>',
                            unsafe_allow_html=True)
                        progress_bar.progress(30)
                        import time as _t
                        _t.sleep(0.3)

                        sug, a, c, t = generate(runs, ath, akey)

                        progress_box.markdown(
                            '<div style="padding:0.6rem 0;color:#6E6E73;font-size:0.88rem;font-weight:500">'
                            '✅ Plano de treino recebido! Montando visualização...</div>',
                            unsafe_allow_html=True)
                        progress_bar.progress(90)
                        _t.sleep(0.2)

                        st.session_state.update({"suggestion": sug,
                                                 "_atl": a, "_ctl": c, "_tsb": t})
                        # Persist training cache
                        _store = _get_persistent_store()
                        _store.update({"suggestion": sug, "_atl": a, "_ctl": c, "_tsb": t})
                        # Save to Supabase
                        _uid = st.session_state.get("sb_user_id")
                        if _uid:
                            supabase_save_training(_uid, sug, a, c, t)
                        progress_bar.progress(100)
                        _t.sleep(0.3)
                        st.rerun()
                except StravaLimitError as e:
                    st.error(str(e))
                    _render_strava_limit_help()
                except Exception as e:
                    logging.exception("Erro ao gerar sugestão")
                    st.error("Erro ao gerar sugestão. Verifique sua conexão e tente novamente.")
                finally:
                    progress_box.empty()
                    progress_bar.empty()

    # ══════════════════════════════════════════
    # TAB 2: RESUMO ÚLTIMOS 30 DIAS
    # ══════════════════════════════════════════
    if active_tab == 1:

        if needs_setup or needs_connect:
            st.markdown(f"""<div class="card" style="text-align:center;padding:3rem 2rem">
                <div style="font-size:3rem;margin-bottom:1rem">📊</div>
                <p class="section-title" style="font-size:1.2rem">
                {'Configure suas credenciais' if needs_setup else 'Conecte seu Strava'}</p>
                <p class="body-text" style="color:#6E6E73;max-width:420px;margin:0 auto">
                Vá na aba <strong>🔧 Configurações app</strong> para
                {'inserir suas credenciais de API' if needs_setup else 'autorizar o acesso ao Strava'}
                e ver o resumo dos seus treinos.</p>
            </div>""", unsafe_allow_html=True)
        else:
            # Load data
            try:
                token = get_valid_token(cid, cs)
            except StravaLimitError as e:
                st.error(str(e))
                _render_strava_limit_help()
                token = None
            except Exception as e:
                logging.exception("Erro de autenticação Strava")
                st.error("Erro de autenticação. Reconecte seu Strava na aba Configurações.")
                token = None

            if token:
                with st.spinner("Carregando atividades do Strava..."):
                    try:
                        runs = fetch_runs(token)
                    except StravaLimitError as e:
                        st.error(str(e))
                        _render_strava_limit_help()
                        runs = []
                    except Exception as e:
                        logging.exception("Erro ao buscar atividades")
                        st.error("Erro ao buscar atividades do Strava. Tente novamente.")
                        runs = []

                if not runs:
                    st.markdown("""<div class="card" style="text-align:center;padding:2rem">
                        <p style="font-size:2rem">😴</p>
                        <p class="body-text">Nenhuma atividade encontrada nos últimos 28 dias.</p>
                    </div>""", unsafe_allow_html=True)
                else:
                    run_only  = [r for r in runs if not r.get("_is_walk")]
                    walk_only = [r for r in runs if r.get("_is_walk")]

                    # Compute metrics
                    ref = run_only if run_only else runs
                    total_km = sum(r["distance"] for r in run_only) / 1000
                    avg_pace = fmt_pace(sum(r.get("average_speed", 0) for r in ref) / len(ref))
                    lbd      = loads_by_day(runs, ath)
                    atl, ctl, tsb = atl_ctl_tsb(lbd)
                    tsb_txt, tsb_cls = tsb_label(tsb)
                    trend    = pace_trend(run_only or runs)
                    doff     = days_off(runs)
                    doff_txt = (f"Ativo {'' if doff == 0 else f'há {doff}d'}" if doff is not None else "—")

                    # ── Bento Grid de métricas (2×2 on mobile) ──
                    row1_c1, row1_c2 = st.columns(2)
                    with row1_c1:
                        st.markdown(metric_card("Volume 28 dias", f"{total_km:.1f}", "km",
                                                f"{len(run_only)} corridas" + (f" · {len(walk_only)} cam." if walk_only else ""),
                                                "badge-orange"),
                                    unsafe_allow_html=True)
                    with row1_c2:
                        st.markdown(metric_card("Pace médio", avg_pace, sub=trend or ""),
                                    unsafe_allow_html=True)
                    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
                    row2_c1, row2_c2 = st.columns(2)
                    with row2_c1:
                        st.markdown(metric_card("ATL / CTL", f"{atl} / {ctl}",
                                                sub="fadiga / condicionamento"),
                                    unsafe_allow_html=True)
                    with row2_c2:
                        st.markdown(metric_card("Forma (TSB)", f"{tsb:+.1f}",
                                                sub=doff_txt, badge=tsb_txt, badge_cls=tsb_cls),
                                    unsafe_allow_html=True)

                    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

                    # ── Weekly km bar chart (in a card) ────
                    weekly_data = compute_weekly_km(runs)
                    st.markdown(
                        '<div class="card" style="padding:1.2rem 1.4rem">', unsafe_allow_html=True)
                    render_weekly_km_chart(weekly_data)
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

                    # ── TSB status card ──
                    tsb_color = "#34C759" if tsb >= 0 else ("#FF9500" if tsb >= -10 else "#FF3B30")
                    tsb_icon = "✅" if tsb >= 0 else ("⚠️" if tsb >= -10 else "🔴")
                    st.markdown(
                        f'<div class="card" style="padding:1rem 1.4rem;'
                        f'border-left:4px solid {tsb_color}">'
                        f'<div style="display:flex;align-items:center;gap:0.6rem">'
                        f'<span style="font-size:1.2rem">{tsb_icon}</span>'
                        f'<div>'
                        f'<span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;'
                        f'letter-spacing:0.06em;color:#6E6E73;display:block">Estado atual</span>'
                        f'<span style="font-size:1rem;font-weight:700;color:#1D1D1F">{tsb_txt}</span>'
                        f'<span style="font-size:0.82rem;color:#6E6E73;margin-left:0.5rem">'
                        f'TSB {tsb:+.1f} · {doff_txt}</span>'
                        f'</div></div></div>',
                        unsafe_allow_html=True)

                    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

                    # ── Activity cards ──
                    lbl_count = f"{len(run_only)} corridas" + (f" + {len(walk_only)} caminhadas" if walk_only else "")
                    st.markdown(
                        f'<p class="section-title">Atividades recentes  ·  {lbl_count}</p>',
                        unsafe_allow_html=True)

                    for i, r in enumerate(runs[:10]):
                        is_w = r.get("_is_walk", False)
                        tipo_color = "#1A8A3A" if is_w else "#FC4C02"
                        tipo_txt = "Caminhada" if is_w else "Corrida"
                        tipo_icon = "🚶" if is_w else "🏃"
                        dt_str = r["start_date"][:10]
                        try:
                            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                            dt_display = dt_obj.strftime("%d/%m")
                            dia_semana_short = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"][dt_obj.weekday()]
                        except Exception:
                            dt_display = dt_str
                            dia_semana_short = ""
                        dist = fmt_dist(r["distance"])
                        dur = fmt_dur(r.get("moving_time", 0))
                        pace = fmt_pace(r.get("average_speed"))
                        hr_txt = f'{round(r["average_heartrate"])} bpm' if r.get("average_heartrate") else ""
                        carga = f'{run_load(r, ath):.0f}'
                        name = html_mod.escape(r.get("name", ""))

                        hr_chip = (
                            f'<span style="display:inline-block;font-size:0.72rem;font-weight:600;'
                            f'color:#FF3B30;background:rgba(255,59,48,0.08);padding:0.15rem 0.45rem;'
                            f'border-radius:6px;margin-left:0.3rem">♥ {hr_txt}</span>'
                        ) if hr_txt else ""

                        st.markdown(
                            f'<div style="background:#FFFFFF;border-radius:14px;padding:0.9rem 1.1rem;'
                            f'box-shadow:0 1px 8px rgba(0,0,0,0.04);border:1px solid rgba(0,0,0,0.04);'
                            f'margin-bottom:0.5rem;border-left:3px solid {tipo_color}">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center">'
                            f'<div>'
                            f'<span style="font-weight:700;color:#1D1D1F;font-size:0.9rem">'
                            f'{tipo_icon} {name or tipo_txt}</span>'
                            f'<span style="font-size:0.78rem;color:#AEAEB2;margin-left:0.5rem">'
                            f'{dia_semana_short} {dt_display}</span>'
                            f'</div>'
                            f'<span style="font-size:0.72rem;font-weight:600;color:{tipo_color};'
                            f'background:{"rgba(26,138,58,0.08)" if is_w else "rgba(252,76,2,0.08)"};'
                            f'padding:0.15rem 0.5rem;border-radius:6px">{tipo_txt}</span>'
                            f'</div>'
                            f'<div style="display:flex;gap:0.8rem;margin-top:0.4rem;flex-wrap:wrap">'
                            f'<span style="font-size:0.82rem;color:#3A3A3C;font-weight:500">{dist}</span>'
                            f'<span style="font-size:0.82rem;color:#6E6E73">{dur}</span>'
                            f'<span style="font-size:0.82rem;color:#6E6E73">{pace}</span>'
                            f'{hr_chip}'
                            f'<span style="font-size:0.72rem;color:#AEAEB2;margin-left:auto">⚡ {carga}</span>'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

    # ══════════════════════════════════════════
    # TAB 3: CONFIGURAÇÕES TREINO
    # ══════════════════════════════════════════
    if active_tab == 2:

        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Perfil do Atleta</span>', unsafe_allow_html=True)
        p = ath
        pc1, pc2 = st.columns(2)
        with pc1:
            nome_v  = st.text_input("Nome", value=p.get("nome", ""), placeholder="Seu nome",
                                    key="cfg_nome")
            obj_v   = st.text_input("Objetivo", value=p.get("objetivo", ""),
                                    placeholder="ex: completar meia maratona",
                                    key="cfg_objetivo")
            prova_v = st.text_input("Prova alvo (opcional)", value=p.get("prova_alvo", ""),
                                    placeholder="ex: Maratona de SP",
                                    key="cfg_prova")
            data_v  = st.text_input("Data da prova (opcional)", value=p.get("data_prova", ""),
                                    placeholder="AAAA-MM-DD",
                                    key="cfg_data_prova")
        with pc2:
            nivel_v   = st.selectbox("Nível do atleta", ["iniciante", "intermediário", "avançado"],
                                     index=["iniciante", "intermediário", "avançado"].index(
                                         p.get("nivel", "intermediário")),
                                     key="cfg_nivel")
            treinos_v = st.slider("Número de treinos por semana", 2, 6,
                                  value=p.get("treinos_semana", 3),
                                  key="cfg_treinos")
            fc_max_v  = st.number_input("FC máxima (bpm)", 140, 220,
                                        value=p.get("fc_max", 185),
                                        help="Estimativa: 220 − sua idade",
                                        key="cfg_fc_max")
            fc_rep_v  = st.number_input("FC repouso (bpm)", 30, 80,
                                        value=p.get("fc_repouso", 50),
                                        key="cfg_fc_rep")
        pace_v = st.text_input("Pace limiar (mm:ss /km)", value=p.get("pace_limiar", "5:30"),
                               placeholder="ex: 5:30",
                               help="Pace que você sustenta por ~1 hora no máximo",
                               key="cfg_pace")
        st.markdown('</div>', unsafe_allow_html=True)

        # Dias de descanso
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Dias de Descanso Fixos</span>', unsafe_allow_html=True)
        desc_cfg = ath.get("dias_descanso", [])
        cols_dias = st.columns(7)
        selecionados_desc = []
        for i, (col, dia) in enumerate(zip(cols_dias, DIAS_SEMANA)):
            with col:
                if st.checkbox(dia[:3], value=(i in desc_cfg), key=f"desc_d{i}"):
                    selecionados_desc.append(i)
        st.markdown('</div>', unsafe_allow_html=True)

        # Dias de fortalecimento de pernas
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Dias de Fortalecimento de Pernas</span>', unsafe_allow_html=True)
        fort_cfg = ath.get("dias_fortalecimento", [])
        cols_fort = st.columns(7)
        selecionados_fort = []
        for i, (col, dia) in enumerate(zip(cols_fort, DIAS_SEMANA)):
            with col:
                if st.checkbox(dia[:3], value=(i in fort_cfg), key=f"fort_d{i}"):
                    selecionados_fort.append(i)
        st.markdown('</div>', unsafe_allow_html=True)

        # Save button
        if st.button("Salvar configurações de treino", key="save_training_config", use_container_width=True):
            new_ath = {
                "nome": nome_v, "nivel": nivel_v, "objetivo": obj_v,
                "prova_alvo": prova_v, "data_prova": data_v,
                "treinos_semana": treinos_v, "fc_max": fc_max_v,
                "fc_repouso": fc_rep_v, "pace_limiar": pace_v,
                "dias_descanso": selecionados_desc,
                "dias_fortalecimento": selecionados_fort,
            }
            save_athlete_profile(new_ath)
            # Persist athlete settings in cache so they survive session resets
            _store = _get_persistent_store()
            _store["athlete_objetivo"] = obj_v
            _store["athlete_dias_descanso"] = selecionados_desc
            _store["athlete_dias_fortalecimento"] = selecionados_fort
            _store["athlete_treinos_semana"] = treinos_v
            # Save to Supabase
            _uid = st.session_state.get("sb_user_id")
            if _uid:
                supabase_save_athlete_profile(_uid, new_ath)
            st.success("Configurações de treino salvas.")

    # ══════════════════════════════════════════
    # TAB 4: CONFIGURAÇÕES APP
    # ══════════════════════════════════════════
    if active_tab == 3:

        # Credenciais Strava (editáveis — salvas em session_state)
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<span class="form-label">Credenciais Strava</span>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            client_id_v = st.text_input("Strava Client ID", value=cid,
                                        placeholder="214364",
                                        key="app_client_id")
        with c2:
            client_secret_v = st.text_input("Strava Client Secret", value=cs,
                                            type="password", placeholder="••••••••",
                                            key="app_client_secret")
        redirect_v = st.text_input("URL do App (para OAuth)",
                                   value=st.session_state.get("redirect_uri", ""),
                                   placeholder="https://seu-app.streamlit.app",
                                   help="Cole aqui a URL do seu app no Streamlit Cloud",
                                   key="app_redirect_uri")
        if st.button("Salvar credenciais", key="save_creds"):
            st.session_state.client_id = client_id_v
            st.session_state.client_secret = client_secret_v
            st.session_state.redirect_uri = redirect_v
            # Persist credentials in cache (survives session resets)
            _store = _get_persistent_store()
            _store["client_id"] = client_id_v
            _store["client_secret"] = client_secret_v
            # Save to Supabase
            _uid = st.session_state.get("sb_user_id")
            if _uid:
                supabase_save_strava_credentials(_uid, client_id_v, client_secret_v)
            st.success("Credenciais salvas.")
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
                    f'<a href="{auth_url}" target="_blank" style="display:inline-block;'
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
                                         placeholder="https://seu-app.streamlit.app/?code=...",
                                         key="manual_redirect_url")
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
                                    firstname = html_mod.escape(
                                        data.get('athlete',{}).get('firstname','Atleta'))
                                    st.success(f"Conectado! Bem-vindo, {firstname}!")
                                    st.rerun()
                                except StravaLimitError as e:
                                    st.error(str(e))
                                    _render_strava_limit_help()
                                except Exception as e:
                                    logging.exception("Erro na conexão manual Strava")
                                    st.error("Erro na conexão. Verifique a URL e tente novamente.")
            else:
                st.info("Preencha o Client ID do Strava acima para conectar.")
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    import pandas  # validar dependência
    main()
