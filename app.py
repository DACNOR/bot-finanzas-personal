import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Control de Finanzas", layout="wide", page_icon="💳")

# Conexión con Google Sheets usando Secrets
@st.cache_resource
def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(credentials)
    # Abre la hoja por nombre exacto
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

# Cargar datos
config_data = ws_config.get_all_records()
fijos_data = ws_fijos.get_all_records()
movs_data = ws_movs.get_all_records()

df_config = pd.DataFrame(config_data)
df_fijos = pd.DataFrame(fijos_data)
df_movs = pd.DataFrame(movs_data)

# Valores base
if not df_config.empty:
    nomina = float(df_config.iloc[-1]["Nomina"])
    bolsa_inicial = float(df_config.iloc[-1]["Bolsa_Mes_Inicial"])
    colchon = float(df_config.iloc[-1]["Colchon_Seguridad"])
else:
    nomina, bolsa_inicial, colchon = 2000.0, 600.0, 200.0

# Cálculos de gastos
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

# Excedente teórico para Ahorro / Colchón
ahorro_disponible = nomina - total_fijos - bolsa_inicial

# ================= UI =================
st.title("💳 Panel Financiero")

# Fila de métricas estilo bloc de notas
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🔥 Bolsa para Pasar el Mes",
        value=f"{bolsa_restante:.2f} €",
        delta=f"-{gastos_bolsa:.2f} € gastados",
        delta_color="inverse"
    )

with col2:
    st.metric(
        label="⏳ Fijos por Cobrar",
        value=f"{fijos_pendientes:.2f} €",
        help="Suma de recibos que aún figuran como pendientes"
    )

with col3:
    st.metric(
        label="🛡️ Colchón en Cuenta",
        value=f"{colchon:.2f} €",
        help="Reserva intocable mínima de seguridad"
    )

with col4:
    st.metric(
        label="💰 Excedente a Ahorro / Fondo",
        value=f"{ahorro_disponible:.2f} €",
        help="Nómina menos fijos totales y bolsa mensual"
    )

st.divider()

# Dos columnas: Meter Gasto vs Recibos Fijos
col_izq, col_der = st.columns([1, 1])

with col_izq:
    st.subheader("➕ Añadir Gasto Rápido")
    with st.form("form_gasto", clear_on_submit=True):
        concepto = st.text_input("Concepto", placeholder="Mercadona, Gasolina, Cine...")
        importe = st.number_input("Importe (€)", min_value=0.01, step=1.0, format="%.2f")
        categoria = st.selectbox("Categoría", ["Alimentación", "Gasolina/Transporte", "Ocio/Restaurante", "Casa", "Otros"])
        impacto = st.radio("Descontar de:", ["Bolsa Mes", "Ahorro / Colchón"], horizontal=True)
        
        btn_guardar = st.form_submit_button("Registrar Movimiento")
        
        if btn_guardar:
            if concepto and importe > 0:
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                ws_movs.append_row([fecha_hoy, concepto, categoria, importe, impacto])
                st.success(f"Guardado: {concepto} por {importe:.2f} €")
                st.rerun()
            else:
                st.warning("Completa el concepto y un importe válido.")

with col_der:
    st.subheader("📋 Recibos del Mes (Tachar al cobrar)")
    if not df_fijos.empty:
        for index, row in df_fijos.iterrows():
            f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
            f_col1.write(f"**{row['Concepto']}**")
            f_col2.write(f"{row['Importe']} €")
            
            estado_actual = row['Estado'] == "Cobrado"
            nuevo_estado = f_col3.checkbox("Cobrado", value=estado_actual, key=f"fijo_{index}")
            
            # Si el usuario cambia el checkbox, actualiza Google Sheets
            if nuevo_estado != estado_actual:
                estado_str = "Cobrado" if nuevo_estado else "Pendiente"
                ws_fijos.update_cell(index + 2, 3, estado_str)
                st.rerun()
    else:
        st.info("No hay recibos fijos configurados.")

st.divider()

# Historial reciente de compras
st.subheader("🧾 Últimos Movimientos")
if not df_movs.empty:
    st.dataframe(df_movs.iloc[::-1].head(15), use_container_width=True)
else:
    st.info("Aún no has registrado movimientos este mes.")
