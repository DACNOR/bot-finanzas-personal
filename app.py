import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Control de Finanzas", layout="wide", page_icon="💳")

# Estilo visual tipo App nativa (oculta barras de Streamlit/GitHub)
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

# Conexión con Google Sheets usando Secrets
@st.cache_resource
def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    info = json.loads(st.secrets["gcp_json"])
    credentials = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(credentials)
    sheet = client.open("Finanzas_Control")
    return sheet

try:
    doc = get_google_sheet()
    ws_config = doc.worksheet("Config_Mes")
    ws_fijos = doc.worksheet("Recibos_Fijos")
    ws_movs = doc.worksheet("Movimientos")
except Exception as e:
    st.error(f"Error conectando con Google Sheets: {e}")
    st.stop()

# Cargar datos desde Google Sheets
config_data = ws_config.get_all_records()
fijos_data = ws_fijos.get_all_records()
movs_data = ws_movs.get_all_records()

df_config = pd.DataFrame(config_data)
df_fijos = pd.DataFrame(fijos_data)
df_movs = pd.DataFrame(movs_data)

# Valores actuales de configuración
if not df_config.empty:
    mes_actual = str(df_config.iloc[-1]["Mes"])
    nomina = float(df_config.iloc[-1]["Nomina"])
    bolsa_inicial = float(df_config.iloc[-1]["Bolsa_Mes_Inicial"])
    colchon = float(df_config.iloc[-1]["Colchon_Seguridad"])
else:
    mes_actual, nomina, bolsa_inicial, colchon = "Actual", 2050.0, 600.0, 200.0

# ================= ENCABEZADO Y CONTROLES PRINCIPALES =================
st.title("💳 Panel Financiero")

# Ajustes integrados directamente en pantalla (sin barra lateral traicionera)
with st.expander("⚙️ AJUSTAR MES (Nómina, Bolsa y Colchón)", expanded=False):
    with st.form("form_ajustes_mes"):
        c1, c2, c3, c4 = st.columns(4)
        nuevo_mes = c1.text_input("Mes", value=mes_actual)
        nueva_nomina = c2.number_input("Nómina ingresada (€)", value=nomina, step=50.0, format="%.2f")
        nueva_bolsa = c3.number_input("Bolsa Pasar Mes (€)", value=bolsa_inicial, step=50.0, format="%.2f")
        nuevo_colchon = c4.number_input("Colchón en Cuenta (€)", value=colchon, step=50.0, format="%.2f")
        
        btn_guardar_config = st.form_submit_button("Guardar Cambios del Mes")
        if btn_guardar_config:
            fila_idx = len(df_config) + 1 if not df_config.empty else 2
            ws_config.update(f"A{fila_idx}:D{fila_idx}", [[nuevo_mes, nueva_nomina, nueva_bolsa, nuevo_colchon]])
            st.success("Ajustes actualizados.")
            st.rerun()

# Cálculos de gastos variables
gastos_bolsa = 0.0
if not df_movs.empty and "Impacta_En" in df_movs.columns:
    df_bolsa = df_movs[df_movs["Impacta_En"] == "Bolsa Mes"]
    gastos_bolsa = float(df_bolsa["Importe"].sum())

bolsa_restante = bolsa_inicial - gastos_bolsa

# Cálculos de fijos
total_fijos = float(df_fijos["Importe"].sum()) if not df_fijos.empty else 0.0
fijos_pendientes = 0.0
if not df_fijos.empty and "Estado" in df_fijos.columns:
    fijos_pendientes = float(df_fijos[df_fijos["Estado"] == "Pendiente"]["Importe"].sum())

# Excedente a Ahorro
ahorro_disponible = nomina - total_fijos - bolsa_inicial

# ================= MÉTRICAS CLAVE =================
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(
        label="🔥 Bolsa para Pasar el Mes",
        value=f"{bolsa_restante:.2f} €",
        delta=f"-{gastos_bolsa:.2f} € gastados",
        delta_color="inverse"
    )

with m2:
    st.metric(
        label="⏳ Fijos por Cobrar",
        value=f"{fijos_pendientes:.2f} €",
        help="Recibos pendientes de cargo en cuenta"
    )

with m3:
    st.metric(
        label="🛡️ Colchón en Cuenta",
        value=f"{colchon:.2f} €",
        help="Reserva fija en la cuenta corriente"
    )

with m4:
    st.metric(
        label="💰 Excedente a Ahorro / Fondo",
        value=f"{ahorro_disponible:.2f} €",
        help="Nómina - Fijos Totales - Bolsa del Mes"
    )

st.divider()

# ================= OPERATIVA: REGISTRO Y RECIBOS =================
col_izq, col_der = st.columns([1, 1])

# Formulario para registrar compras al vuelo
with col_izq:
    st.subheader("➕ Añadir Gasto Rápido")
    with st.form("form_gasto", clear_on_submit=True):
        concepto = st.text_input("Concepto", placeholder="Mercadona, Gasolina, Cine...")
        importe = st.number_input("Importe (€)", min_value=0.01, step=1.0, format="%.2f")
        categoria = st.selectbox("Categoría", ["Alimentación", "Gasolina/Transporte", "Ocio/Restaurante", "Hogar", "Otros"])
        impacto = st.radio("Descontar de:", ["Bolsa Mes", "Ahorro / Colchón"], horizontal=True)
        
        btn_guardar = st.form_submit_button("Registrar Movimiento")
        if btn_guardar:
            if concepto and importe > 0:
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                ws_movs.append_row([fecha_hoy, concepto, categoria, importe, impacto])
                st.success(f"Guardado: {concepto} ({importe:.2f} €)")
                st.rerun()
            else:
                st.warning("Completa el concepto y el importe.")

# Checklist de fijos con guardado seguro por lote
with col_der:
    st.subheader("📋 Recibos del Mes")
    if not df_fijos.empty:
        with st.form("form_recibos"):
            estados_actualizados = []
            for index, row in df_fijos.iterrows():
                f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
                f_col1.write(f"**{row['Concepto']}**")
                f_col2.write(f"{row['Importe']} €")
                
                estado_actual = row['Estado'] == "Cobrado"
                marcado = f_col3.checkbox("Cobrado", value=estado_actual, key=f"fijo_chk_{index}")
                estados_actualizados.append("Cobrado" if marcado else "Pendiente")
            
            btn_guardar_recibos = st.form_submit_button("Actualizar Estados de Recibos")
            if btn_guardar_recibos:
                celdas = [[e] for e in estados_actualizados]
                ws_fijos.update(f"C2:C{len(estados_actualizados) + 1}", celdas)
                st.success("Recibos actualizados.")
                st.rerun()
    else:
        st.info("No hay recibos configurados.")

st.divider()

# Historial reciente
st.subheader("🧾 Últimos Movimientos")
if not df_movs.empty:
    st.dataframe(df_movs.iloc[::-1].head(15), use_container_width=True)
else:
    st.info("Aún no has registrado movimientos este mes.")
