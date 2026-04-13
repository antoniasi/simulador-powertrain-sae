import streamlit as st
import pandas as pd
import plotly.express as px
from st_supabase_connection import SupabaseConnection

# Configuração da Página
st.set_page_config(page_title="Simulador Híbrido SAE", layout="wide")

# 1. CONEXÃO COM O BANCO DE DADOS
try:
    conn = st.connection("supabase", type=SupabaseConnection)
    # Busca a tabela de combustíveis
    response = conn.query("*", table="combustiveis").execute()
    df_db = pd.DataFrame(response.data)
    
    if df_db.empty:
        st.error("A tabela de combustíveis está vazia no Supabase.")
        st.stop()
except Exception as e:
    st.error(f"Erro ao conectar ao Supabase: {e}")
    st.stop()

# TÍTULO E CABEÇALHO
st.title("⚡ Otimização de Powertrain Híbrido - SAE")
st.markdown(f"**Status:** Conectado ao Supabase (`{len(df_db)}` combustíveis carregados)")
st.markdown("---")

# 2. SIDEBAR - PARÂMETROS DE CONTROLE
st.sidebar.header("⚙️ Configurações do Banco")

# Seleção de combustível baseada nos dados REAIS do banco
nome_selecionado = st.sidebar.selectbox("Selecionar Combustível", df_db['nome'].unique())
fuel = df_db[df_db['nome'] == nome_selecionado].iloc[0]

st.sidebar.markdown("---")
st.sidebar.subheader("Ajuste de Calibração")

# Sliders dinâmicos baseados nas propriedades do combustível selecionado
pot_eletrica = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150, step=10)
afr = st.sidebar.slider("Mistura (AFR)", 1.0, 45.0, float(fuel['afr_estoic']), step=0.1)
avanco = st.sidebar.slider("Avanço de Ignição (°)", 5, 50, int(fuel['avanco_base']))

# 3. LÓGICA DE CÁLCULO (ENGENHARIA)
# Define o alvo baseado no tipo de motor (Otto vs Diesel/Pobre)
if fuel['tipo_motor'] in ['Diesel', 'Pobre']:
    alvo_afr = float(fuel['afr_estoic']) * 1.2
else:
    alvo_afr = float(fuel['afr_estoic']) * 0.85

# Cálculo da Penalidade Parabólica (Perda de eficiência por erro de ajuste)
penalidade = (10 * (afr - alvo_afr)**2) + (1.5 * (avanco - float(fuel['avanco_base']))**2)
pot_ice = max(0, float(fuel['pot_max']) - penalidade)
pot_total = pot_ice + pot_eletrica
eficiencia = (pot_ice / float(fuel['pot_max'])) * 100

# 4. EXIBIÇÃO DE MÉTRICAS
col1, col2, col3 = st.columns(3)
col1.metric("Potência ICE (Combustão)", f"{pot_ice:.1f} cv")
col2.metric("Potência Total Híbrida", f"{pot_total:.1f} cv")
col3.metric("Eficiência do Ajuste", f"{eficiencia:.1f}%")

# Alerta de segurança
if pot_ice < (float(fuel['pot_max']) * 0.3):
    st.error("⚠️ Atenção: Perda crítica de potência. Ajuste fora da janela de ignição.")
elif eficiencia > 95:
    st.success(f"✅ Calibração Otimizada para {nome_selecionado}!")

# 5. VISUALIZAÇÃO TÉCNICA (MAPA DE CALOR)
st.markdown("---")
st.subheader(f"📊 Ilha de Eficiência: {nome_selecionado}")
st.write("O gráfico abaixo mostra como a potência total varia ao redor do seu ajuste atual.")

# Gerando malha de dados para o gráfico (Grid Search local)
grid_data = []
for a in [afr + i for i in range(-3, 4)]:
    for v in [avanco + i for i in range(-5, 6)]:
        p_penalidade = (10 * (a - alvo_afr)**2) + (1.5 * (v - float(fuel['avanco_base']))**2)
        p_ice = max(0, float(fuel['pot_max']) - p_penalidade)
        grid_data.append({"AFR": a, "Avanço": v, "Potência Total": p_ice + pot_eletrica})

df_plot = pd.DataFrame(grid_data)

# Criando o Heatmap com Plotly
fig = px.density_heatmap(
    df_plot, x="AFR", y="Avanço", z="Potência Total",
    color_continuous_scale="Turbo",
    labels={'Potência Total': 'Potência (cv)'},
    text_auto=".1f"
)
st.plotly_chart(fig, use_container_width=True)

st.caption("Dados processados via Supabase & Streamlit para artigo técnico SAE.")
