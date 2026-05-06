import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from supabase import create_client

st.set_page_config(page_title="Simulador Híbrido SAE", layout="wide")

# 1. CONEXÃO E BUSCA DE DADOS
try:
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    supabase = create_client(url, key)
    response = supabase.table("combustiveis").select("*").execute()
    df_db = pd.DataFrame(response.data)
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# 2. SIDEBAR - AJUSTES SUGERIDOS
st.sidebar.header("⚙️ Calibração Técnica")
nome_sel = st.sidebar.selectbox("Combustível", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_sel].iloc[0]

st.sidebar.markdown("---")

# Ajuste 1: Nome amigável e passos definidos
mistura = st.sidebar.slider(
    "Relação Ar-Combustível (Mistura)", 
    min_value=1.0, max_value=45.0, 
    value=float(fuel['afr_estoic']), 
    step=0.5
)

# Ajuste 2: Range de avanço dinâmico (Simulando limites de segurança)
limite_avanco = 45 if fuel['nome'] in ['Etanol', 'Nitrometano'] else 35
avanco = st.sidebar.slider(
    "Avanço de Ignição (°BTDC)", 
    5, limite_avanco, 
    int(fuel['avanco_base'])
)

pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# 3. LÓGICA DA CURVA DE POTÊNCIA (Ajuste 3)
rpm = np.linspace(1000, 7000, 50)
alvo_afr = float(fuel['afr_estoic']) * 0.9 # Alvo para potência máxima
erro_ajuste = (abs(mistura - alvo_afr) * 0.1) + (abs(avanco - fuel['avanco_base']) * 0.05)

# Modelo simplificado de torque (Parábola de eficiência volumétrica)
torque_base = float(fuel['pot_max']) * 0.85
curva_torque = torque_base * (1 - ((rpm - 4500)**2 / 20000000)) * (1 - erro_ajuste)
curva_potencia_ice = (curva_torque * rpm) / 716.2
curva_potencia_total = curva_potencia_ice + pot_eletrica

# 4. DASHBOARD VISUAL
st.title("⚡ Otimização de Powertrain Híbrido - SAE")

col1, col2 = st.columns([1, 2])

with col1:
    st.metric("Pico de Potência Total", f"{max(curva_potencia_total):.1f} cv")
    st.metric("Eficiência de Combustão", f"{max(100*(1-erro_ajuste), 0):.1f}%")
    if erro_ajuste > 0.4:
        st.warning("⚠️ Risco de Pré-Ignição ou Perda de Torque Significativa.")

with col2:
    # Gráfico de Curva de Potência e Torque
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rpm, y=curva_potencia_ice, name="Potência ICE (Combustão)", line=dict(color='orange', dash='dash')))
    fig.add_trace(go.Scatter(x=rpm, y=curva_potencia_total, name="Potência Combinada (Híbrida)", line=dict(color='cyan', width=4)))
    
    fig.update_layout(
        title=f"Curva de Performance: {nome_sel}",
        xaxis_title="Rotação (RPM)",
        yaxis_title="Potência (cv)",
        template="plotly_dark",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    st.plotly_chart(fig, use_container_width=True)

st.info("Nota Técnica: O gráfico acima simula a integração dinâmica entre o motor elétrico e a combustão baseada no seu ajuste de mistura e avanço.")
