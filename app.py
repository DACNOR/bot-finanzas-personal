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

def limpiar_cifra(valor):
    if pd.isna(valor) or valor == "":
        return 0.0
    v = str(valor).replace("€", "").replace("'", "").strip()
    if "," in v and "." not in v:
        v = v.replace(",", ".")
    elif "." in v and "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except:
        return 0.0

# Lectura de datos
config_data = ws_config.get_all_records(numericise_ignore=['all'])
fijos_data = ws_fijos.get_all_records(numericise_ignore=['all'])
movs_data = ws_movs.get_all_records(numericise_ignore=['all'])

df_config = pd.DataFrame(config_data)
df_fijos = pd.DataFrame(fijos_data)
df_movs = pd.DataFrame(movs_data)

if not df_fijos.empty and "Importe" in df_fijos.columns:
    df_fijos["Importe"] = df_fijos["Importe"].apply(limpiar_cifra)

if not df_movs.empty and "Importe" in df_movs.columns:
    df_movs["Importe"] = df_movs["Importe"].apply(limpiar_cifra)

# Configuración actual
if not df_config.empty:
    mes_actual = str(df_config.iloc[-1]["Mes"])
    nomina = limpiar_cifra(df_config.iloc[-1]["Nomina"])
    bolsa_inicial = limpiar_cifra(df_config.iloc[-1]["Bolsa_Mes_Inicial"])
    colchon = limpiar_cifra(df_config.iloc[-1]["Colchon_Seguridad"])
else:
    mes_actual, nomina, bolsa_inicial, colchon = "09-2026", 1969.0, 544.11, 2152.0

# Cálculos de bolsa
gastos_bolsa = 0.0
if not df_movs.empty and "Impacta_En" in df_movs.columns:
    df_bolsa = df_movs[df_movs["Impacta_En"] == "Bolsa Mes"]
    gastos_bolsa = float(df_bolsa["Importe"].sum())

bolsa_restante = bolsa_inicial - gastos_bolsa

# Cálculos de recibos pendientes
fijos_pendientes = 0.0
if not df_fijos.empty and "Estado" in df_fijos.columns:
    fijos_pendientes = float(df_fijos[df_fijos["Estado"] == "Pendiente"]["Importe"].sum())

# SALDO REAL TOTAL EN CUENTA
saldo_total_banco = colchon + bolsa_restante + fijos_pendientes

# ================= UI =================
st.title("💳 Panel Financiero")

# Desplegable del Día 1: Justo después del título y antes de las tarjetas
with st.expander("⚙️ Modificar Ajustes del Mes (Nómina, Bolsa Inicial, Ahorro)"):
    with st.form("form_ajustes_mes"):
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        nuevo_mes = c_m1.text_input("Mes / Etiqueta", value=mes_actual)
        nueva_nomina = c_m2.number_input("Nómina ingresada (€)", value=nomina, step=10.0, format="%.2f")
        nueva_bolsa = c_m3.number_input("Bolsa Inicial Mes (€)", value=bolsa_inicial, step=10.0, format="%.2f")
        nuevo_colchon = c_m4.number_input("Ahorro / Colchón (€)", value=colchon, step=10.0, format="%.2f")
        
        btn_guardar_config = st.form_submit_button("Guardar Nuevos Ajustes")
        if btn_guardar_config:
            fila_idx = len(df_config) + 1 if not df_config.empty else 2
            ws_config.update(f"A{fila_idx}:D{fila_idx}", [[nuevo_mes, str(nueva_nomina), str(nueva_bolsa), str(nuevo_colchon)]])
            st.success("Ajustes guardados correctamente.")
            st.rerun()

# Marcadores principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🔥 Bolsa Pasar Mes (Disponible)",
        value=f"{bolsa_restante:.2f} €",
        delta=f"-{gastos_bolsa:.2f} € gastados",
        delta_color="inverse"
    )

with col2:
    st.metric(
        label="⏳ Recibos/Apartados Pendientes",
        value=f"{fijos_pendientes:.2f} €",
        help="Jazztel + Gas + Mudanza (lo que falta por salir)"
    )

with col3:
    st.metric(
        label="🛡️ Ahorro / Colchón",
        value=f"{colchon:.2f} €",
        help="Tu reserva acumulada"
    )

with col4:
    st.metric(
        label="🏦 Total en Cuenta (Banco)",
        value=f"{saldo_total_banco:.2f} €",
        help="Ahorro + Bolsa Disponible + Pendientes por salir"
    )

st.divider()

col_izq, col_der = st.columns([1, 1])

# Registrar gasto
with col_izq:
    st.subheader("➕ Añadir Gasto Rápido")
    with st.form("form_gasto", clear_on_submit=True):
        concepto = st.text_input("Concepto", placeholder="Mercadona, Gasolina, Cine...")
        importe_txt = st.text_input("Importe (€)", placeholder="Ej: 21,26 o 21.26")
        categoria = st.selectbox("Categoría", ["Alimentación", "Gasolina/Transporte", "Ocio/Restaurante", "Hogar", "Otros"])
        impacto = st.radio("Descontar de:", ["Bolsa Mes", "Ahorro / Colchón"], horizontal=True)
        
        btn_guardar = st.form_submit_button("Registrar Movimiento")
        
        if btn_guardar:
            val = limpiar_cifra(importe_txt)
            if concepto.strip() and val > 0:
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                ws_movs.append_row([fecha_hoy, concepto.strip(), categoria, f"{val:.2f}", impacto])
                st.success(f"Guardado: {concepto.strip()} ({val:.2f} €)")
                st.rerun()
            else:
                st.warning("Indica un concepto y un importe válido.")

# Recibos y apartados
with col_der:
    st.subheader("📋 Recibos y Apartados del Mes")
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
            
            btn_guardar_recibos = st.form_submit_button("Actualizar Estados")
            if btn_guardar_recibos:
                celdas = [[e] for e in estados_actualizados]
                ws_fijos.update(f"C2:C{len(estados_actualizados) + 1}", celdas)
                st.success("Estados actualizados.")
                st.rerun()
    else:
        st.info("No hay recibos configurados.")

st.divider()

# Historial y borrado
st.subheader("🧾 Últimos Movimientos")

if not df_movs.empty:
    with st.expander("🗑️ Eliminar un movimiento"):
        opciones_borrar = {}
        for i in reversed(df_movs.index):
            row = df_movs.iloc[i]
            num_fila_sheets = i + 2
            etiqueta = f"Fila {num_fila_sheets} | {row['Fecha']} - {row['Concepto']} ({row['Importe']:.2f} €) [{row['Impacta_En']}]"
            opciones_borrar[etiqueta] = num_fila_sheets
        
        eleccion = st.selectbox("Selecciona para borrar:", list(opciones_borrar.keys()))
        if st.button("Eliminar seleccionado", type="primary"):
            fila_a_borrar = opciones_borrar[eleccion]
            ws_movs.delete_rows(fila_a_borrar)
            st.success("Movimiento eliminado.")
            st.rerun()

    df_mostrar = df_movs.copy().iloc[::-1]
    df_mostrar["Importe"] = df_mostrar["Importe"].map(lambda x: f"{x:.2f} €")
    st.dataframe(df_mostrar.head(20), use_container_width=True)
else:
    st.info("Aún no has registrado movimientos este mes.")
