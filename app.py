import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SAE Powertrain Optimizer v2.1", layout="wide")

# --- CONEXÃO COM O BANCO DE DADOS ---
# Tenta ler do Secrets (Streamlit Cloud). Se não existir, usa a string manual.
if "DB_URI" in st.secrets:
    DB_URI = st.secrets["DB_URI"]
else:
    # String para teste local (Porta 6543 e SSL)
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

# Filtrar dados para o combustível selecionado
df_comb = df[df['combustivel'] == comb_selecionado]

# Sliders dinâmicos baseados no range disponível no banco
min_afr = float(df_comb['afr_testado'].min())
max_afr = float(df_comb['afr_testado'].max())
afr_target = st.sidebar.slider("Mistura (AFR)", min_afr, max_afr, float(df_comb['afr_testado'].median()), 0.1)

min_avanco = int(df_comb['avanco_testado'].min())
max_avanco = int(df_comb['avanco_testado'].max())
avanco_target = st.sidebar.slider("Avanço de Ignição (°BTDC)", min_avanco, max_avanco, int(df_comb['avanco_testado'].median()))

auxilio_eletrico = st.sidebar.number_input("Auxílio Elétrico (cv)", value=150)

# --- LÓGICA DE CAPTURA DO PONTO ATUAL ---
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
    st.metric("EGT (Exaustão)", f"{atual['egt_estimada']} °C", 
              delta=f"{atual['egt_estimada'] - 950} °C", delta_color="inverse")
with col4:
    st.metric("Consumo (BSFC)", f"{atual['bsfc_estimado']} g/kWh")

st.divider()

# --- ROW 2: ANÁLISE GRÁFICA EM ABAS ---
tab_potencia, tab_termica, tab_spider, tab_3d, tab_eficiencia = st.tabs([
    "📊 Performance 2D", "🔥 Térmica (EGT)", "💡 Comparativo (Spider)", "📐 Visão 3D", "💰 Consumo e Custo"
])

# --- ABA 1: PERFORMANCE 2D ---
with tab_potencia:
    st.subheader("Mapa de Calor: Potência Total (cv)")
    fig_pot = px.density_heatmap(
        df_comb, x="afr_testado", y="avanco_testado", z="potencia_total",
        color_continuous_scale="Viridis", text_auto=True,
        labels={'afr_testado': 'AFR', 'avanco_testado': 'Avanço (°)'}
    )
    st.plotly_chart(fig_pot, use_container_width=True)

# --- ABA 2: TÉRMICA ---
with tab_termica:
    st.subheader("Mapa de Calor: Temperatura de Exaustão (°C)")
    fig_egt = px.density_heatmap(
        df_comb, x="afr_testado", y="avanco_testado", z="egt_estimada",
        color_continuous_scale="Reds", text_auto=True,
        labels={'afr_testado': 'AFR', 'avanco_testado': 'Avanço (°)'}
    )
    st.plotly_chart(fig_egt, use_container_width=True)

# --- ABA 3: SPIDER CHART ---
with tab_spider:
    st.subheader("Análise Multicritério: Combustível Atual vs Referência")
    comb_ref = st.selectbox("Selecionar Referência para Comparação", lista_combustiveis, index=3) # Gasolina como padrão
    
    # Função para extrair o melhor cenário de cada combustível e normalizar de 0 a 1
    def get_metrics(name):
        d = df[df['combustivel'] == name]
        best = d.loc[d['potencia_ice'].idxmax()]
        return [
            best['potencia_ice'] / 800, # Normalizado (Max Nitrometano ~800)
            1 - (best['egt_estimada'] / 1200), # Inverso: quanto menor a EGT, maior a nota
            1 - (best['bsfc_estimado'] / 2000), # Inverso: quanto menor o consumo, maior a nota
            best['potencia_total'] / 950, # Normalizado
            1 - (best['custo_estimado_hora'] / 500) # Inverso: quanto mais barato, maior a nota
        ]

    categories = ['Potência ICE', 'Segurança Térmica', 'Eficiência BSFC', 'Potência Híbrida', 'Viabilidade Econômica']
    
    fig_spider = go.Figure()
    fig_spider.add_trace(go.Scatterpolar(r=get_metrics(comb_selecionado), theta=categories, fill='toself', name=comb_selecionado))
    fig_spider.add_trace(go.Scatterpolar(r=get_metrics(comb_ref), theta=categories, fill='toself', name=comb_ref))
    
    fig_spider.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=True)
    st.plotly_chart(fig_spider, use_container_width=True)

# --- ABA 4: VISÃO 3D ---
with tab_3d:
    st.subheader("Superfície de Resposta: Mapa de Potência 3D")
    
    # Prepara os dados para o formato de matriz
    z_data = df_comb.pivot(index='avanco_testado', columns='afr_testado', values='potencia_total').values
    x_data = df_comb['afr_testado'].unique()
    y_data = df_comb['avanco_testado'].unique()
    
    fig_3d = go.Figure(data=[go.Surface(z=z_data, x=x_data, y=y_data, colorscale='Viridis')])
    
    # Adicionar o ponto atual como um marcador (bolinha vermelha) - CORRIGIDO PARA 'circle'
    fig_3d.add_trace(go.Scatter3d(
        x=[atual['afr_testado']], y=[atual['avanco_testado']], z=[atual['potencia_total']],
        mode='markers', marker=dict(size=10, color='red', symbol='circle'),
        name='Ajuste Atual'
    ))
    
    fig_3d.update_layout(
        scene=dict(xaxis_title='AFR', yaxis_title='Avanço (°)', zaxis_title='Potência (cv)'),
        margin=dict(l=0, r=0, b=0, t=0)
    )
    st.plotly_chart(fig_3d, use_container_width=True)

# --- ABA 5: EFICIÊNCIA ---
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
        st.info("O custo é calculado com base no BSFC (Consumo Específico) e no preço médio de mercado do combustível selecionado.")

# --- FOOTER ---
st.divider()
st.caption("Protótipo de Simulação SAE Powertrain v2.1 - Desenvolvido para análise avançada de combustíveis.")
