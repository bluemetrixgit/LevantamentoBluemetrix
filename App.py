# ================================================================
# APP Streamlit: Controle de Contratos - Consolidado 2026
# ================================================================
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import plotly.express as px

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
                palavras_resumo = ['Contas Ativas', 'Contas Inativas', 'Contas Encerradas', 'Contas Pode Operar']
                df = df[~df.iloc[:, 1].astype(str).str.contains('|'.join(palavras_resumo), case=False, na=False)]
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

# ====================== FORMATAÇÃO ======================
for col in ['Início da Gestão', 'Data distrato']:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')

if 'Conta' in df.columns:
    df['Conta'] = pd.to_numeric(df['Conta'], errors='coerce').fillna(0).astype(int).astype(str)

# ====================== EXTRAÇÃO DE DATAS DE PL ======================
def extrair_datas_pl(df):
    datas_pl = []
    for col in df.columns:
        col_str = str(col).strip()
        if "/" in col_str and len(col_str.split("/")) == 3:
            try:
                dt = pd.to_datetime(col_str, dayfirst=True, errors='coerce')
                if pd.notna(dt):
                    # Formato YYYY-MM para ordenação correta
                    ano_mes_sort = dt.strftime("%Y-%m")
                    # Formato bonito para exibição: Abril/2025
                    mes_ano_display = dt.strftime("%B/%Y")
                    datas_pl.append((dt, ano_mes_sort, mes_ano_display, col_str))
            except:
                continue
    # Ordena pela data real (cronológica)
    return sorted(datas_pl, key=lambda x: x[0], reverse=True)

datas_pl_disponiveis = extrair_datas_pl(df)
opcoes_periodo = ["Mais recente"] + [f"{display} ({col})" for _, _, display, col in datas_pl_disponiveis]

periodo_selecionado = st.sidebar.selectbox("Período do PL", opcoes_periodo)

if periodo_selecionado == "Mais recente":
    coluna_pl = datas_pl_disponiveis[0][3] if datas_pl_disponiveis else None
else:
    coluna_pl = periodo_selecionado.split("(")[-1].strip(")")

def extrair_pl_especifico(row, col_pl):
    if col_pl is None or col_pl not in row.index:
        return 0, None
    valor = pd.to_numeric(row[col_pl], errors='coerce')
    return round(valor) if pd.notna(valor) else 0, col_pl

df[["PL", "Data_PL"]] = df.apply(lambda row: pd.Series(extrair_pl_especifico(row, coluna_pl)), axis=1)

internacional = ["Interactive Brokers", "Pershing", "XP Internacional"]
df.loc[df["Corretora"].isin(internacional), "PL"] = (df.loc[df["Corretora"].isin(internacional), "PL"] * USD_TO_BRL).round(0)

# ====================== FILTROS NA SIDEBAR ======================
st.sidebar.header("🔎 Filtros Gerais")
filtro_escritorio = st.sidebar.multiselect("Escritório", sorted(df["Escritório"].dropna().unique()))
filtro_corretora = st.sidebar.multiselect("Corretora", sorted(df["Corretora"].unique()))
filtro_uf = st.sidebar.multiselect("UF", sorted(df["UF"].dropna().unique()))

status_opcoes = ["Todos"] + sorted(df["Status"].dropna().unique().tolist())
filtro_status = st.sidebar.multiselect("Status da Conta", status_opcoes, default=["Todos"])

df_filtrado = df.copy()
if filtro_escritorio: df_filtrado = df_filtrado[df_filtrado["Escritório"].isin(filtro_escritorio)]
if filtro_corretora: df_filtrado = df_filtrado[df_filtrado["Corretora"].isin(filtro_corretora)]
if filtro_uf:        df_filtrado = df_filtrado[df_filtrado["UF"].isin(filtro_uf)]
if "Todos" not in filtro_status and filtro_status:
    df_filtrado = df_filtrado[df_filtrado["Status"].isin(filtro_status)]

colunas_exibicao = [
    "Corretora", "Cliente", "Conta", "Escritório", "UF", "Assessor", "Carteira",
    "Status", "Início da Gestão", "Data distrato", "PL", "Data_PL"
]

# ====================== TABS ======================
tab_geral, tab_cliente, tab_fluxo, tab_evolucao, tab_assessor = st.tabs([
    "📊 Visão Geral",
    "👤 Por Cliente",
    "📈 Fluxo Mensal/Anual",
    "📉 Evolução PL Total",
    "👥 PL por Assessor"
])

# ABA 1: VISÃO GERAL
with tab_geral:
    st.header("Visão Geral")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Clientes", len(df_filtrado))
    col2.metric("Patrimônio Total", f"R$ {df_filtrado['PL'].sum():,.0f}")
    col3.metric("Período do PL", periodo_selecionado)

    st.dataframe(
        df_filtrado[colunas_exibicao].style.format({"PL": "R$ {:,.0f}"}),
        hide_index=True
    )

# ABA 2: POR CLIENTE (mantido igual)
with tab_cliente:
    st.header("Consolidado por Cliente")
    busca = st.text_input("🔍 Nome (ou parte)", placeholder="Ex: Alessandra Charbel")
    if busca.strip():
        mask = df_filtrado["Cliente"].astype(str).str.contains(busca.strip(), case=False, na=False)
        df_cliente = df_filtrado[mask].copy()
        if not df_cliente.empty:
            st.success(f"**Patrimônio Total Consolidado ({periodo_selecionado}): R$ {df_cliente['PL'].sum():,.0f}**")
            st.dataframe(
                df_cliente[colunas_exibicao].style.format({"PL": "R$ {:,.0f}"}),
                hide_index=True
            )
        else:
            st.warning("Nenhuma conta encontrada.")

# ABA 3: FLUXO MENSAL/ANUAL (mantido)
with tab_fluxo:
    st.header("Contas Novas × Encerramentos por Mês/Ano")
    df["Início da Gestão"] = pd.to_datetime(df["Início da Gestão"], errors='coerce', dayfirst=True)
    df["Data distrato"]     = pd.to_datetime(df["Data distrato"],     errors='coerce', dayfirst=True)
    
    novos = df[df["Início da Gestão"].notna()].copy()
    novos["Ano-Mês"] = novos["Início da Gestão"].dt.strftime("%Y-%m")
    novos_por_mes = novos.groupby("Ano-Mês").size().reset_index(name="Novas")
    
    encerrados = df[df["Data distrato"].notna()].copy()
    encerrados["Ano-Mês"] = encerrados["Data distrato"].dt.strftime("%Y-%m")
    encerrados_por_mes = encerrados.groupby("Ano-Mês").size().reset_index(name="Encerradas")
    
    fluxo = pd.merge(novos_por_mes, encerrados_por_mes, on="Ano-Mês", how="outer").fillna(0)
    fluxo = fluxo.sort_values("Ano-Mês")
    
    fig = px.bar(
        fluxo, x="Ano-Mês", y=["Novas", "Encerradas"],
        title="Contas Novas × Encerradas por Mês",
        barmode="group",
        color_discrete_sequence=["#00CC66", "#FF3333"]
    )
    st.plotly_chart(fig, use_container_width=True)

# ABA 4: EVOLUÇÃO PL TOTAL
with tab_evolucao:
    st.header("Evolução do Patrimônio Total por Mês/Ano")
    
    pl_por_periodo = []
    for _, ano_mes_sort, mes_ano_display, col in datas_pl_disponiveis:
        pl_val = df[col].apply(pd.to_numeric, errors='coerce').sum()
        if pd.notna(pl_val):
            pl_por_periodo.append({
                "Ano-Mês": ano_mes_sort,           # para ordenação correta
                "Período": mes_ano_display,        # para exibição bonita
                "PL Total": round(pl_val)
            })
    
    df_evol = pd.DataFrame(pl_por_periodo).sort_values("Ano-Mês")
    
    fig_evol = px.line(
        df_evol,
        x="Ano-Mês",
        y="PL Total",
        title="Evolução do PL Total",
        markers=True,
        hover_name="Período"
    )
    fig_evol.update_traces(textposition="top center")
    fig_evol.update_layout(
        xaxis_title="Período",
        yaxis_title="PL Total",
        yaxis_tickformat="R$ ,.0f",
        xaxis_tickformat="%b/%Y"  # mostra como Abr/2025 no eixo
    )
    st.plotly_chart(fig_evol, use_container_width=True)
    
    st.dataframe(
        df_evol[["Período", "PL Total"]].style.format({"PL Total": "R$ {:,.0f}"}),
        hide_index=True
    )

# ABA 5: PL POR ASSESSOR
with tab_assessor:
    st.header("Evolução do PL por Assessor")
    
    assessores = sorted(df_filtrado["Assessor"].dropna().unique())
    assessores_sel = st.multiselect("Selecione o(s) assessor(es)", assessores, default=assessores[:3])
    
    if assessores_sel:
        df_ass = df_filtrado[df_filtrado["Assessor"].isin(assessores_sel)].copy()
        
        pl_por_ass = []
        for _, ano_mes_sort, mes_ano_display, col in datas_pl_disponiveis:
            for ass in assessores_sel:
                pl_val = df_ass[(df_ass["Assessor"] == ass)][col].apply(pd.to_numeric, errors='coerce').sum()
                if pd.notna(pl_val):
                    pl_por_ass.append({
                        "Ano-Mês": ano_mes_sort,
                        "Período": mes_ano_display,
                        "Assessor": ass,
                        "PL": round(pl_val)
                    })
        
        df_pl_ass = pd.DataFrame(pl_por_ass).sort_values("Ano-Mês")
        
        fig_ass = px.line(
            df_pl_ass,
            x="Ano-Mês",
            y="PL",
            color="Assessor",
            title="Evolução do PL por Assessor",
            markers=True,
            hover_name="Período"
        )
        fig_ass.update_layout(
            yaxis_tickformat="R$ ,.0f",
            xaxis_tickformat="%b/%Y"
        )
        st.plotly_chart(fig_ass, use_container_width=True)
        
        st.subheader("Tabela por Assessor e Período")
        tabela_pivot = df_pl_ass.pivot_table(
            index="Período",
            columns="Assessor",
            values="PL",
            aggfunc='sum'
        ).fillna(0).sort_index(key=lambda x: pd.to_datetime(x, format="%B/%Y", errors='coerce'))
        
        st.dataframe(
            tabela_pivot.style.format("R$ {:,.0f}"),
            use_container_width=True
        )
    else:
        st.info("Selecione pelo menos um assessor.")

# ====================== RODAPÉ ======================
st.caption(f"""
    • PL exibido como número inteiro • Conta sem ponto/decimal • 
    Datas DD/MM/YYYY • Linhas de resumo ignoradas • Status como filtro na sidebar
""")





