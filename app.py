import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# Configuração da Página
st.set_page_config(page_title="Simulador Híbrido SAE", layout="wide")

# 1. CONEXÃO COM O BANCO DE DADOS (CLIENTE DIRETO)
try:
    # Busca as credenciais das Secrets
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    
    # Inicializa o cliente oficial do Supabase
    supabase = create_client(url, key)
    
    # Busca os dados da tabela
    response = supabase.table("combustiveis").select("*").execute()
    df_db = pd.DataFrame(response.data)
    
    if df_db.empty:
        st.error("A tabela 'combustiveis' foi encontrada, mas está vazia.")
        st.stop()
        
except Exception as e:
    st.error(f"Erro crítico de conexão: {e}")
    st.info("Dica: Verifique se as Secrets estão como [connections.supabase] e se a URL/Key estão corretas.")
    st.stop()

# TÍTULO E CABEÇALHO
st.title("Otimização de Powertrain Híbrido - SAE")
st.markdown(f"**Status:** Conectado ao banco de dados SAE (Data: {len(df_db)} combustíveis)")
st.markdown("---")

# 2. SIDEBAR - PARÂMETROS DE CONTROLE
st.sidebar.header("⚙️ Painel de Controle")

# Seleção de combustível vindo do SQL
nome_selecionado = st.sidebar.selectbox("Selecionar Combustível", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_selecionado].iloc[0]

st.sidebar.markdown("---")
st.sidebar.subheader("Calibração em Tempo Real")

# Inputs numéricos e Sliders
pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150, step=10)
# Os sliders agora iniciam no valor exato que está cadastrado no seu banco
afr = st.sidebar.slider("Mistura (AFR)", 1.0, 45.0, float(fuel['afr_estoic']), step=0.1)
avanco = st.sidebar.slider("Avanço de Ignição (°BTDC)", 5, 50, int(fuel['avanco_base']))

# 3. LÓGICA DE ENGENHARIA (CÁLCULOS)
# Define o alvo estequiométrico baseado no tipo de ciclo (Otto vs Diesel/Pobre)
if fuel['tipo_motor'] in ['Diesel', 'Pobre']:
    alvo_afr = float(fuel['afr_estoic']) * 1.2
else:
    alvo_afr = float(fuel['afr_estoic']) * 0.85

# Cálculo da Penalidade Parabólica
penalidade = (10 * (afr - alvo_afr)**2) + (1.5 * (avanco - float(fuel['avanco_base']))**2)
pot_ice = max(0, float(fuel['pot_max']) - penalidade)
pot_total = pot_ice + pot_eletrica
eficiencia = (pot_ice / float(fuel['pot_max'])) * 100

# 4. DASHBOARD DE MÉTRICAS
col1, col2, col3 = st.columns(3)
col1.metric("Potência ICE", f"{pot_ice:.1f} cv")
col2.metric("Potência Total (Híbrida)", f"{pot_total:.1f} cv")
col3.metric("Eficiência do Setup", f"{eficiencia:.1f}%")

# Feedback visual de engenharia
if eficiencia < 40:
    st.error("⚠️ Calibração Instável: Risco de danos mecânicos ou falha de ignição.")
elif eficiencia > 95:
    st.success(f"✅ Setup de Alta Performance para {nome_selecionado}!")

# 5. VISUALIZAÇÃO TÉCNICA (MAPA DE CALOR)
st.markdown("---")
st.subheader(f"📊 Análise de Sensibilidade: {nome_selecionado}")
st.write("O mapa abaixo simula a variação de potência total nos arredores do seu ajuste atual.")

# Gerando malha de simulação para o gráfico
grid_data = []
for a in [afr + (i * 0.5) for i in range(-5, 6)]:
    for v in [avanco + i for i in range(-5, 6)]:
        p_penalidade = (10 * (a - alvo_afr)**2) + (1.5 * (v - float(fuel['avanco_base']))**2)
        p_ice = max(0, float(fuel['pot_max']) - p_penalidade)
        grid_data.append({"AFR": a, "Avanço": v, "Potência Total": p_ice + pot_eletrica})

df_plot = pd.DataFrame(grid_data)

# Gráfico de calor usando Plotly
fig = px.density_heatmap(
    df_plot, x="AFR", y="Avanço", z="Potência Total",
    color_continuous_scale="Viridis",
    labels={'Potência Total': 'Potência (cv)'},
    text_auto=".0f"
)
st.plotly_chart(fig, use_container_width=True)

st.caption("Desenvolvido por Daniel Antoniasi - Projeto SAE Powertrain Otimização")
