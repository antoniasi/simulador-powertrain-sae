import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SAE Powertrain Optimizer v2", layout="wide")

# --- CONEXÃO COM O BANCO DE DADOS ---
# Tenta ler do Secrets (Streamlit Cloud). Se não existir, usa a string manual (Local).
if "DB_URI" in st.secrets:
    DB_URI = st.secrets["DB_URI"]
else:
    # Substitua aqui apenas para testes locais se necessário
    DB_URI = "postgresql://postgres.pksspzswlwtkejupilod:DGN5iXp7qY8NwPU7@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

@st.cache_resource
def get_engine():
    return create_engine(DB_URI)

def load_data():
    engine = get_engine()
    # Busca a View robusta que criamos no SQL
    query = "SELECT * FROM vw_mapa_eficiencia_powertrain"
    return pd.read_sql(query, engine)

# --- CARREGAMENTO DE DADOS ---
try:
    df = load_data()
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.stop()

# --- SIDEBAR: PAINEL DE CONTROLE ---
st.sidebar.header("🕹️ Painel de Controle")

lista_combustiveis = df['combustivel'].unique()
comb_selecionado = st.sidebar.selectbox("Selecionar Combustível", lista_combustiveis)

# Filtrar dados para o combustível selecionado
df_comb = df[df['combustivel'] == comb_selecionado]

# Sliders dinâmicos baseados no range disponível no banco de dados
min_afr = float(df_comb['afr_testado'].min())
max_afr = float(df_comb['afr_testado'].max())
afr_target = st.sidebar.slider("Mistura (AFR)", min_afr, max_afr, float(df_comb['afr_testado'].median()), 0.1)

min_avanco = int(df_comb['avanco_testado'].min())
max_avanco = int(df_comb['avanco_testado'].max())
avanco_target = st.sidebar.slider("Avanço de Ignição (°BTDC)", min_avanco, max_avanco, int(df_comb['avanco_testado'].median()))

auxilio_eletrico = st.sidebar.number_input("Auxílio Elétrico Adicional (cv)", value=150)

# --- LÓGICA DE CAPTURA DO PONTO ATUAL ---
# Filtra o dataframe para encontrar a configuração exata escolhida nos sliders
try:
    atual = df_comb[
        (df_comb['afr_testado'] >= afr_target - 0.2) & (df_comb['afr_testado'] <= afr_target + 0.2) &
        (df_comb['avanco_testado'] == avanco_target)
    ].iloc[0]
except IndexError:
    st.error("Configuração fora do mapa de operação. Ajuste os sliders.")
    st.stop()

# --- TÍTULO E STATUS DE SEGURANÇA ---
st.title("🚀 Otimização de Powertrain Híbrido - SAE")
st.write(f"**Análise de Performance e Termodinâmica** | Combustível: {comb_selecionado}")

# Alertas dinâmicos baseados na coluna status_seguranca do SQL
status = atual['status_seguranca']
if "PERIGO" in status:
    st.error(f"🛑 {status}")
elif "Ineficiente" in status:
    st.warning(f"⚠️ {status}")
else:
    st.success(f"✅ {status}")

st.divider()

# --- ROW 1: MÉTRICAS PRINCIPAIS (KPIs) ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Potência ICE", f"{atual['potencia_ice']} cv")
with col2:
    pot_total = atual['potencia_ice'] + auxilio_eletrico
    st.metric("Potência Total", f"{pot_total} cv")
with col3:
    # Delta comparativo com limite de segurança de 950°C
    st.metric("EGT (Exaustão)", f"{atual['egt_estimada']} °C", 
              delta=f"{atual['egt_estimada'] - 950} °C", delta_color="inverse")
with col4:
    st.metric("Consumo (BSFC)", f"{atual['bsfc_estimado']} g/kWh")

st.divider()

# --- ROW 2: ANÁLISE GRÁFICA EM ABAS ---
tab_potencia, tab_termica, tab_eficiencia = st.tabs(["📊 Performance", "🔥 Térmica (EGT)", "💰 Consumo e Custo"])

with tab_potencia:
    st.subheader("Mapa de Calor: Potência Total (cv)")
    fig_pot = px.density_heatmap(
        df_comb, x="afr_testado", y="avanco_testado", z="potencia_total",
        color_continuous_scale="Viridis", text_auto=True,
        labels={'afr_testado': 'AFR', 'avanco_testado': 'Avanço (°)'}
    )
    st.plotly_chart(fig_pot, use_container_width=True)

with tab_termica:
    st.subheader("Mapa de Calor: Temperatura de Exaustão (°C)")
    fig_egt = px.density_heatmap(
        df_comb, x="afr_testado", y="avanco_testado", z="egt_estimada",
        color_continuous_scale="Reds", text_auto=True,
        labels={'afr_testado': 'AFR', 'avanco_testado': 'Avanço (°)'}
    )
    st.plotly_chart(fig_egt, use_container_width=True)

with tab_eficiencia:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Eficiência de Consumo (g/kWh)")
        fig_bsfc = px.density_heatmap(
            df_comb, x="afr_testado", y="avanco_testado", z="bsfc_estimado",
            color_continuous_scale="YlGn", text_auto=True
        )
        st.plotly_chart(fig_bsfc, use_container_width=True)
    with col_b:
        st.subheader("Análise Econômica")
        st.metric("Custo Estimado", f"R$ {atual['custo_estimado_hora']} / hora")
        st.info("O custo é calculado com base no BSFC e no preço de mercado do combustível selecionado.")

# --- FOOTER ---
st.divider()
st.caption("Protótipo de Simulação SAE Powertrain v2.0 - Desenvolvido para análise de combustíveis alternativos.")
