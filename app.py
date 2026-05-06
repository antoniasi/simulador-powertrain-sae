import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from supabase import create_client

st.set_page_config(page_title="Simulador SAE", layout="wide")

# 1. CONEXÃO
try:
    url = st.secrets["url"]
    key = st.secrets["key"]
    supabase = create_client(url, key)
    response = supabase.table("combustiveis").select("*").execute()
    df_db = pd.DataFrame(response.data)
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# 2. INTERFACE DINÂMICA
st.sidebar.header("⚙️ Calibração Técnica")
nome_sel = st.sidebar.selectbox("Combustível", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_sel].iloc[0]

st.sidebar.markdown("---")

# Ajuste 1: Mistura com limites vindos do banco
mistura = st.sidebar.slider(
    "Relação Ar-Combustível (Mistura)", 
    min_value=float(fuel['afr_min']), 
    max_value=float(fuel['afr_max']), 
    value=float(fuel['afr_estoic']), 
    step=0.5
)

# Ajuste 2: Avanço com limite dinâmico (avanco_max) vindo do banco
avanco = st.sidebar.slider(
    "Avanço de Ignição (°BTDC)", 
    5.0, 
    float(fuel['avanco_max']), 
    float(fuel['avanco_base']),
    step=1.0
)

pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# 3. LÓGICA DE CURVA (Usando dados de RPM e Pico do banco)
# Criamos o eixo X baseado no rpm_max do combustível selecionado
rpm_limite = int(fuel['rpm_max'])
rpm = np.linspace(1000, rpm_limite, 100)

# Alvo de potência máxima (10% mais rico)
alvo_afr = float(fuel['afr_estoic']) * 0.9 

# Cálculo de eficiência baseado no desvio dos sliders
erro_mistura = abs(mistura - alvo_afr) * 0.15
erro_avanco = abs(avanco - fuel['avanco_base']) * 0.05
eficiencia_total = max(0, 1 - (erro_mistura + erro_avanco))

# Simulação de curva de torque usando o rpm_pico_torque do banco
pico_torque_rpm = int(fuel['rpm_pico_torque'])
torque_max = float(fuel['pot_max']) * 0.8

# A parábola agora centraliza no pico de torque definido no Supabase
torque_curva = torque_max * (1 - ((rpm - pico_torque_rpm)**2 / (rpm_limite**2 / 2))) * eficiencia_total
pot_ice = (torque_curva * rpm) / 716.2
pot_total = pot_ice + pot_eletrica

# 4. DASHBOARD
st.title("⚡ Otimização de Powertrain Híbrido - SAE")

col1, col2 = st.columns([1, 2])
with col1:
    st.metric("Pico de Potência Combinada", f"{max(pot_total):.1f} cv")
    st.metric("Eficiência de Combustão", f"{eficiencia_total*100:.1f}%")
    
    if eficiencia_total < 0.5:
        st.error("⚠️ Calibração Crítica: Risco de quebra ou falta de ignição.")

with col2:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rpm, y=pot_ice, name="Motor a Combustão (ICE)", line=dict(color='orange', dash='dot')))
    fig.add_trace(go.Scatter(x=rpm, y=pot_total, name="Conjunto Híbrido (Total)", line=dict(color='#00d4ff', width=4)))
    
    fig.update_layout(
        template="plotly_dark",
        xaxis_title="Rotação (RPM)",
        yaxis_title="Potência (cv)",
        hovermode="x unified",
        title=f"Curva de Performance: {nome_sel}"
    )
    st.plotly_chart(fig, use_container_width=True)
