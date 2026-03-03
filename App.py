# ================================================================
# APP Streamlit: Controle de Contratos - Consolidado 2026
# ================================================================
# Autor: Adaptado para Bluemetrix
# Objetivo: Ler planilha Excel do GitHub, mostrar consolidados,
#           permitir busca por cliente (incluindo contas conjuntas)
# ================================================================

import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

# ====================== CONFIGURAÇÕES (NÃO ALTERE A MENOS QUE PRECISE) ======================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/bluemetrixgit/Levantamento-Bluemetrix/main/Controle%20de%20Contratos%20-%20Atualizado%202026.xlsx"

LOGO_URL = "https://raw.githubusercontent.com/bluemetrixgit/Levantamento-Bluemetrix/main/logo.branca.png"

# Cotação dólar → real (mude aqui quando precisar atualizar)
USD_TO_BRL = 5.25

# Abas que serão consolidadas
SHEETS = [
    "BTG",
    "XP",
    "Safra",
    "Ágora",
    "XP Internacional",
    "Pershing",
    "Interactive Brokers"
]
# =============================================================================

# Configuração da página Streamlit
st.set_page_config(
    page_title="Controle de Contratos 2026 - Bluemetrix",
    layout="wide",
    page_icon="📊"
)

# Logo no topo da página
st.image(LOGO_URL, use_column_width=True)

st.title("📊 Controle de Contratos - Consolidado 2026")
st.markdown("**Dados lidos diretamente do GitHub • Atualização automática**")

# ====================== FUNÇÃO QUE CARREGA OS DADOS DO EXCEL ======================
@st.cache_data(ttl=3600)  # cache de 1 hora para não baixar toda vez
def carregar_dados():
    try:
        # Baixa o arquivo Excel do GitHub
        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()  # levanta erro se falhar

        # Converte os bytes em um "arquivo em memória" que o pandas entende
        excel_bytes = BytesIO(response.content)

        dfs = []  # lista para guardar os dataframes de cada aba

        for sheet_name in SHEETS:
            try:
                # Lê cada aba usando a LINHA 2 como cabeçalho (header=1)
                df_sheet = pd.read_excel(
                    excel_bytes,
                    sheet_name=sheet_name,
                    header=1
                )
                # Adiciona coluna com o nome da corretora
                df_sheet["Corretora"] = sheet_name
                dfs.append(df_sheet)
            except Exception as e:
                st.warning(f"Não foi possível ler a aba '{sheet_name}': {e}")

        if not dfs:
            st.error("Nenhuma aba foi carregada com sucesso.")
            return pd.DataFrame()

        # Junta todas as abas em um único dataframe
        return pd.concat(dfs, ignore_index=True)

    except Exception as e:
        st.error(f"Erro ao baixar o arquivo do GitHub: {e}")
        return pd.DataFrame()

# Carrega os dados
df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar os dados. Verifique a URL do arquivo.")
    st.stop()

# ====================== IDENTIFICA E EXTRAI O PL MAIS RECENTE ======================
def pegar_pl_mais_recente(row):
    valores = {}
    for coluna in row.index:
        nome_coluna = str(coluna).strip()
        # Procura colunas que parecem datas no formato DD/MM/YYYY
        if "/" in nome_coluna and len(nome_coluna.split("/")) == 3:
            try:
                data = pd.to_datetime(nome_coluna, dayfirst=True, errors="coerce")
                if pd.notna(data):
                    valor = pd.to_numeric(row[coluna], errors="coerce")
                    if pd.notna(valor) and valor != 0:
                        valores[data] = valor
            except:
                continue
    
    if valores:
        data_mais_nova = max(valores.keys())
        return valores[data_mais_nova], data_mais_nova.strftime("%d/%m/%Y")
    return 0.0, None

# Aplica a função em todas as linhas
df[["PL", "Data_PL"]] = df.apply(
    lambda row: pd.Series(pegar_pl_mais_recente(row)),
    axis=1
)

# ====================== CONVERTE VALORES INTERNACIONAIS (USD → BRL) ======================
contas_internacionais = ["Interactive Brokers", "Pershing", "XP Internacional"]
mask_internacional = df["Corretora"].isin(contas_internacionais)
df.loc[mask_internacional, "PL"] = df.loc[mask_internacional, "PL"] * USD_TO_BRL
df["PL"] = df["PL"].round(2)

# ====================== INTERFACE COM TABS ======================
tab_geral, tab_cliente = st.tabs(["📊 Visão Geral", "👤 Consolidado por Cliente"])

# ────────────────────────────────────────────────
# ABA 1: VISÃO GERAL
# ────────────────────────────────────────────────
with tab_geral:
    st.header("Visão Geral de Todas as Contas")

    # Filtros na sidebar
    st.sidebar.header("🔎 Filtros Gerais")
    filtro_escritorio = st.sidebar.multiselect(
        "Escritório",
        options=sorted(df["Escritório"].dropna().unique()),
        default=[]
    )
    filtro_corretora = st.sidebar.multiselect(
        "Corretora",
        options=sorted(df["Corretora"].unique()),
        default=[]
    )
    filtro_uf = st.sidebar.multiselect(
        "UF",
        options=sorted(df["UF"].dropna().unique()),
        default=[]
    )

    # Aplica os filtros
    df_filtrado = df.copy()
    if filtro_escritorio:
        df_filtrado = df_filtrado[df_filtrado["Escritório"].isin(filtro_escritorio)]
    if filtro_corretora:
        df_filtrado = df_filtrado[df_filtrado["Corretora"].isin(filtro_corretora)]
    if filtro_uf:
        df_filtrado = df_filtrado[df_filtrado["UF"].isin(filtro_uf)]

    # Métricas principais
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Clientes", len(df_filtrado))
    col2.metric("Patrimônio Total", f"R$ {df_filtrado['PL'].sum():,.2f}")
    col3.metric("Cotação Dólar", f"R$ {USD_TO_BRL}")

    # Colunas que vamos exibir
    colunas_exibicao = ["Corretora", "Cliente", "Conta", "Escritório", "UF", "Assessor", "Carteira", "PL", "Data_PL"]

    # Mostra a tabela
    st.dataframe(
        df_filtrado[colunas_exibicao].style.format({"PL": "R$ {:,.2f}"}),
        width=None,           # resolve o warning de depreciação
        hide_index=True
    )

# ────────────────────────────────────────────────
# ABA 2: CONSOLIDADO POR CLIENTE
# ────────────────────────────────────────────────
with tab_cliente:
    st.header("👤 Consolidado por Cliente")
    st.markdown(
        "Digite parte do nome do cliente. Inclui automaticamente contas conjuntas "
        "(ex: 'Alessandra Charbel' pega também linhas com 'e/ou André ...')."
    )

    busca = st.text_input(
        "🔍 Nome (ou parte do nome) do Cliente",
        placeholder="Ex: Alessandra Charbel, João Carlos, Kenia Mendes..."
    )

    if busca.strip():
        # Busca case-insensitive (ignora maiúsculas/minúsculas)
        mask_cliente = df["Cliente"].astype(str).str.contains(busca.strip(), case=False, na=False)
        df_cliente = df[mask_cliente].copy()

        if not df_cliente.empty:
            total_pl = df_cliente["PL"].sum()
            qtd_contas = len(df_cliente)

            st.success(f"**Patrimônio Total Consolidado: R$ {total_pl:,.2f}**")
            st.info(f"Encontradas **{qtd_contas} conta(s)** em todas as corretoras")

            # Tabela completa do cliente
            st.dataframe(
                df_cliente[colunas_exibicao].style.format({"PL": "R$ {:,.2f}"}),
                width=None,
                hide_index=True
            )

            # Resumo por corretora
            resumo_corretora = df_cliente.groupby("Corretora")["PL"].agg(["sum", "count"]).round(2)
            resumo_corretora.columns = ["Patrimônio Total", "Nº de Contas"]
            st.subheader("Resumo por Corretora")
            st.dataframe(
                resumo_corretora.style.format({"Patrimônio Total": "R$ {:,.2f}"}),
                width=None
            )

            # Botão de download específico desse cliente
            csv_cliente = df_cliente[colunas_exibicao].to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Baixar apenas este cliente (CSV)",
                data=csv_cliente,
                file_name=f"Cliente_{busca.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.warning(f"Nenhuma conta encontrada para '{busca}'.")

    else:
        st.info("Digite o nome do cliente acima para ver o consolidado completo.")

# ====================== RODAPÉ / INFORMAÇÕES ======================
st.markdown("---")
st.caption(
    f"""
    • PL extraído automaticamente da coluna de data mais recente (formato DD/MM/YYYY)  
    • Contas internacionais convertidas usando USD = R$ {USD_TO_BRL}  
    • Busca inteligente reconhece nomes parciais e contas conjuntas ("e/ou")  
    • Última atualização dos dados: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    """

)


