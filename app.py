import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from supabase import create_client

st.set_page_config(page_title="Simulador SAE Powertrain", layout="wide")

# ==========================================
# 1. CONEXÃO COM O BANCO DE DADOS
# ==========================================
try:
    url = st.secrets["url"]
    key = st.secrets["key"]
    supabase = create_client(url, key)
    # Puxa os dados da tabela combustiveis
    response = supabase.table("combustiveis").select("*").execute()
    df_db = pd.DataFrame(response.data)
except Exception as e:
    st.error(f"Erro de conexão com o Supabase: {e}")
    st.stop()

# ==========================================
# 2. INTERFACE DINÂMICA (SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Calibração Técnica")
nome_sel = st.sidebar.selectbox("Combustível Selecionado", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_sel].iloc[0]

st.sidebar.markdown("---")

# Ajuste 1: Sinal AFR (Forçando limite negativo para leitura do sensor em mA)
# Pega o menor valor entre -5.0 ou o mínimo do banco
min_afr = min(-5.0, float(fuel['afr_min']))
mistura = st.sidebar.slider(
    "Sinal Sensor AFR (mA) \n*(Negativo=Rico | Positivo=Pobre)*", 
    min_value=min_afr, 
    max_value=float(fuel['afr_max']), 
    value=float(fuel['afr_estoic']), 
    step=0.1
)

# Ajuste 2: Avanço (Liberando avanço negativo / ATDC)
avanco = st.sidebar.slider(
    "Avanço de Ignição (°BTDC)", 
    min_value=-15.0, # Permite ponto atrasado
    max_value=float(fuel['avanco_max']), 
    value=float(fuel['avanco_base']),
    step=1.0
)

pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# ==========================================
# 3. LÓGICA DE CURVA (Cenário Atual do Slider)
# ==========================================
rpm_limite = int(fuel['rpm_max'])
rpm = np.linspace(1000, rpm_limite, 100)

# Alvo ideal estequiométrico ajustado para performance (ex: 10% mais rico)
alvo_afr = float(fuel['afr_estoic']) * 0.9 

# Cálculo de eficiência baseado no desvio do ponto ideal
erro_mistura = abs(mistura - alvo_afr) * 0.15
erro_avanco = abs(avanco - fuel['avanco_base']) * 0.05
eficiencia_total = max(0, 1 - (erro_mistura + erro_avanco))

pico_torque_rpm = int(fuel['rpm_pico_torque'])
torque_max = float(fuel['pot_max']) * 0.8

# Curva parabólica centralizada no pico de torque do banco
torque_curva = torque_max * (1 - ((rpm - pico_torque_rpm)**2 / (rpm_limite**2 / 2))) * eficiencia_total
pot_ice = (torque_curva * rpm) / 716.2
pot_total = pot_ice + pot_eletrica

# ==========================================
# 4. DASHBOARD E ABAS
# ==========================================
st.title("⚡ Otimização de Powertrain Híbrido - SAE")

# KPIs Rápidos
col1, col2, col3 = st.columns(3)
col1.metric("Pico ICE", f"{max(pot_ice):.1f} cv")
col2.metric("Pico Combinado (Híbrido)", f"{max(pot_total):.1f} cv")
col3.metric("Eficiência de Combustão", f"{eficiencia_total*100:.1f}%")

if eficiencia_total < 0.5:
    st.error("⚠️ Calibração Crítica: Risco de detonação, derretimento ou falha de ignição.")

st.markdown("---")

# Abas para organizar os visuais
tab1, tab2, tab3 = st.tabs(["📈 Curva de Potência", "🔥 Mapa de Calor (AFR x Avanço)", "🕸️ Comparativo Multicritério"])

# --- ABA 1: CURVA DE POTÊNCIA (Seu gráfico original) ---
with tab1:
    fig_curva = go.Figure()
    fig_curva.add_trace(go.Scatter(x=rpm, y=pot_ice, name="Motor a Combustão (ICE)", line=dict(color='orange', dash='dot')))
    fig_curva.add_trace(go.Scatter(x=rpm, y=pot_total, name="Conjunto Híbrido (Total)", line=dict(color='#00d4ff', width=4)))
    
    fig_curva.update_layout(
        template="plotly_dark",
        xaxis_title="Rotação (RPM)",
        yaxis_title="Potência (cv)",
        hovermode="x unified",
        title=f"Dyno Sweep: {nome_sel}"
    )
    st.plotly_chart(fig_curva, use_container_width=True)

# --- ABA 2: MAPA DE CALOR (Gerado matematicamente) ---
with tab2:
    st.subheader(f"Superfície de Performance Estimada: {nome_sel}")
    
    # Gera uma malha 2D (Grid) para simular o mapa
    afr_range = np.linspace(min_afr, float(fuel['afr_max']), 30)
    avanco_range = np.linspace(-15.0, float(fuel['avanco_max']), 30)
    z_potencia = np.zeros((len(avanco_range), len(afr_range)))

    # Calcula a potência máxima para cada cruzamento de AFR e Avanço
    for i, a_adv in enumerate(avanco_range):
        for j, a_afr in enumerate(afr_range):
            e_mistura = abs(a_afr - alvo_afr) * 0.15
            e_avanco = abs(a_adv - fuel['avanco_base']) * 0.05
            eff_ponto = max(0, 1 - (e_mistura + e_avanco))
            
            p_ice_ponto = (torque_max * pico_torque_rpm) / 716.2 * eff_ponto
            z_potencia[i, j] = p_ice_ponto + pot_eletrica # Potência Total

    fig_heat = go.Figure(data=go.Contour(
        z=z_potencia, x=afr_range, y=avanco_range,
        colorscale='Viridis',
        contours=dict(showlabels=True, labelfont=dict(color='white'))
    ))
    
    # Adiciona uma "mira" mostrando onde os sliders estão configurados no momento
    fig_heat.add_trace(go.Scatter(
        x=[mistura], y=[avanco], mode='markers',
        marker=dict(color='red', size=12, symbol='cross'),
        name='Ajuste Atual'
    ))

    fig_heat.update_layout(
        template="plotly_dark",
        xaxis_title="Sinal Sensor AFR (mA)",
        yaxis_title="Avanço de Ignição (°BTDC)",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# --- ABA 3: GRÁFICO DE TEIA (SPIDER CHART) ---
with tab3:
    col_spider1, col_spider2 = st.columns([1, 3])
    with col_spider1:
        st.write("### Análise Competitiva")
        comb_ref = st.selectbox("Comparar com:", df_db['nome'].unique(), index=len(df_db)-1)
    
    with col_spider2:
        # Função para normalizar os dados (transformar em porcentagem de 0 a 1) para o gráfico não distorcer
        def normalizar_radar(row_fuel):
            max_pot = float(df_db['pot_max'].max())
            max_rpm = float(df_db['rpm_max'].max())
            max_avanco = float(df_db['avanco_max'].max())
            
            return [
                float(row_fuel['pot_max']) / max_pot,
                float(row_fuel['rpm_max']) / max_rpm,
                float(row_fuel['avanco_max']) / max_avanco,
                0.8, # Eficiência Térmica (Valor simulado ilustrativo)
                0.9  # Custo/Disponibilidade (Valor simulado ilustrativo)
            ]

        categorias = ['Potência Específica', 'Limite de Rotação', 'Tolerância ao Avanço', 'Eficiência Térmica', 'Viabilidade Projeto']
        
        fig_spider = go.Figure()
        
        # Desenha o combustível principal
        fig_spider.add_trace(go.Scatterpolar(
            r=normalizar_radar(fuel), theta=categorias, fill='toself', name=nome_sel, line_color='#00d4ff'
        ))
        
        # Desenha o combustível de referência
        if comb_ref != nome_sel:
            f_ref = df_db[df_db['nome'] == comb_ref].iloc[0]
            fig_spider.add_trace(go.Scatterpolar(
                r=normalizar_radar(f_ref), theta=categorias, fill='toself', name=comb_ref, line_color='orange'
            ))

        fig_spider.update_layout(
            template="plotly_dark",
            polar=dict(radialaxis=dict(visible=False, range=[0, 1])),
            showlegend=True
        )
        st.plotly_chart(fig_spider, use_container_width=True)
