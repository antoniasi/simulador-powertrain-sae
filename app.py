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

# 2. INTERFACE (Sugestões Aplicadas)
st.sidebar.header("⚙️ Calibração Técnica")
nome_sel = st.sidebar.selectbox("Combustível", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_sel].iloc[0]

st.sidebar.markdown("---")

# Ajuste 1: Termo simples e escalas definidas (passo de 5 em 5 visualmente no slider)
mistura = st.sidebar.slider(
    "Relação Ar-Combustível (Mistura)", 
    min_value=1.0, max_value=40.0, 
    value=float(fuel['afr_estoic']), 
    step=0.5,
    help="Ajuste a massa de ar em relação à massa de combustível."
)

# Ajuste 2: Range de avanço definido por tipo de combustível
# Nitrometano e Etanol permitem mais avanço que Gasolina
max_avanco_perm = 45 if fuel['nome'] in ['Etanol', 'Nitrometano'] else 35
avanco = st.sidebar.slider(
    "Avanço de Ignição (°BTDC)", 
    5, max_avanco_perm, 
    int(fuel['avanco_base'])
)

pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# 3. LÓGICA DE CURVA (Ajuste 3: Potência e Torque por RPM)
rpm = np.linspace(1000, 7000, 100)
# Alvo de potência máxima costuma ser 10-15% mais rico que a estequiometria
alvo_afr = float(fuel['afr_estoic']) * 0.9 

# Cálculo de erro (quanto mais longe do alvo, menor a eficiência)
erro_mistura = abs(mistura - alvo_afr) * 0.15
erro_avanco = abs(avanco - fuel['avanco_base']) * 0.05
eficiencia_total = max(0, 1 - (erro_mistura + erro_avanco))

# Simulação de curva de torque (Parábola) e conversão para Potência
# Potência (cv) = (Torque * RPM) / 716.2
torque_max = float(fuel['pot_max']) * 0.8
torque_curva = torque_max * (1 - ((rpm - 4500)**2 / 20000000)) * eficiencia_total
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
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)
