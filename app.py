import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Simulador Híbrido SAE", layout="wide")

st.title("⚡ Otimização de Powertrain Híbrido - SAE")
st.markdown("---")

# Sidebar para configurações
st.sidebar.header("⚙️ Parâmetros de Teste")
combustivel = st.sidebar.selectbox("Combustível Base", ["Gasolina", "Etanol", "Hidrogênio", "Nitrometano"])
pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

st.sidebar.markdown("---")
st.sidebar.subheader("Calibração em Tempo Real")
afr = st.sidebar.slider("Mistura (AFR)", 5.0, 40.0, 14.7, help="Relação Ar-Combustível")
avanco = st.sidebar.slider("Avanço de Ignição (°)", 10, 50, 26)

# Lógica de Cálculo (Simulação)
# Estes alvos virão do Supabase às 15h
config_alvos = {
    "Gasolina": {"afr": 12.5, "av": 26, "pot": 300},
    "Etanol": {"afr": 7.6, "av": 32, "pot": 330},
    "Hidrogênio": {"afr": 41.1, "av": 10, "pot": 295},
    "Nitrometano": {"afr": 1.4, "av": 40, "pot": 800}
}

alvo = config_alvos[combustivel]

# Fórmula da Penalidade
penalidade = (10 * (afr - alvo["afr"])**2) + (1.5 * (avanco - alvo["av"])**2)
pot_ice = max(0, alvo["pot"] - penalidade)
pot_total = pot_ice + pot_eletrica

# Exibição de Resultados
col1, col2, col3 = st.columns(3)
col1.metric("Potência ICE", f"{pot_ice:.1f} cv")
col2.metric("Potência Total Híbrida", f"{pot_total:.1f} cv")
col3.metric("Eficiência do Ajuste", f"{((pot_ice/alvo['pot'])*100):.1f}%")

if pot_ice == 0:
    st.error("⚠️ Calibração Crítica: O motor apagou ou sofreu danos térmicos simulados.")
else:
    st.success(f"Motor operando de forma estável com {combustivel}")

st.info("Nota: Às 15h conectaremos este painel ao banco de dados Supabase para gerar mapas de calor.")
