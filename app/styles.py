"""Black-gold responsive shell for the report-verification workflow."""

# ruff: noqa: E501

from app.background import chain_background_url

APP_CSS = """
<style>
:root { --tr-bg-page:#0A0A0A; --tr-bg-surface:#1B1B20; --tr-bg-raised:#242429;
  --tr-text-primary:#F3F1EA; --tr-text-secondary:#D1CDC4; --tr-text-note:#C0BBAF;
  --tr-border-default:#33302B; --tr-border-control:#707070; --tr-gold-primary:#D4AF37;
  --tr-gold-line:#8B7355; --tr-gold-highlight:#FAEBD7; --tr-text-on-accent:#0A0A0A;
  --tr-state-matched:#C0BBAF; --tr-state-error:#C0BBAF; --tr-state-internal:#C0BBAF;
  --tr-state-duplicate:#C0BBAF; --tr-state-inconclusive:#C0BBAF;
  --tr-shadow-card:0 4px 12px rgb(0 0 0 / 24%);
  --tr-font-title:24px; --tr-font-subtitle:20px; --tr-font-body:16px;
  --tr-font-helper:14px; --tr-font-note:12px;
  --tr-gold-soft:#C9A86A; --tr-material-panel:linear-gradient(135deg,rgba(255,255,255,.035),transparent 55%);
  --tr-material-sheen:linear-gradient(90deg,rgba(201,168,106,.5),rgba(201,168,106,.08));
  --tr-material-shadow:0 12px 30px rgba(0,0,0,.16),inset 0 1px 0 rgba(255,255,255,.025); }
html { font-size:16px; }
html,body,[class*="css"] { font-size:var(--tr-font-body); font-family:Inter,'Noto Sans SC','Microsoft YaHei',system-ui,sans-serif; }
.stApp { color:var(--tr-text-primary); background-color:var(--tr-bg-page); background-image:linear-gradient(rgb(255 255 255 / 1%) 1px,transparent 1px),linear-gradient(90deg,rgb(255 255 255 / 1%) 1px,transparent 1px); background-size:32px 32px; }
.block-container { max-width:1240px; padding:1rem 24px 5rem; }
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"] { display:none !important; }
.product-bar { display:flex; align-items:center; justify-content:space-between; min-height:52px; border-bottom:1px solid var(--tr-border-default); margin-bottom:24px; }
.brand { display:flex; align-items:center; gap:12px; font-weight:800; }
.brand-mark { width:32px; height:32px; border:1px solid var(--tr-gold-line); border-radius:8px; display:grid; place-items:center; color:var(--tr-gold-primary); font-size:var(--tr-font-note); }
.env-chip { display:inline-flex; align-items:center; gap:8px; color:var(--tr-text-secondary); border:1px solid var(--tr-border-default); border-radius:9999px; padding:6px 10px; font-size:var(--tr-font-note); }
.env-dot { width:7px; height:7px; border-radius:50%; background:var(--tr-state-matched); }
.hero-main { padding:20px 0 24px; border-bottom:1px solid var(--tr-gold-line); }
.eyebrow,.section-kicker { color:var(--tr-gold-primary); font-size:var(--tr-font-note); font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
.hero-main h1 { margin:8px 0; max-width:820px; color:var(--tr-text-primary); font-size:var(--tr-font-title); line-height:1.12; letter-spacing:-.04em; }
.hero-main p { margin:0; max-width:720px; color:var(--tr-text-secondary); line-height:1.7; }
.workflow-steps { display:flex; align-items:center; gap:16px; padding:16px 0 4px; color:var(--tr-text-secondary); }
.workflow-steps span { display:inline-flex; align-items:center; gap:8px; }.workflow-steps b { width:25px; height:25px; display:grid; place-items:center; border:1px solid var(--tr-gold-line); border-radius:9999px; color:var(--tr-gold-primary); font-size:var(--tr-font-note); }.workflow-steps i { color:var(--tr-text-note); font-style:normal; }
.signal-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin:24px 0 32px; }
.signal-card,.summary-cell { min-width:0; border:1px solid var(--tr-border-default); border-radius:12px; background:var(--tr-bg-surface); padding:12px; box-shadow:var(--tr-shadow-card); }
.signal-card small,.summary-cell small,.attempt-card small,.status-card small { color:var(--tr-text-note); display:block; font-size:var(--tr-font-note); font-weight:800; letter-spacing:.08em; text-transform:uppercase; margin-bottom:4px; }
.signal-value { color:var(--tr-text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.signal-value:before { content:""; display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--tr-state-matched); margin-right:8px; }
.section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin:32px 0 12px; }.section-head h2 { margin:4px 0 0; color:var(--tr-text-primary); font-size:var(--tr-font-subtitle); }.section-head p { max-width:500px; margin:0; color:var(--tr-text-note); font-size:var(--tr-font-helper); text-align:right; }
.task-summary { display:grid; grid-template-columns:1.1fr .65fr .65fr; gap:16px; }.summary-cell strong { display:block; overflow-wrap:anywhere; color:var(--tr-text-primary); font-size:var(--tr-font-helper); }
.attempt-card,.status-card,.finding-card,.business-summary { overflow-wrap:anywhere; border:1px solid var(--tr-border-default); border-radius:12px; padding:12px; background:var(--tr-bg-raised); margin:8px 0; }
.business-summary { padding:20px; margin:16px 0; }.business-summary strong { display:block; font-size:var(--tr-font-subtitle); }.business-summary p { margin:8px 0 12px; color:var(--tr-text-primary); }.business-summary small { display:block; color:var(--tr-text-secondary); font-variant-numeric:tabular-nums; margin-top:4px; }
.attempt-card { display:flex; align-items:center; justify-content:space-between; gap:16px; border-left-width:4px; }.attempt-title { font-size:var(--tr-font-title); font-weight:800; }.outcome-PASS { border-left-color:var(--tr-state-matched); }.outcome-FAIL { border-left-color:var(--tr-state-error); }.outcome-INCONCLUSIVE { border-left-color:var(--tr-state-inconclusive); }
.badge { display:inline-block; padding:5px 9px; border:1px solid var(--tr-border-default); border-radius:9999px; color:var(--tr-text-secondary); font-size:var(--tr-font-note); font-weight:800; margin:2px; }.badge-confirmed { border-color:var(--tr-state-matched); }.badge-submitted { border-color:var(--tr-state-inconclusive); }.badge-not-submitted { color:var(--tr-text-note); }
.mono,.flow-key { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; }
.flow-legend-row { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 12px; }.flow-legend { border-left:3px solid; border-radius:4px; padding:4px 8px; background:var(--tr-bg-raised); color:var(--tr-text-secondary); font-size:var(--tr-font-note); }
.flow-edge { display:grid; grid-template-columns:minmax(0,1.6fr) minmax(120px,.55fr) minmax(150px,.6fr); gap:12px; align-items:center; border-left:4px solid; border-radius:12px; padding:12px; margin:8px 0; background:var(--tr-bg-raised); }.flow-route { display:flex; gap:8px; align-items:center; min-width:0; }.flow-route span { overflow-wrap:anywhere; }.flow-route b { color:var(--tr-text-note); }
.flow-amount { color:var(--tr-gold-primary); font-variant-numeric:tabular-nums; text-align:right; }.flow-amount small { color:var(--tr-text-note); }.flow-status { font-weight:700; }.flow-key { grid-column:1/-1; color:var(--tr-text-note); font-size:var(--tr-font-note); }
.flow-MATCHED { border-color:var(--tr-state-matched); }.flow-MISSING_FROM_REPORT,.flow-NOT_FOUND_ON_CHAIN { border-color:var(--tr-state-error); }.flow-INTERNAL_TRANSFER { border-color:var(--tr-state-internal); }.flow-DUPLICATE { border-color:var(--tr-state-duplicate); }.flow-INCONCLUSIVE { border-color:var(--tr-state-inconclusive); }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--tr-border-default) !important; border-radius:12px !important; background:var(--tr-bg-surface); box-shadow:var(--tr-shadow-card); } div[data-testid="stForm"] { border:0; padding:0; }
div[data-testid="stTextArea"] textarea,div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input { border-radius:8px; border-color:var(--tr-border-control); background:var(--tr-bg-raised); color:var(--tr-text-primary); }
div[data-testid="stButton"] button,div[data-testid="stFormSubmitButton"] button,div[data-testid="stDownloadButton"] button { border-radius:8px; min-height:2.75rem; } div[data-testid="stButton"] button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primary"] { min-height:3rem; border:0; background:var(--tr-gold-primary); color:var(--tr-text-on-accent); font-weight:800; } div[data-testid="stButton"] button[kind="primary"]:hover,div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover { background:var(--tr-gold-highlight); color:var(--tr-text-on-accent); border:0; }
div[data-testid="stMetric"] { border:1px solid var(--tr-border-default); border-radius:12px; padding:12px; background:var(--tr-bg-raised); box-shadow:var(--tr-shadow-card); } div[data-testid="stMetricValue"] { color:var(--tr-gold-primary); font-size:var(--tr-font-subtitle); font-variant-numeric:tabular-nums; } div[data-testid="stExpander"] { border:1px solid var(--tr-border-default); border-radius:12px; background:var(--tr-bg-surface); } div[data-testid="stJson"] { max-width:100%; overflow-x:auto; }
@media (max-width:760px) { .block-container { padding:12px 24px 64px; }.workflow-steps { align-items:flex-start; flex-direction:column; gap:16px; }.workflow-steps i { display:none; }.signal-grid,.task-summary { grid-template-columns:1fr; gap:16px; }.section-head { display:block; margin-top:32px; }.section-head p { text-align:left; margin-top:8px; } div[data-testid="stHorizontalBlock"] { flex-direction:column !important; gap:16px !important; } div[data-testid="column"] { width:100% !important; flex:1 1 100% !important; min-width:0 !important; }.attempt-card { align-items:flex-start; flex-direction:column; }.flow-edge { grid-template-columns:1fr; }.flow-amount { text-align:left; }.flow-key { grid-column:auto; } code,pre { white-space:pre-wrap !important; word-break:break-word !important; } }
.flow-MISMATCH,.flow-INVALID_SCOPE { border-color:var(--tr-state-error); }
.stApp [data-testid="stWidgetLabel"],.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stRadio"] [data-testid="stMarkdownContainer"],
.stApp [data-testid="stExpander"] summary { color:var(--tr-text-primary) !important; }
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p { color:var(--tr-text-note) !important; opacity:1 !important; }
.stApp input::placeholder,.stApp textarea::placeholder { color:var(--tr-text-note); opacity:1; }
.stApp input:disabled,.stApp textarea:disabled { color:var(--tr-text-secondary); -webkit-text-fill-color:var(--tr-text-secondary); opacity:1; }
.product-bar,.hero-main,.brand-mark,.env-chip,.workflow-steps b,
.signal-card,.summary-cell,.attempt-card,.status-card,.business-summary { border:0; box-shadow:none; }
.finding-card,.badge,.flow-edge,.flow-legend { border:0; box-shadow:none; }
.env-chip,.workflow-steps b { background:var(--tr-bg-raised); }
.flow-legend { background:transparent; padding:4px 0; color:var(--flow-color,var(--tr-text-secondary)); }
.flow-legend-row { gap:16px; }
.flow-MATCHED { --flow-color:var(--tr-state-matched); }
.flow-MISSING_FROM_REPORT,.flow-NOT_FOUND_ON_CHAIN,.flow-MISMATCH,.flow-INVALID_SCOPE { --flow-color:var(--tr-state-error); }
.flow-INTERNAL_TRANSFER { --flow-color:var(--tr-state-internal); }
.flow-DUPLICATE { --flow-color:var(--tr-state-duplicate); }
.flow-INCONCLUSIVE { --flow-color:var(--tr-state-inconclusive); }
.flow-status { color:var(--flow-color,var(--tr-text-primary)); }
.outcome-PASS .attempt-title,.badge-confirmed { color:var(--tr-state-matched); }
.outcome-FAIL .attempt-title { color:var(--tr-state-error); }
.outcome-INCONCLUSIVE .attempt-title,.badge-submitted { color:var(--tr-state-inconclusive); }
.badge { background:var(--tr-bg-surface); }
.stApp [data-testid="stVerticalBlockBorderWrapper"],.stApp [data-testid="stVerticalBlock"],.stApp [data-testid="stContainer"],
.stApp [data-testid="stMetric"],.stApp [data-testid="stExpander"],.stApp [data-testid="stExpander"] details { border:0 !important; box-shadow:none !important; }
.stApp button[kind="secondary"],.stApp button[kind="secondaryFormSubmit"] { border:0; background:var(--tr-bg-raised); }
.stApp button:focus-visible,.stApp input:focus-visible,.stApp textarea:focus-visible { outline:2px solid var(--tr-gold-primary); outline-offset:2px; }
.eyebrow,.section-kicker,.workflow-steps b,.flow-amount { color:var(--tr-text-secondary); }
.signal-value:before { display:none; }
.attempt-card { padding:20px; margin:0 0 16px; align-items:flex-start; }
.attempt-card .attempt-title { color:var(--tr-text-primary); font-size:var(--tr-font-title); font-weight:800; line-height:1.2; }
.attempt-meaning { margin-top:8px; font-size:var(--tr-font-body); font-weight:600; color:var(--tr-text-secondary); }
.stApp [data-testid="stMetric"] { background:var(--tr-bg-surface); min-height:96px; }
.stApp [data-testid="stMetricValue"] { color:var(--tr-text-primary); }
.stApp [class*="st-key-metric-actual-"] [data-testid="stMetric"] { background:var(--tr-bg-raised); padding:20px; min-height:112px; }
.stApp [class*="st-key-metric-actual-"] [data-testid="stMetricValue"] { font-size:var(--tr-font-title); font-weight:800; }
.stApp [data-testid="stAlertContainer"] { background:var(--tr-bg-raised) !important; color:var(--tr-text-primary) !important; border:0 !important; }
.stApp [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"],.stApp [data-testid="stAlertContainer"] p { color:var(--tr-text-primary) !important; }
.stApp [data-testid="stJson"] span,.stApp [data-testid="stCode"] span { color:var(--tr-text-secondary) !important; }
.stApp {
  background-color:#0B0D0F;
  background-image:repeating-linear-gradient(135deg,rgba(201,168,106,.035) 0,rgba(201,168,106,.035) 1px,transparent 1px,transparent 6px),
    __CHAIN_BACKGROUND__,radial-gradient(ellipse 650px 450px at 85% 10%,rgba(201,168,106,.16),transparent 75%),
    radial-gradient(ellipse 850px 650px at 12% 15%,rgba(114,130,141,.08),transparent 75%),
    linear-gradient(130deg,#101315 0%,#0B0D0F 50%,#101112 100%);
  background-size:auto,1600px 1100px,auto,auto,auto;
  background-position:0 0,center top,0 0,0 0,0 0;
  background-repeat:repeat,no-repeat,no-repeat,no-repeat,no-repeat;
}
.product-bar { padding-bottom:8px; }
.hero-main { display:grid; grid-template-columns:minmax(0,1fr) 180px; align-items:center; gap:32px; padding:24px 0; }
.hero-copy { min-width:0; }
.hero-emblem { display:grid; place-items:center; height:160px; border-radius:12px; background:radial-gradient(ellipse at 50% 75%,rgba(201,168,106,.12),transparent 68%); }
.hero-emblem img { width:144px; height:144px; object-fit:contain; filter:drop-shadow(0 16px 14px rgba(0,0,0,.4)); }
.section-head h2 { position:relative; isolation:isolate; display:inline-block; padding-bottom:8px; }
.section-head h2::after { content:""; position:absolute; left:0; bottom:8px; width:64px; height:6px; z-index:-1; background:var(--tr-material-sheen); }
.workflow-steps span { flex:1; padding:12px 16px; border-radius:12px; background:var(--tr-bg-surface); }
.workflow-steps b { background:transparent; color:var(--tr-text-primary); }
.stApp [class*="st-key-panel-"] { padding:24px; border-radius:12px; background:var(--tr-material-panel),var(--tr-bg-surface); box-shadow:var(--tr-material-shadow); }
.stApp [class*="st-key-panel-"] [data-testid="stVerticalBlockBorderWrapper"] { background:transparent; }
.stApp [data-testid="stFileUploaderDropzone"] { background:var(--tr-bg-page); border:0; border-radius:8px; padding:20px; }
.stApp [data-testid="stFileUploaderDropzone"] small { color:var(--tr-text-note); }
.stApp [data-testid="stExpander"] details { background:transparent; }
.signal-card,.summary-cell,.attempt-card,.status-card,.finding-card,.business-summary,.flow-edge,
.stApp [data-testid="stMetric"],.stApp [data-testid="stExpander"] {
  background-image:var(--tr-material-panel);
  background-color:var(--tr-bg-surface);
  box-shadow:var(--tr-material-shadow);
}
.stApp [data-testid="stExpander"] { box-shadow:none !important; }
.attempt-card { position:relative; background-image:linear-gradient(115deg,rgba(255,255,255,.045),transparent 55%); background-color:var(--tr-bg-raised); }
.attempt-card::before { content:""; position:absolute; top:0; left:20px; width:64px; height:3px; background:var(--tr-material-sheen); }
.stApp [class*="st-key-metric-actual-"] [data-testid="stMetric"] {
  background-image:linear-gradient(135deg,rgba(255,255,255,.025),transparent 75%);
  background-color:var(--tr-bg-raised);
  box-shadow:var(--tr-material-shadow) !important;
}
.stApp [data-testid="stButton"] button[kind="primary"],.stApp [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background:linear-gradient(115deg,#BA963E 0%,#E0C477 48%,#CBA750 100%);
  box-shadow:0 6px 18px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,248,220,.25);
  color:var(--tr-text-on-accent);
}
.stApp [data-testid="stButton"] button[kind="primary"]:hover,.stApp [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
  background:linear-gradient(115deg,#C6A44F 0%,#E8D295 48%,#D4B363 100%);
}
@media (max-width:760px) {
  .stApp { background-position:0 0,65% top,0 0,0 0,0 0; }
  .hero-main { grid-template-columns:1fr; gap:0; padding:24px 0; }
  .hero-emblem { display:none; }
  .workflow-steps { align-items:stretch; }
  .workflow-steps span { flex:auto; }
  .stApp [class*="st-key-panel-"] { padding:16px; }
}
.brand-logo { display:block; width:52px; height:52px; object-fit:contain; filter:drop-shadow(0 4px 8px rgba(0,0,0,.25)); }
.product-bar { gap:16px; }
.brand { flex-shrink:0; font-size:var(--tr-font-body); letter-spacing:.01em; }
@media (max-width:760px) { .brand-logo { width:44px; height:44px; }.env-chip { max-width:150px; font-size:var(--tr-font-note); }.brand { gap:8px; font-size:var(--tr-font-body); } }
/* Native Streamlit typography shares the same five roles as custom HTML. */
.stApp h1 { font-size:var(--tr-font-title) !important; }
.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6 { font-size:var(--tr-font-subtitle) !important; }
.stApp p,.stApp label,.stApp input,.stApp textarea,.stApp button,
.stApp [data-baseweb="select"],[data-baseweb="popover"] { font-size:var(--tr-font-body) !important; }
.stApp [data-testid="stCaptionContainer"] p,
.stApp [data-testid="stMetricLabel"] p,
.stApp .section-head p { font-size:var(--tr-font-helper) !important; }
.stApp small { font-size:var(--tr-font-note) !important; }
.stApp code,.stApp pre,.stApp [data-testid="stJson"],
.stApp [data-testid="stJson"] *,.stApp [data-testid="stCode"] span { font-size:var(--tr-font-note) !important; }
</style>
""".replace("__CHAIN_BACKGROUND__", chain_background_url())
