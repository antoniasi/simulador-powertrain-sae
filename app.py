import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SAE Powertrain Optimizer v2", layout="wide")

# Substitua pelas suas credenciais do Supabase (URI de conexão direta)
DB_URI = "postgresql://postgres:[SENHA]@db.[ID-PROJETO].supabase.co:5432/postgres"

@st.cache_resource
def get_engine():
    return create_engine(DB_URI)

def load_data():
    engine = get_engine()
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

# Sliders dinâmicos baseados no range disponível no DB
min_afr = float(df_comb['afr_testado'].min())
max_afr = float(df_comb['afr_testado'].max())
afr_target = st.sidebar.slider("Mistura (AFR)", min_afr, max_afr, float(df_comb['afr_testado'].median()), 0.1)

min_avanco = int(df_comb['avanco_testado'].min())
max_avanco = int(df_comb['avanco_testado'].max())
avanco_target = st.sidebar.slider("Avanço de Ignição (°BTDC)", min_avanco, max_avanco, int(df_comb['avanco_testado'].median()))

auxilio_eletrico = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# --- LÓGICA DE CAPTURA DO PONTO ATUAL ---
# Busca a linha exata no dataframe que corresponde ao ajuste dos sliders
atual = df_comb[
    (df_comb['afr_testado'] >= afr_target - 0.2) & (df_comb['afr_testado'] <= afr_target + 0.2) &
    (df_comb['avanco_testado'] == avanco_target)
].iloc[0]

# --- TÍTULO E STATUS ---
st.title("🚀 Otimização de Powertrain Híbrido - SAE")
st.write(f"**Desenvolvido por Daniel Antoniasi** | Combustível: {comb_selecionado}")

# Alertar sobre a segurança (Mudança de cor dinâmica)
status = atual['status_seguranca']
if "PERIGO" in status:
    st.error(f"🛑 {status}")
elif "Ineficiente" in status:
    st.warning(f"⚠️ {status}")
else:
    st.success(f"✅ {status}")

st.divider()

# --- ROW 1: MÉTRICAS PRINCIPAIS ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Potência ICE", f"{atual['potencia_ice']} cv")
with col2:
    # Somando o auxílio elétrico dinâmico do slider
    pot_total = atual['potencia_ice'] + auxilio_eletrico
    st.metric("Potência Total", f"{pot_total} cv")
with col3:
    # Delta baseado em temperatura crítica de 950 graus
    st.metric("EGT (Temperatura)", f"{atual['egt_estimada']} °C", 
              delta=f"{atual['egt_estimada'] - 950} °C", delta_color="inverse")
with col4:
    st.metric("Consumo (BSFC)", f"{atual['bsfc_estimado']} g/kWh")

st.divider()

# --- ROW 2: ANÁLISE GRÁFICA (TABS) ---
tab_potencia, tab_termica, tab_custo = st.tabs(["📊 Mapa de Performance", "🔥 Análise Térmica", "💰 Eficiência e Custo"])

with tab_potencia:
    st.subheader("Variação de Potência Total (cv)")
    fig_pot = px.density_heatmap(
        df_comb, x="afr_testado", y="avanco_testado", z="potencia_total",
        color_continuous_scale="Viridis", text_auto=True,
        labels={'afr_testado': 'AFR', 'avanco_testado': 'Avanço (°)'}
    )
    st.plotly_chart(fig_pot, use_container_width=True)

with tab_termica:
    st.subheader("Mapa de Temperatura de Exaustão (EGT)")
    fig_egt = px.density_heatmap(
        df_comb, x="afr_testado", y="avanco_testado", z="egt_estimada",
        color_continuous_scale="Reds", text_auto=True,
        labels={'afr_testado': 'AFR', 'avanco_testado': 'Avanço (°)'}
    )
    st.plotly_chart(fig_egt, use_container_width=True)

with tab_custo:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Eficiência de Consumo (g/kWh)")
        fig_bsfc = px.density_heatmap(
            df_comb, x="afr_testado", y="avanco_testado", z="bsfc_estimado",
            color_continuous_scale="Bluyl", text_auto=True
        )
        st.plotly_chart(fig_bsfc, use_container_width=True)
    with col_b:
        st.subheader("Custo Estimado por Hora (BRL)")
        st.metric("Custo/Hora Atual", f"R$ {atual['custo_estimado_hora']}")
        st.info("O custo considera a densidade energética e o BSFC do combustível selecionado.")

# --- FOOTER ---
st.caption("Nota: Os dados apresentados são simulações baseadas em modelos termodinâmicos para o Projeto SAE.")
