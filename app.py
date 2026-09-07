import json
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

# Asegurar tipo numérico en importes
if not df_fijos.empty and "Importe" in df_fijos.columns:
    df_fijos["Importe"] = pd.to_numeric(df_fijos["Importe"].astype(str).str.replace(",", ".").str.replace("'", ""), errors="coerce").fillna(0.0)

if not df_movs.empty and "Importe" in df_movs.columns:
    df_movs["Importe"] = pd.to_numeric(df_movs["Importe"].astype(str).str.replace(",", ".").str.replace("'", ""), errors="coerce").fillna(0.0)

# Configuración activa del mes
if not df_config.empty:
    mes_actual = str(df_config.iloc[-1]["Mes"])
    nomina = float(str(df_config.iloc[-1]["Nomina"]).replace(",", "."))
    bolsa_inicial = float(str(df_config.iloc[-1]["Bolsa_Mes_Inicial"]).replace(",", "."))
    colchon = float(str(df_config.iloc[-1]["Colchon_Seguridad"]).replace(",", "."))
else:
    mes_actual, nomina, bolsa_inicial, colchon = "Actual", 2050.0, 600.0, 200.0

# Panel lateral para ajustar el Día 1
with st.sidebar:
    st.header("⚙️ Ajustes del Mes")
    with st.form("form_ajustes_mes"):
        nuevo_mes = st.text_input("Mes / Etiqueta", value=mes_actual)
        nueva_nomina = st.number_input("Nómina ingresada (€)", value=nomina, step=50.0, format="%.2f")
        nueva_bolsa = st.number_input("Bolsa para Pasar el Mes (€)", value=bolsa_inicial, step=50.0, format="%.2f")
        nuevo_colchon = st.number_input("Colchón en Cuenta (€)", value=colchon, step=50.0, format="%.2f")
        btn_guardar_config = st.form_submit_button("Guardar Ajustes del Mes")
        
        if btn_guardar_config:
            fila_idx = len(df_config) + 1 if not df_config.empty else 2
            ws_config.update(f"A{fila_idx}:D{fila_idx}", [[nuevo_mes, nueva_nomina, nueva_bolsa, nuevo_colchon]])
            st.success("Configuración actualizada.")
            st.rerun()

# Cálculos
gastos_bolsa = 0.0
if not df_movs.empty and "Impacta_En" in df_movs.columns:
    df_bolsa = df_movs[df_movs["Impacta_En"] == "Bolsa Mes"]
    gastos_bolsa = float(df_bolsa["Importe"].sum())

bolsa_restante = bolsa_inicial - gastos_bolsa

total_fijos = float(df_fijos["Importe"].sum()) if not df_fijos.empty else 0.0
fijos_pendientes = 0.0
if not df_fijos.empty and "Estado" in df_fijos.columns:
    fijos_pendientes = float(df_fijos[df_fijos["Estado"] == "Pendiente"]["Importe"].sum())

ahorro_disponible = nomina - total_fijos - bolsa_inicial

# ================= UI =================
st.title("💳 Panel Financiero")

# Marcadores principales
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
        help="Recibos pendientes de cobro"
    )

with col3:
    st.metric(
        label="🛡️ Colchón en Cuenta",
        value=f"{colchon:.2f} €",
        help="Reserva fijada en cuenta"
    )

with col4:
    st.metric(
        label="💰 Excedente a Ahorro / Fondo",
        value=f"{ahorro_disponible:.2f} €",
        help="Nómina - Fijos Totales - Bolsa del Mes"
    )

st.divider()

col_izq, col_der = st.columns([1, 1])

# Formulario de gasto preparado para comas, puntos y apóstrofes
with col_izq:
    st.subheader("➕ Añadir Gasto Rápido")
    with st.form("form_gasto", clear_on_submit=True):
        concepto = st.text_input("Concepto", placeholder="Mercadona, Gasolina, Cena...")
        importe_txt = st.text_input("Importe (€)", placeholder="Ej: 21,26 o 21.26")
        categoria = st.selectbox("Categoría", ["Alimentación", "Gasolina/Transporte", "Ocio/Restaurante", "Hogar", "Otros"])
        impacto = st.radio("Descontar de:", ["Bolsa Mes", "Ahorro / Colchón"], horizontal=True)
        
        btn_guardar = st.form_submit_button("Registrar Movimiento")
        
        if btn_guardar:
            limpio = importe_txt.replace(",", ".").replace("'", "").strip()
            try:
                importe_val = float(limpio)
                if concepto.strip() and importe_val > 0:
                    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                    ws_movs.append_row([fecha_hoy, concepto.strip(), categoria, f"{importe_val:.2f}", impacto])
                    st.success(f"Guardado: {concepto.strip()} ({importe_val:.2f} €)")
                    st.rerun()
                else:
                    st.warning("Escribe un concepto y un importe mayor a cero.")
            except ValueError:
                st.error("Formato de importe no válido. Usa números como 21.26 o 21,26")

# Gestión de recibos fijos
with col_der:
    st.subheader("📋 Recibos del Mes")
    if not df_fijos.empty:
        with st.form("form_recibos"):
            estados_actualizados = []
            for index, row in df_fijos.iterrows():
                f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
                f_col1.write(f"**{row['Concepto']}**")
                f_col2.write(f"{row['Importe']:.2f} €")
                
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
        st.info("No hay recibos fijos configurados.")

st.divider()

# Historial reciente y eliminación de movimientos
st.subheader("🧾 Últimos Movimientos")

if not df_movs.empty:
    # Desplegable para borrar filas directamente
    with st.expander("🗑️ Eliminar un movimiento erróneo"):
        opciones_borrar = {}
        # Recorremos de más reciente a más antiguo
        for i in reversed(df_movs.index):
            row = df_movs.iloc[i]
            # La fila real en Google Sheets es índice + 2 (por encabezado y base 1)
            num_fila_sheets = i + 2
            etiqueta = f"Fila {num_fila_sheets} | {row['Fecha']} - {row['Concepto']} ({row['Importe']:.2f} €) [{row['Impacta_En']}]"
            opciones_borrar[etiqueta] = num_fila_sheets
        
        eleccion = st.selectbox("Selecciona el movimiento que quieres borrar:", list(opciones_borrar.keys()))
        if st.button("Eliminar movimiento seleccionado", type="primary"):
            fila_a_borrar = opciones_borrar[eleccion]
            ws_movs.delete_rows(fila_a_borrar)
            st.success(f"Movimiento eliminado correctamente.")
            st.rerun()

    # Tabla visual
    df_mostrar = df_movs.copy().iloc[::-1]
    df_mostrar["Importe"] = df_mostrar["Importe"].map(lambda x: f"{x:.2f} €")
    st.dataframe(df_mostrar.head(20), use_container_width=True)
else:
    st.info("Aún no has registrado movimientos este mes.")
