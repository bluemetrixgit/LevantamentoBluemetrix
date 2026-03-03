# ================================================================
# APP Streamlit: Controle de Contratos - Consolidado 2026
# ================================================================
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

# ====================== CONFIGURAÇÕES ======================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/bluemetrixgit/LevantamentoBluemetrix/main/Controle%20de%20Contratos%20-%20Atualizado%202026.xlsx"
LOGO_URL = "https://raw.githubusercontent.com/bluemetrixgit/Levantamento-Bluemetrix/main/logo.branca.png"

USD_TO_BRL = 5.25

SHEETS = ["BTG", "XP", "Safra", "Ágora", "XP Internacional", "Pershing", "Interactive Brokers"]
# =============================================================================

st.set_page_config(page_title="Controle de Contratos 2026", layout="wide", page_icon="📊")
st.image(LOGO_URL, use_column_width=True)
st.title("📊 Controle de Contratos - Consolidado 2026")
st.markdown("**Dados lidos diretamente do GitHub • Atualização automática**")

# ====================== CARREGAMENTO ======================
@st.cache_data(ttl=3600)
def carregar_dados():
    try:
        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()
        excel_bytes = BytesIO(response.content)
        dfs = []
        for sheet_name in SHEETS:
            try:
                df = pd.read_excel(excel_bytes, sheet_name=sheet_name, header=1)
                df = df.dropna(how='all').reset_index(drop=True)
                df["Corretora"] = sheet_name
                dfs.append(df)
            except Exception as e:
                st.warning(f"Erro na aba '{sheet_name}': {e}")
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao baixar do GitHub: {e}")
        return pd.DataFrame()

df = carregar_dados()
if df.empty:
    st.stop()

# ====================== IDENTIFICA TODAS AS DATAS DE PL ======================
def extrair_datas_pl(df):
    datas_pl = set()
    for col in df.columns:
        col_str = str(col).strip()
        if "/" in col_str and len(col_str.split("/")) == 3:
            try:
                dt = pd.to_datetime(col_str, dayfirst=True, errors='coerce')
                if pd.notna(dt):
                    mes_ano = dt.strftime("%B/%Y")  # ex: Março/2025
                    datas_pl.add((dt, mes_ano, col_str))
            except:
                continue
    # Ordena por data real
    datas_ordenadas = sorted(datas_pl, key=lambda x: x[0], reverse=True)
    return datas_ordenadas  # lista de tuplas (datetime, "Mês/Ano", "coluna_original")

datas_pl_disponiveis = extrair_datas_pl(df)

# Opções para o selectbox
opcoes_periodo = ["Mais recente"] + [f"{mes_ano} ({col})" for _, mes_ano, col in datas_pl_disponiveis]
periodo_selecionado = st.sidebar.selectbox("Selecione o período do PL", opcoes_periodo)

# Determina qual coluna usar para PL
if periodo_selecionado == "Mais recente":
    coluna_pl = datas_pl_disponiveis[0][2] if datas_pl_disponiveis else None
else:
    # Extrai o nome da coluna do texto selecionado
    coluna_pl = periodo_selecionado.split("(")[-1].strip(")")
    coluna_pl = coluna_pl.strip(")")

# Função para extrair PL de uma coluna específica
def extrair_pl_especifico(row, col_pl):
    if col_pl is None or col_pl not in row.index:
        return 0, None
    valor = pd.to_numeric(row[col_pl], errors='coerce')
    data_str = col_pl if col_pl else None
    return round(valor) if pd.notna(valor) else 0, data_str

# Aplica PL do período escolhido
df[["PL", "Data_PL"]] = df.apply(lambda row: pd.Series(extrair_pl_especifico(row, coluna_pl)), axis=1)

# Conversão internacional (após extrair PL)
internacional = ["Interactive Brokers", "Pershing", "XP Internacional"]
df.loc[df["Corretora"].isin(internacional), "PL"] = (df.loc[df["Corretora"].isin(internacional), "PL"] * USD_TO_BRL).round(0)

# Colunas de exibição
colunas_exibicao = [
    "Corretora", "Cliente", "Conta", "Escritório", "UF", "Assessor", "Carteira",
    "Status", "Início da Gestão", "Data distrato", "PL", "Data_PL"
]

# ====================== TABS ======================
tab_geral, tab_cliente = st.tabs(["📊 Visão Geral", "👤 Por Cliente"])

# ────────────────────────────────────────────────
# ABA 1: VISÃO GERAL
# ────────────────────────────────────────────────
with tab_geral:
    st.header("Visão Geral")
    st.sidebar.header("🔎 Filtros Gerais")
    
    filtro_escritorio = st.sidebar.multiselect("Escritório", sorted(df["Escritório"].dropna().unique()))
    filtro_corretora = st.sidebar.multiselect("Corretora", sorted(df["Corretora"].unique()))
    filtro_uf = st.sidebar.multiselect("UF", sorted(df["UF"].dropna().unique()))

    df_filtrado = df.copy()
    if filtro_escritorio: df_filtrado = df_filtrado[df_filtrado["Escritório"].isin(filtro_escritorio)]
    if filtro_corretora: df_filtrado = df_filtrado[df_filtrado["Corretora"].isin(filtro_corretora)]
    if filtro_uf: df_filtrado = df_filtrado[df_filtrado["UF"].isin(filtro_uf)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Clientes", len(df_filtrado))
    col2.metric("Patrimônio Total", f"R$ {df_filtrado['PL'].sum():,.0f}")
    col3.metric("Período Selecionado", periodo_selecionado if periodo_selecionado != "Mais recente" else "Mais recente")

    st.dataframe(
        df_filtrado[colunas_exibicao].style.format({"PL": "{:,.0f}"}),
        hide_index=True
    )

# ────────────────────────────────────────────────
# ABA 2: POR CLIENTE (mantida igual, mas usa o PL selecionado)
# ────────────────────────────────────────────────
with tab_cliente:
    st.header("Consolidado por Cliente")
    busca = st.text_input("🔍 Nome (ou parte)", placeholder="Ex: Alessandra Charbel")
    
    if busca.strip():
        mask = df["Cliente"].astype(str).str.contains(busca.strip(), case=False, na=False)
        df_cliente = df[mask].copy()
        
        if not df_cliente.empty:
            total_pl = df_cliente["PL"].sum()
            st.success(f"**Patrimônio Total Consolidado ({periodo_selecionado}): R$ {total_pl:,.0f}**")
            st.dataframe(
                df_cliente[colunas_exibicao].style.format({"PL": "{:,.0f}"}),
                hide_index=True
            )
        else:
            st.warning("Nenhuma conta encontrada.")

# ====================== RODAPÉ ======================
st.caption(f"""
    • PL exibido como número inteiro • Período selecionado: {periodo_selecionado}  
    • Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}
""")






