import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SAE Powertrain Optimizer v2.1", layout="wide")

# --- CONEXÃO COM O BANCO DE DADOS ---
if "DB_URI" in st.secrets:
    DB_URI = st.secrets["DB_URI"]
else:
    # String para teste local
    DB_URI = "postgresql://postgres.pksspzswlwtkejupilod:DGN5iXp7qY8NwPU7@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

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
df_comb = df[df['combustivel'] == comb_selecionado]

# Sliders
min_afr, max_afr = float(df_comb['afr_testado'].min()), float(df_comb['afr_testado'].max())
afr_target = st.sidebar.slider("Mistura (AFR)", min_afr, max_afr, float(df_comb['afr_testado'].median()), 0.1)

min_avanco, max_avanco = int(df_comb['avanco_testado'].min()), int(df_comb['avanco_testado'].max())
avanco_target = st.sidebar.slider("Avanço de Ignição (°BTDC)", min_avanco, max_avanco, int(df_comb['avanco_testado'].median()))

auxilio_eletrico = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# Ponto Atual
atual = df_comb[
    (df_comb['afr_testado'] >= afr_target - 0.2) & (df_comb['afr_testado'] <= afr_target + 0.2) &
    (df_comb['avanco_testado'] == avanco_target)
].iloc[0]

# --- TÍTULO E MÉTRICAS ---
st.title("🚀 Otimização de Powertrain Híbrido - SAE")
status = atual['status_seguranca']
if "PERIGO" in status: st.error(f"🛑 {status}")
elif "Ineficiente" in status: st.warning(f"⚠️ {status}")
else: st.success(f"✅ {status}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Potência ICE", f"{atual['potencia_ice']} cv")
col2.metric("Potência Total", f"{atual['potencia_total']} cv")
col3.metric("EGT (Exaustão)", f"{atual['egt_estimada']} °C", delta=f"{atual['egt_estimada'] - 950} °C", delta_color="inverse")
col4.metric("Consumo (BSFC)", f"{atual['bsfc_estimado']} g/kWh")

st.divider()

# --- ABAS DE ANÁLISE ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Performance 2D", "🔥 Térmica", "💡 Comparativo (Spider)", "📐 Visão 3D", "💰 Custo"])

# --- ABA 3: SPIDER CHART (COMPARATIVO) ---
with tab3:
    st.subheader("Análise Multicritério: Combustível Atual vs Referência")
    comb_ref = st.selectbox("Selecionar Referência para Comparação", lista_combustiveis, index=3) # Gasolina como padrão
    
    # Pegar os melhores pontos de cada um para comparar o potencial máximo
    def get_metrics(name):
        d = df[df['combustivel'] == name]
        best = d.loc[d['potencia_ice'].idxmax()]
        return [
            best['potencia_ice'] / 800, # Normalizado pela pot máx do Nitro
            1 - (best['egt_estimada'] / 1200), # Inverso (quanto menor EGT, melhor)
            1 - (best['bsfc_estimado'] / 2000), # Inverso (quanto menor BSFC, melhor)
            best['potencia_total'] / 950,
            1 - (best['custo_estimado_hora'] / 500) # Inverso (quanto menor custo, melhor)
        ]

    categories = ['Potência ICE', 'Segurança Térmica', 'Eficiência BSFC', 'Potência Híbrida', 'Viabilidade Econômica']
    
    fig_spider = go.Figure()
    fig_spider.add_trace(go.Scatterpolar(r=get_metrics(comb_selecionado), theta=categories, fill='toself', name=comb_selecionado))
    fig_spider.add_trace(go.Scatterpolar(r=get_metrics(comb_ref), theta=categories, fill='toself', name=comb_ref))
    
    fig_spider.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=True)
    st.plotly_chart(fig_spider, use_container_width=True)

# --- ABA 4: GRÁFICO 3D ---
with tab4:
    st.subheader("Superfície de Resposta: Mapa de Potência 3D")
    # Pivotar os dados para o formato de matriz que o Surface exige
    z_data = df_comb.pivot(index='avanco_testado', columns='afr_testado', values='potencia_total').values
    x_data = df_comb['afr_testado'].unique()
    y_data = df_comb['avanco_testado'].unique()
    
    fig_3d = go.Figure(data=[go.Surface(z=z_data, x=x_data, y=y_data, colorscale='Viridis')])
    
    # Adicionar o ponto atual como um marcador (esfera)
    fig_3d.add_trace(go.Scatter3d(
        x=[atual['afr_testado']], y=[atual['avanco_testado']], z=[atual['potencia_total']],
        mode='markers', marker=dict(size=10, color='red', symbol='sphere')
    ))
    
    fig_3d.update_layout(
        scene=dict(xaxis_title='AFR', yaxis_title='Avanço (°)', zaxis_title='Potência (cv)'),
        margin=dict(l=0, r=0, b=0, t=0)
    )
    st.plotly_chart(fig_3d, use_container_width=True)

# (Manter os códigos das outras abas Tab1, Tab2 e Tab5 conforme o arquivo anterior)
