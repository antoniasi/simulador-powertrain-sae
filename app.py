import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from supabase import create_client

st.set_page_config(page_title="Simulador SAE Powertrain v3.0", layout="wide")

# ==========================================
# 1. CONEXÃO E LEITURA DE DADOS
# ==========================================
try:
    url = st.secrets["url"]
    key = st.secrets["key"]
    supabase = create_client(url, key)
    
    # Leitura das tabelas
    df_db = pd.DataFrame(supabase.table("combustiveis").select("*").execute().data)
    df_motor = pd.DataFrame(supabase.table("parametros_motor").select("*").execute().data)
    motor = df_motor.iloc[0] # Pega os dados do motor (ex: V8 4.0L)
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.stop()

# ==========================================
# 2. SIDEBAR (CONTROLES)
# ==========================================
st.sidebar.header("⚙️ Calibração Técnica")
nome_sel = st.sidebar.selectbox("Combustível Selecionado", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_sel].iloc[0]

# Sliders dinâmicos
mistura = st.sidebar.slider("Sinal Sensor AFR (mA) *(-Rico / +Pobre)*", 
                            min_value=float(min(-5.0, fuel['afr_min'])), 
                            max_value=float(fuel['afr_max']), 
                            value=float(fuel['afr_estoic']), step=0.1)

avanco = st.sidebar.slider("Avanço de Ignição (°BTDC)", -15.0, float(fuel['avanco_max']), float(fuel['avanco_base']), 1.0)
pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# ==========================================
# 3. LÓGICA DE CURVA (FÍSICA DA PLANILHA)
# ==========================================
rpm = np.linspace(1000, int(fuel['rpm_max']), 100)

# Fluxo de Ar (Físico)
vol_aspirado = (rpm / 60.0) * (float(motor['cilindrada_litros']) / 1000.0) * 0.5
massa_ar = vol_aspirado * float(motor['densidade_ar']) * float(motor['eficiencia_volumetrica'])

# Fluxo Combustível
afr_real = abs(mistura) if mistura != 0 else 0.1
massa_comb = massa_ar / afr_real

# Energia Bruta (MW)
energia_bruta = massa_comb * float(fuel['densidade_energetica'])

# Regras de Eficiência (Ciclos)
if fuel['tipo_motor'] == 'Diesel':
    eta = 0.40
elif fuel['tipo_motor'] == 'Pobre':
    eta = 0.35
else:
    eta = float(motor['rendimento_otto_base']) + (avanco * 0.001)
    # Penalidade por desvio de mistura
    eta -= (abs(afr_real - float(fuel['afr_estoic'])) * 0.015)

eta = np.clip(eta, 0.05, 0.60)

# Potência
pot_ice = energia_bruta * eta * 1359.62
pico_torque_rpm = int(fuel['rpm_pico_torque'])
curva_queda = 1 - (((rpm - pico_torque_rpm) / int(fuel['rpm_max'])) ** 2)
pot_ice = pot_ice * np.clip(curva_queda, 0.5, 1.0)
pot_total = pot_ice + pot_eletrica

# ==========================================
# 4. DASHBOARD
# ==========================================
st.title(f"🚀 Otimização Powertrain: {nome_sel}")
col1, col2, col3 = st.columns(3)
col1.metric("Pico ICE", f"{max(pot_ice):.1f} cv")
col2.metric("Pico Combinado", f"{max(pot_total):.1f} cv")
col3.metric("Eficiência Térmica", f"{np.mean(eta)*100:.1f}%")

tabs = st.tabs(["📈 Curva de Potência", "🔥 Mapa de Calor", "🕸️ Comparativo"])

with tabs[0]: # Curva de Potência
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rpm, y=pot_ice, name="Motor (ICE)", line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=rpm, y=pot_total, name="Híbrido (Total)", line=dict(color='#00d4ff', width=4)))
    fig.update_layout(template="plotly_dark", title="Dinâmica de Potência")
    st.plotly_chart(fig, use_container_width=True)

with tabs[1]: # Mapa de Calor
    afr_range = np.linspace(float(min(-5.0, fuel['afr_min'])), float(fuel['afr_max']), 30)
    avanco_range = np.linspace(-15.0, float(fuel['avanco_max']), 30)
    z = np.zeros((30, 30))
    for i, a_adv in enumerate(avanco_range):
        for j, a_afr in enumerate(afr_range):
            z[i, j] = (energia_bruta[50] * (0.30 + (a_adv*0.001)) * 1359.62) + pot_eletrica
    
    fig_heat = go.Figure(data=go.Contour(z=z, x=afr_range, y=avanco_range, colorscale='Viridis'))
    fig_heat.add_trace(go.Scatter(x=[mistura], y=[avanco], mode='markers', marker=dict(color='red', size=12, symbol='cross')))
    fig_heat.update_layout(template="plotly_dark", title="Superfície de Performance")
    st.plotly_chart(fig_heat, use_container_width=True)

with tabs[2]: # Spider Chart
    categorias = ['Potência Específica', 'Limite RPM', 'Avanço', 'Eficiência', 'Viabilidade']
    fig_spider = go.Figure()
    fig_spider.add_trace(go.Scatterpolar(r=[float(fuel['pot_max'])/800, 0.8, 0.7, np.mean(eta)*2, 0.9], theta=categorias, fill='toself', name=nome_sel))
    fig_spider.update_layout(template="plotly_dark", polar=dict(radialaxis=dict(visible=False)))
    st.plotly_chart(fig_spider, use_container_width=True)
