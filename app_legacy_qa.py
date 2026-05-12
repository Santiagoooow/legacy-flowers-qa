"""
Legacy Flowers QA — App completa
• Guarda en Google Sheets
• Genera PDF con portada, tortas y tabla de observaciones
• Optimizada para celular (navegador)
"""

import io
import json
import math
import os
from datetime import datetime, date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st

# ── Google Sheets ──────────────────────────
import gspread
from google.oauth2.service_account import Credentials

# ── PDF ────────────────────────────────────
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ═══════════════════════════════════════════
# ⚙️  CONFIG
# ═══════════════════════════════════════════
st.set_page_config(
    page_title="Legacy Flowers QA",
    page_icon="🌹",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROJO   = "#c00000"
VERDE  = "#2e7d32"
GRIS   = "#d9d9d9"

CRITERIOS_PROD = [
    "Apertura", "Tamaño de Botón", "Condición de Botón",
    "Fitosanidad en Botón", "Longitud Tallos",
    "Condición tallos/Follaje", "Fitosanidad en tallos/Follaje",
]
CRITERIOS_MAT = [
    "Capuchón", "Preservante", "Caucho/Cinta",
    "UPC", "Hidratación", "Temperatura Cuarto Frio",
]

# ═══════════════════════════════════════════
# 🎨  CSS
# ═══════════════════════════════════════════
st.markdown(f"""
<style>
  body {{ font-family: Arial, sans-serif; }}
  h2.title-red {{
    color:{ROJO}; font-weight:bold; font-size:1.15rem;
    text-align:center; text-transform:uppercase; line-height:1.3;
  }}
  .section-title {{
    background:{GRIS}; font-weight:bold; padding:6px;
    border:1px solid #000; margin-top:18px;
    text-align:center; font-size:.9rem;
  }}
  .meta-table {{ border-collapse:collapse; font-size:.78rem; width:180px; }}
  .meta-table td {{ border:1px solid #000; padding:4px; }}
  .calc-box {{
    background:#f5f5f5; border:1px solid #ccc;
    padding:14px; border-radius:6px; margin-top:10px;
  }}
  .calc-row {{ display:flex; justify-content:space-between; margin-bottom:6px; }}
  .nc {{ color:{ROJO}; font-weight:bold; }}
  .c  {{ color:{VERDE}; font-weight:bold; }}
  .stRadio > div {{ flex-direction:row !important; gap:10px; }}
  div[data-testid="stNumberInput"] input {{
    border:2px solid {ROJO} !important;
    background:#fff5f5 !important;
    font-weight:bold; color:{ROJO};
  }}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════
# 💾  GOOGLE SHEETS
# ═══════════════════════════════════════════
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_sheet():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open(st.secrets["sheet_name"])
    ws = sh.sheet1
    if ws.row_count == 0 or ws.cell(1, 1).value is None:
        ws.append_row([
            "timestamp","fecha","finca","producto","po",
            "ramos_proc","ramos_eval","porc_muestra","auditor",
            *[f"prod_{c}_status" for c in CRITERIOS_PROD],
            *[f"prod_{c}_qty"    for c in CRITERIOS_PROD],
            *[f"prod_{c}_obs"    for c in CRITERIOS_PROD],
            *[f"mat_{c}_status"  for c in CRITERIOS_MAT],
            *[f"mat_{c}_qty"     for c in CRITERIOS_MAT],
            *[f"mat_{c}_obs"     for c in CRITERIOS_MAT],
            "total_fallas","porc_nc","porc_c",
            "obs_generales","firma_auditor","firma_resp",
        ])
    return ws


def save_to_sheets(record: dict):
    ws = get_sheet()
    row = [
        record["timestamp"], record["fecha"], record["finca"],
        record["producto"], record["po"],
        record["ramos_proc"], record["ramos_eval"], record["porc_muestra"],
        record["auditor"],
        *[record["prod_data"][c]["status"] for c in CRITERIOS_PROD],
        *[record["prod_data"][c]["qty"]    for c in CRITERIOS_PROD],
        *[record["prod_data"][c]["obs"]    for c in CRITERIOS_PROD],
        *[record["mat_data"][c]["status"]  for c in CRITERIOS_MAT],
        *[record["mat_data"][c]["qty"]     for c in CRITERIOS_MAT],
        *[record["mat_data"][c]["obs"]     for c in CRITERIOS_MAT],
        record["total_fallas"], record["porc_nc"], record["porc_c"],
        record["obs_generales"], record["firma_auditor"], record["firma_resp"],
    ]
    ws.append_row(row)


def load_from_sheets() -> pd.DataFrame:
    ws = get_sheet()
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()


# ═══════════════════════════════════════════
# 📊  TORTAS (matplotlib)
# ═══════════════════════════════════════════
def _pie_single(ax, label, qty_nc, total, color_nc=ROJO, color_c=VERDE):
    qty_c   = max(total - qty_nc, 0)
    sizes   = [qty_nc, qty_c] if qty_nc > 0 else [0, max(total,1)]
    clrs    = [color_nc, color_c]
    explode = [0.04, 0] if qty_nc > 0 else [0, 0]
    _, _, autotexts = ax.pie(
        sizes, colors=clrs, explode=explode,
        autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=1.5),
    )
    for at in autotexts:
        at.set_fontsize(9); at.set_fontweight("bold"); at.set_color("white")
    ax.set_title(label, fontsize=8, fontweight="bold", pad=5, wrap=True)


def make_pie_criterios(criterios, data, total, title) -> io.BytesIO:
    n    = len(criterios)
    cols = 3
    rows = math.ceil(n / cols) + 1
    fig, axes = plt.subplots(rows, cols, figsize=(cols*3.2, rows*3))
    fig.suptitle(title, fontsize=13, fontweight="bold", color=ROJO, y=1.01)
    axes = axes.flatten()

    total_nc = 0
    for i, crit in enumerate(criterios):
        qty = data[crit]["qty"]; total_nc += qty
        _pie_single(axes[i], crit, qty, total)

    last = (rows-1)*cols
    for j in range(n, last): axes[j].set_visible(False)
    mid = last + 1
    axes[last].set_visible(False); axes[last+2].set_visible(False)
    _pie_single(axes[mid], f"RESUMEN {title}", total_nc, total,
                color_nc="#8b0000", color_c="#1b5e20")
    axes[mid].set_title(f"RESUMEN {title}\n{total_nc} NC / {total} ramos",
                        fontsize=9, fontweight="bold", color="#8b0000", pad=5)

    patch_nc = mpatches.Patch(color=ROJO,  label="No Conforme")
    patch_c  = mpatches.Patch(color=VERDE, label="Conforme")
    fig.legend(handles=[patch_nc, patch_c], loc="lower center",
               ncol=2, fontsize=9, frameon=False)
    plt.tight_layout(rect=[0,0.04,1,1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf


def make_pie_global(prod_data, mat_data, total) -> io.BytesIO:
    nc_prod = sum(v["qty"] for v in prod_data.values())
    nc_mat  = sum(v["qty"] for v in mat_data.values())
    nc_tot  = nc_prod + nc_mat
    c_tot   = max(total - nc_tot, 0)

    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    fig.suptitle("RESUMEN GLOBAL DE CALIDAD", fontsize=13, fontweight="bold", color=ROJO)
    _pie_single(axes[0], "NC Producto",   nc_prod, total)
    _pie_single(axes[1], "NC Materiales", nc_mat,  total, color_nc="#e65100")

    sizes = [nc_tot, c_tot] if nc_tot > 0 else [0, 1]
    axes[2].pie(sizes, colors=[ROJO, VERDE],
                autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
                startangle=90, pctdistance=0.75,
                wedgeprops=dict(edgecolor="white", linewidth=1.5),
                explode=[0.04,0] if nc_tot > 0 else [0,0])
    axes[2].set_title("C vs NC Total", fontsize=10, fontweight="bold", pad=6)

    patch_nc = mpatches.Patch(color=ROJO,  label="No Conforme")
    patch_c  = mpatches.Patch(color=VERDE, label="Conforme")
    fig.legend(handles=[patch_nc, patch_c], loc="lower center",
               ncol=2, fontsize=9, frameon=False)
    plt.tight_layout(rect=[0,0.08,1,1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf


# ═══════════════════════════════════════════
# 📄  PDF
# ═══════════════════════════════════════════
def generar_pdf(record: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.8*cm, bottomMargin=1.5*cm,
                            leftMargin=1.8*cm, rightMargin=1.8*cm)
    styles  = getSampleStyleSheet()
    rl_rojo = colors.HexColor(ROJO)
    rl_verde= colors.HexColor(VERDE)
    rl_gris = colors.HexColor(GRIS)

    titulo_st = ParagraphStyle("tit", parent=styles["Title"],
                               textColor=rl_rojo, fontSize=15, spaceAfter=4)
    seccion_st = ParagraphStyle("sec", parent=styles["Heading2"],
                                textColor=colors.white, backColor=rl_rojo,
                                fontSize=11, spaceAfter=4, spaceBefore=10,
                                leftIndent=4, borderPadding=(4,4,4,4))
    normal_st = styles["Normal"]
    story = []

    # — Portada
    story.append(Paragraph("🌹 LEGACY FLOWERS", titulo_st))
    story.append(Paragraph(
        "Lista de Chequeo — Aseguramiento de Calidad<br/>Producto Terminado en Finca",
        ParagraphStyle("sub2", parent=styles["Normal"], fontSize=11,
                       textColor=rl_rojo, spaceAfter=8, fontName="Helvetica-Bold")))
    story.append(HRFlowable(width="100%", thickness=2, color=rl_rojo, spaceAfter=10))

    meta = [
        ["Finca",           record["finca"],           "PO",               record["po"]],
        ["Fecha",           record["fecha"],            "Auditor",          record["auditor"]],
        ["Producto",        record["producto"],         "Ramos Procesados", str(record["ramos_proc"])],
        ["Ramos Evaluados", str(record["ramos_eval"]),  "% Muestra",        f"{record['porc_muestra']:.1f}%"],
    ]
    t_meta = Table(meta, colWidths=[3.8*cm,5.8*cm,3.8*cm,4.6*cm])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),rl_gris),("BACKGROUND",(2,0),(2,-1),rl_gris),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),9),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,colors.HexColor("#f9f9f9")]),
    ]))
    story.append(t_meta); story.append(Spacer(1,0.5*cm))

    total   = record["ramos_eval"]
    nc      = record["total_fallas"]
    porc_nc = record["porc_nc"]; porc_c = record["porc_c"]

    t_res = Table([
        ["TOTAL RAMOS EVALUADOS", str(total), "RAMOS CON FALLAS", str(nc)],
        ["% CONFORME", f"{porc_c:.2f}%",     "% NO CONFORME",    f"{porc_nc:.2f}%"],
    ], colWidths=[4.8*cm,4.8*cm,4.8*cm,4.6*cm])
    t_res.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),rl_gris),("BACKGROUND",(2,0),(2,-1),rl_gris),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),10),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("TEXTCOLOR",(1,1),(1,1),rl_verde),("TEXTCOLOR",(3,1),(3,1),rl_rojo),
        ("ALIGN",(1,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(t_res)

    if record.get("obs_generales"):
        story.append(Spacer(1,0.3*cm))
        story.append(Paragraph(f"<b>Observaciones:</b> {record['obs_generales']}", normal_st))

    # — Tortas Producto
    story.append(PageBreak())
    story.append(Paragraph("GRÁFICAS POR CRITERIO — PRODUCTO", seccion_st))
    story.append(Spacer(1,0.3*cm))
    story.append(Image(make_pie_criterios(CRITERIOS_PROD, record["prod_data"], total, "Producto"),
                       width=17*cm, height=14*cm))

    # — Tortas Materiales + Global
    story.append(PageBreak())
    story.append(Paragraph("GRÁFICAS POR CRITERIO — MATERIALES", seccion_st))
    story.append(Spacer(1,0.3*cm))
    story.append(Image(make_pie_criterios(CRITERIOS_MAT, record["mat_data"], total, "Materiales"),
                       width=17*cm, height=11*cm))
    story.append(Spacer(1,0.4*cm))
    story.append(Paragraph("RESUMEN GLOBAL", seccion_st))
    story.append(Image(make_pie_global(record["prod_data"], record["mat_data"], total),
                       width=17*cm, height=6*cm))

    # — Tabla detallada
    story.append(PageBreak())
    story.append(Paragraph("TABLA DETALLADA DE CRITERIOS Y OBSERVACIONES", seccion_st))
    story.append(Spacer(1,0.3*cm))

    tabla = [["#","Categoría","Criterio","Estado","Ramos NC","Observación"]]
    filas_colores = []
    idx = 1
    for cat, criterios, data in [
        ("Producto",   CRITERIOS_PROD, record["prod_data"]),
        ("Materiales", CRITERIOS_MAT,  record["mat_data"]),
    ]:
        for c in criterios:
            v   = data[c]
            est = v["status"]; qty = v["qty"]; obs = v["obs"] or "—"
            tabla.append([str(idx), cat, c, est, str(qty) if est=="NC" else "0", obs])
            filas_colores.append((idx, colors.HexColor("#ffe0e0") if est=="NC" else colors.white))
            idx += 1

    t_det = Table(tabla, colWidths=[0.7*cm,2.8*cm,5*cm,1.6*cm,2*cm,5.9*cm])
    sty = [
        ("BACKGROUND",(0,0),(-1,0),rl_rojo),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
        ("GRID",(0,0),(-1,-1),0.4,colors.grey),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f9f9f9")]),
    ]
    for ri, col in filas_colores:
        if col != colors.white:
            sty += [("BACKGROUND",(0,ri),(-1,ri),col),
                    ("TEXTCOLOR",(3,ri),(3,ri),rl_rojo),
                    ("FONTNAME",(3,ri),(3,ri),"Helvetica-Bold")]
    t_det.setStyle(TableStyle(sty))
    story.append(t_det)

    story.append(Spacer(1,1.2*cm))
    t_firmas = Table([[
        f"Auditor: {record['firma_auditor'] or '________________________'}",
        f"Responsable: {record['firma_resp'] or '________________________'}",
    ]], colWidths=[9*cm,9*cm])
    t_firmas.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
    ]))
    story.append(t_firmas)
    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════
# 🖼️  ENCABEZADO
# ═══════════════════════════════════════════
def render_header():
    hoy = datetime.now().strftime("%d/%m/%Y")
    col_logo, col_title, col_meta = st.columns([0.8,2,1])
    with col_logo:
        try: st.image("logo.png", width=110)
        except: st.write("")
    with col_title:
        st.markdown("<h2 class='title-red'>Lista de Chequeo Aseguramiento de Calidad<br>"
                    "Producto Terminado en Finca</h2>", unsafe_allow_html=True)
    with col_meta:
        st.markdown(f"""<table class="meta-table">
            <tr><td>Consecutivo:</td><td><b>001</b></td></tr>
            <tr><td>Versión:</td><td><b>001</b></td></tr>
            <tr><td>Fecha:</td><td>{hoy}</td></tr>
            </table>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# 🧩  FILA DE CRITERIO
# ═══════════════════════════════════════════
def criterio_row(criterio, prefix, ramos_eval) -> dict:
    key_st = f"{prefix}_status"; key_qty = f"{prefix}_qty"; key_obs = f"{prefix}_obs"
    col_n, col_r, col_q, col_o = st.columns([2,1.2,1.5,2.5])
    with col_n: st.markdown(f"**{criterio}**")
    with col_r:
        status = st.radio("Estado",["C","NC"], key=key_st,
                          horizontal=True, label_visibility="collapsed")
    is_nc = status == "NC"
    with col_q:
        if is_nc:
            qty = st.number_input("Ramos NC", min_value=0,
                                  max_value=int(ramos_eval) if ramos_eval>0 else 9999,
                                  step=1, key=key_qty,
                                  help="Ramos que NO cumplen este criterio")
        else:
            if key_qty in st.session_state: st.session_state[key_qty] = 0
            qty = 0
            st.markdown("<span style='color:#2e7d32;font-size:1.3rem;'>✔</span>",
                        unsafe_allow_html=True)
    with col_o:
        if is_nc:
            obs = st.text_input("Obs", key=key_obs,
                                placeholder="Ej: maltrato, mancha…",
                                label_visibility="collapsed")
            if criterio == "Apertura":
                sc = st.columns(3)
                with sc[0]: st.checkbox("Abierto",  key=f"{prefix}_ab")
                with sc[1]: st.checkbox("Cerrado",  key=f"{prefix}_cer")
                with sc[2]: st.checkbox("Mezclado", key=f"{prefix}_mez")
        else:
            if key_obs in st.session_state: st.session_state[key_obs] = ""
            obs = ""; st.write("")
    return {"status": status, "qty": int(qty), "obs": obs}


# ═══════════════════════════════════════════
# 📝  FORMULARIO
# ═══════════════════════════════════════════
def render_form():
    st.markdown('<div class="section-title">📋 DATOS GENERALES</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        finca    = st.text_input("Finca",    key="finca")
        fecha    = st.date_input("Fecha",    date.today(), key="fecha")
        producto = st.text_input("Producto", key="producto")
        auditor  = st.text_input("Nombre Auditor", key="auditor")
    with col2:
        po         = st.text_input("PO", key="po")
        ramos_proc = st.number_input("Ramos Procesados",          min_value=0, step=1, key="ramos_proc")
        ramos_eval = st.number_input("Ramos Evaluados (Muestra)", min_value=1, step=1, key="ramos_eval")
        porc_m = (ramos_eval/ramos_proc*100) if ramos_proc > 0 else 0
        color_m = VERDE if porc_m >= 10 else ROJO
        st.markdown(f"""<div style="background:#f5f5f5;border:1px solid #ccc;border-radius:4px;
                        padding:8px 12px;margin-top:4px;">
            <span style="font-size:.8rem;color:#555;">% Muestra sobre procesado:</span><br>
            <span style="font-size:1.3rem;font-weight:bold;color:{color_m};">{porc_m:.1f}%</span>
            <span style="font-size:.75rem;color:#888;">&nbsp;({int(ramos_eval)} de {int(ramos_proc)} ramos)</span>
            </div>""", unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="section-title">✅ CRITERIO ESTÁNDAR PRODUCTO</div>', unsafe_allow_html=True)
    h1,h2,h3,h4 = st.columns([2,1.2,1.5,2.5])
    with h1: st.caption("**Criterio**")
    with h2: st.caption("**Estado**")
    with h3: st.caption("**Cant. NC**")
    with h4: st.caption("**Observación**")

    prod_data = {}
    for i, c in enumerate(CRITERIOS_PROD):
        prod_data[c] = criterio_row(c, f"prod_{i}", ramos_eval); st.divider()

    st.markdown('<div class="section-title">📦 CRITERIO ESTÁNDAR MATERIALES</div>', unsafe_allow_html=True)
    h1,h2,h3,h4 = st.columns([2,1.2,1.5,2.5])
    with h1: st.caption("**Criterio**")
    with h2: st.caption("**Estado**")
    with h3: st.caption("**Cant. NC**")
    with h4: st.caption("**Observación**")

    mat_data = {}
    for i, c in enumerate(CRITERIOS_MAT):
        mat_data[c] = criterio_row(c, f"mat_{i}", ramos_eval); st.divider()

    st.markdown('<div class="section-title">📊 CÁLCULOS DE CALIDAD</div>', unsafe_allow_html=True)
    total_fallas = sum(v["qty"] for v in prod_data.values()) + sum(v["qty"] for v in mat_data.values())
    porc_nc = (total_fallas/ramos_eval*100) if ramos_eval > 0 else 0
    porc_c  = 100 - porc_nc
    st.markdown(f"""<div class="calc-box">
        <div class="calc-row"><span>Total Ramos con Fallas:</span><span class="nc">{total_fallas}</span></div>
        <hr>
        <div class="calc-row"><span>% No Conforme:</span><span class="nc">{porc_nc:.2f}%</span></div>
        <div class="calc-row"><span>% Conforme:</span><span class="c">{porc_c:.2f}%</span></div>
        </div>""", unsafe_allow_html=True)
    st.divider()

    obs_gen       = st.text_area("Observaciones Generales", key="obs_gen")
    firma_auditor = st.text_input("Firma Auditor",          key="firma_auditor")
    firma_resp    = st.text_input("Firma Responsable",      key="firma_resp")

    if st.button("💾 GUARDAR CHECKLIST", type="primary", use_container_width=True):
        record = {
            "timestamp": datetime.now().isoformat(),
            "fecha": str(fecha), "finca": finca, "producto": producto, "po": po,
            "ramos_proc": int(ramos_proc), "ramos_eval": int(ramos_eval),
            "porc_muestra": round(porc_m, 2), "auditor": auditor,
            "prod_data": prod_data, "mat_data": mat_data,
            "total_fallas": total_fallas,
            "porc_nc": round(porc_nc,2), "porc_c": round(porc_c,2),
            "obs_generales": obs_gen, "firma_auditor": firma_auditor, "firma_resp": firma_resp,
        }
        try:
            save_to_sheets(record)
            st.session_state["ultimo_record"] = record
            st.success("✅ Guardado en Google Sheets correctamente.")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")


# ═══════════════════════════════════════════
# 📈  HISTORIAL + PDF
# ═══════════════════════════════════════════
def render_dashboard():
    st.markdown('<div class="section-title">📈 HISTORIAL Y GENERACIÓN DE PDF</div>',
                unsafe_allow_html=True)

    # PDF del último checklist guardado
    if "ultimo_record" in st.session_state:
        st.info("📄 Último checklist guardado listo para exportar:")
        if st.button("📥 Generar PDF del último checklist"):
            with st.spinner("Generando PDF…"):
                pdf_bytes = generar_pdf(st.session_state["ultimo_record"])
            nombre = (f"QA_{st.session_state['ultimo_record']['finca']}_"
                      f"{st.session_state['ultimo_record']['fecha']}.pdf").replace(" ","_")
            st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                               file_name=nombre, mime="application/pdf",
                               use_container_width=True)
    st.markdown("---")

    # PDF por rango de fechas
    st.subheader("📅 Generar PDF por rango de fechas")
    col_f1, col_f2 = st.columns(2)
    with col_f1: fecha_ini = st.date_input("Fecha inicio", key="fi")
    with col_f2: fecha_fin = st.date_input("Fecha fin",    key="ff")

    if st.button("🔍 Buscar registros del periodo"):
        with st.spinner("Cargando datos de Google Sheets…"):
            try:
                df = load_from_sheets()
            except Exception as e:
                st.error(f"Error al leer Sheets: {e}"); return

        if df.empty:
            st.info("No hay registros aún."); return

        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
        mask = (df["fecha_dt"].dt.date >= fecha_ini) & (df["fecha_dt"].dt.date <= fecha_fin)
        df_r = df[mask]

        if df_r.empty:
            st.warning("No hay registros en ese rango."); return

        st.success(f"**{len(df_r)}** registros entre {fecha_ini} y {fecha_fin}.")
        st.dataframe(df_r[["fecha","finca","auditor","ramos_eval",
                            "total_fallas","porc_c","porc_nc"]],
                     use_container_width=True)
        st.session_state["df_periodo"] = df_r

    if "df_periodo" in st.session_state and st.button("📄 Generar PDF consolidado del periodo"):
        df_r = st.session_state["df_periodo"]
        records = []
        for _, row in df_r.iterrows():
            prod_d = {c: {"status": row.get(f"prod_{c}_status","C"),
                          "qty":    int(row.get(f"prod_{c}_qty",0) or 0),
                          "obs":    row.get(f"prod_{c}_obs","") or ""}
                      for c in CRITERIOS_PROD}
            mat_d  = {c: {"status": row.get(f"mat_{c}_status","C"),
                          "qty":    int(row.get(f"mat_{c}_qty",0) or 0),
                          "obs":    row.get(f"mat_{c}_obs","") or ""}
                      for c in CRITERIOS_MAT}
            records.append({
                "timestamp": row.get("timestamp",""),
                "fecha":     row.get("fecha",""),
                "finca":     row.get("finca",""),
                "producto":  row.get("producto",""),
                "po":        row.get("po",""),
                "ramos_proc": int(row.get("ramos_proc",0) or 0),
                "ramos_eval": int(row.get("ramos_eval",1) or 1),
                "porc_muestra": float(row.get("porc_muestra",0) or 0),
                "auditor":   row.get("auditor",""),
                "prod_data": prod_d, "mat_data": mat_d,
                "total_fallas": int(row.get("total_fallas",0) or 0),
                "porc_nc": float(row.get("porc_nc",0) or 0),
                "porc_c":  float(row.get("porc_c",100) or 100),
                "obs_generales": row.get("obs_generales","") or "",
                "firma_auditor": row.get("firma_auditor","") or "",
                "firma_resp":    row.get("firma_resp","") or "",
            })

        with st.spinner("Generando PDF del periodo…"):
            from pypdf import PdfWriter, PdfReader
            writer = PdfWriter()
            for rec in records:
                reader = PdfReader(io.BytesIO(generar_pdf(rec)))
                for page in reader.pages:
                    writer.add_page(page)
            out = io.BytesIO(); writer.write(out); pdf_final = out.getvalue()

        nombre_p = f"QA_Periodo_{fecha_ini}_{fecha_fin}.pdf".replace(" ","_")
        st.download_button("⬇️ Descargar PDF del periodo", data=pdf_final,
                           file_name=nombre_p, mime="application/pdf",
                           use_container_width=True)


# ═══════════════════════════════════════════
# 🚀  MAIN
# ═══════════════════════════════════════════
def main():
    render_header()
    tab1, tab2 = st.tabs(["📝 Nuevo Checklist", "📊 Historial & PDF"])
    with tab1:
        render_form()
    with tab2:
        render_dashboard()

if __name__ == "__main__":
    main()
