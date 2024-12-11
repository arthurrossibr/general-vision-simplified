import json
import re

import pandas as pd
import plotly.express as px
import streamlit as st
from babel.numbers import format_currency
from unidecode import unidecode


def format_currency_brl(value):
    return format_currency(value, "BRL", locale="pt_BR")

def load_data(file_paths):
    dataframes = []
    for file in file_paths:
        with open(file, "r") as f:
            json_data = f.read()
        json_dict = json.loads(json_data)
        main_key = next(iter(json_dict))
        df = pd.json_normalize(json_dict[main_key])
        dataframes.append(df)
    return pd.concat(dataframes, ignore_index=True)


def load_geojson(geojson_path="resource/brazil_states.geojson"):
    with open(geojson_path, "r") as file:
        geojson_brasil = json.load(file)
    return geojson_brasil


def load_states(filename="resource/estados_brasil.txt"):
    with open(filename, "r") as file:
        estados_brasil = [line.strip() for line in file]
    return estados_brasil


def extract_distribution_by_column(df, column_name, new_column_names, cut=False, cut_limit=5):

    distribution = df[column_name].value_counts().reset_index()
    distribution.columns = new_column_names
    if len(distribution) > cut_limit and cut:
        top_categories = distribution.iloc[:cut_limit]
        outros_total = distribution.iloc[cut_limit:][new_column_names[1]].sum()
        outros_row = pd.DataFrame({new_column_names[0]: ["OUTROS"], new_column_names[1]: [outros_total]})
        distribution = pd.concat([top_categories, outros_row], ignore_index=True)
    return distribution


def extract_top_principal_subjects(df, cut=False, cut_limit=5):
    df_ranking = (
        df["assuntosCNJ"]
        .explode()
        .dropna()
        .loc[
            lambda x: x.apply(
                lambda item: isinstance(item, dict) and item.get("ePrincipal", False)
            )
        ]
        .apply(lambda item: item["titulo"])
        .value_counts()
        .reset_index()
        .rename(columns={"assuntosCNJ": "Assunto", "count": "Total"})
    )



    if cut and len(df_ranking) > cut_limit:
        top_categories = df_ranking.iloc[:cut_limit]
        outros_total = df_ranking.iloc[cut_limit:]["Total"].sum()
        outros_row = pd.DataFrame({"Assunto": ["OUTROS"], "Total": [outros_total]})
        df_ranking = pd.concat([top_categories, outros_row], ignore_index=True)

    return df_ranking

def extract_distribution_from_principal_subjects(df, new_column_names, cut=False, cut_limit=5):
    # Explodir e filtrar os assuntos principais
    principal_subjects = (
        df["assuntosCNJ"]
        .explode()
        .dropna()
        .loc[
            lambda x: x.apply(
                lambda item: isinstance(item, dict) and item.get("ePrincipal", False)
            )
        ]
        .apply(lambda item: item["titulo"])
    )

    # Contar os valores e criar a distribuição
    distribution = principal_subjects.value_counts().reset_index()
    distribution.columns = new_column_names

    # Aplicar corte, se necessário
    if cut and len(distribution) > cut_limit:
        top_categories = distribution.iloc[:cut_limit]
        outros_total = distribution.iloc[cut_limit:][new_column_names[1]].sum()
        outros_row = pd.DataFrame({new_column_names[0]: ["OUTROS"], new_column_names[1]: [outros_total]})
        distribution = pd.concat([top_categories, outros_row], ignore_index=True)

    # Calcular percentual
    distribution["Percentual"] = (distribution[new_column_names[1]] / distribution[new_column_names[1]].sum()) * 100
    distribution["Percentual"] = distribution["Percentual"].apply(lambda x: f"{x:.2f}%")

    return distribution


def normalize_name(name):
    if isinstance(name, str):
        name = unidecode(name.strip().upper())
        name = re.sub(r'\bS[./\s]?A\b', 'SA', name)
        name = re.sub(r'[./-]', ' ', name)
        name = re.sub(r'\b(SA|LTDA|LIMITADA|ME|EPP|EIRELI|INC|LLC?)\b', '', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
    return name


def extract_top_parties(df, top_n=5):
    df_parties = df["partes"].explode().apply(pd.Series)
    df_parties["nome"] = df_parties["nome"].apply(normalize_name)
    top_parties = (
        df_parties["nome"]
        .value_counts()
        .reset_index()
        .rename(columns={"nome": "Nome", "count": "Total"})
    )
    top_parties["Percentual"] = (top_parties["Total"] / top_parties["Total"].sum()) * 100
    top_parties["Percentual"] = top_parties["Percentual"].apply(lambda x: f"{x:.2f}%")
    return top_parties.head(top_n)


def extract_top_lawyers(df, top_n=5):
    df_parties = df["partes"].explode().apply(pd.Series)
    df_lawyers = pd.json_normalize(df_parties.explode("advogados")["advogados"]).dropna(
        subset=["oab.numero"]
    )
    df_lawyers["nome"] = df_lawyers["nome"].apply(normalize_name)
    top_lawyers = (
        df_lawyers["nome"]
        .value_counts()
        .reset_index()
        .rename(columns={"nome": "Nome", "count": "Total"})
    )
    top_lawyers["Percentual"] = (top_lawyers["Total"] / top_lawyers["Total"].sum()) * 100
    top_lawyers["Percentual"] = top_lawyers["Percentual"].apply(lambda x: f"{x:.2f}%")
    return top_lawyers.head(top_n)


def extract_state_data(df):
    estados_brasil = load_states()

    df_states = (
        df.groupby("uf")
        .agg(
            quantidade=("numeroProcessoUnico", "count"),
            valor_total=("valorCausa.valor", "sum"),
        )
        .reset_index()
    )

    df_states["percentual"] = (
        df_states["quantidade"] / df_states["quantidade"].sum()
    ) * 100
    df_estado_completo = pd.DataFrame(estados_brasil, columns=["uf"])
    df_estado_completo = df_estado_completo.merge(
        df_states, on="uf", how="left"
    ).fillna({"quantidade": 0, "percentual": 0, "valor_total": 0})

    df_estado_completo["Label"] = df_estado_completo.apply(
        lambda row: f"{row['uf']}: {row['quantidade']} processos ({row['percentual']:.2f}%)",
        axis=1,
    )

    return df_estado_completo


def extract_dist_vs_arq(df):
    # Converta as colunas relevantes para datetime
    df["dataDistribuicao"] = pd.to_datetime(df["dataDistribuicao"], errors="coerce")
    df["statusPredictus.dataArquivamento"] = pd.to_datetime(
        df["statusPredictus.dataArquivamento"], errors="coerce"
    )

    # Certifique-se de que os valores são datetime-like antes de acessar .dt
    if pd.api.types.is_datetime64_any_dtype(df["dataDistribuicao"]):
        distribuidos = df["dataDistribuicao"].dt.year.value_counts().rename("Distribuídos")
    else:
        distribuidos = pd.Series(dtype="int", name="Distribuídos")

    if pd.api.types.is_datetime64_any_dtype(df["statusPredictus.dataArquivamento"]):
        arquivados = df["statusPredictus.dataArquivamento"].dt.year.value_counts().rename("Arquivados")
    else:
        arquivados = pd.Series(dtype="int", name="Arquivados")

    # Combine as séries em um DataFrame
    df_dist_arq = pd.concat([distribuidos, arquivados], axis=1).reset_index()
    df_dist_arq = df_dist_arq.rename(columns={"index": "Ano"})

    return df_dist_arq


def extract_principal_subjects_per_year(df):
    # Extrair o ano
    df["Ano"] = pd.to_datetime(df["dataDistribuicao"], errors="coerce").dt.year

    # Explodir e filtrar os assuntos principais
    df_assuntos = (
        df.explode("assuntosCNJ")
        .dropna(subset=["assuntosCNJ"])
        .loc[lambda x: x["assuntosCNJ"].apply(lambda item: isinstance(item, dict) and item.get("ePrincipal", False))]
        .assign(Assunto=lambda x: x["assuntosCNJ"].apply(lambda item: item["titulo"]))
    )

    # Contar os assuntos por ano
    df_assuntos_contagem = (
        df_assuntos.groupby(["Ano", "Assunto"])
        .size()
        .reset_index(name="Total")
        .sort_values(by=["Ano", "Total"], ascending=[True, False])
    )

    # Manter apenas o assunto mais frequente por ano
    df_top_assuntos = df_assuntos_contagem.groupby("Ano").head(3)

    # Calcular o percentual de ocorrência
    total_por_ano = df_assuntos.groupby("Ano").size().rename("TotalAno")
    df_top_assuntos = df_top_assuntos.merge(total_por_ano, on="Ano")
    df_top_assuntos["Percentual"] = (df_top_assuntos["Total"] / df_top_assuntos["TotalAno"]) * 100
    df_top_assuntos["Percentual"] = df_top_assuntos["Percentual"].apply(lambda x: f"{x:.2f}%")

    # Selecionar colunas finais e converter o ano para inteiro
    df_top_assuntos = df_top_assuntos[["Ano", "Assunto", "Total", "Percentual"]]
    df_top_assuntos["Ano"] = df_top_assuntos["Ano"].astype(int).astype(str)

    return df_top_assuntos


def create_assuntos_df(df):
    df_assuntos = (
        df["assuntosCNJ"]
        .explode()
        .dropna()
        .apply(lambda x: x["titulo"] if isinstance(x, dict) and x.get("ePrincipal", False) else None)
        .dropna()
        .value_counts()
        .reset_index()
    )
    df_assuntos.columns = ["Assunto", "Total"]
    return df_assuntos


def prepare_date_column(df, column):
    df[column] = pd.to_datetime(df[column], errors="coerce")
    df[column] = df[column].dt.strftime("%Y")
    return df

def add_year_column(df, date_column="dataDistribuicao"):
    if date_column in df.columns:
        df["Ano"] = pd.to_datetime(df[date_column], errors="coerce").dt.year
    return df


@st.cache_data
def extract_data(df, term):
    data = {}

    # ========================== Preparar Datas ====================================================================

    df = prepare_date_column(df, "dataDistribuicao")
    df = prepare_date_column(df, "statusPredictus.dataArquivamento")

    # ========================== Separar ativo e Passivo ===========================================================

    df_ativo = df[
        df["partes"].apply(
            lambda partes: any(
                p.get("polo") == "ATIVO" and p.get("cnpj") == term for p in partes
            )
        )
    ]

    df_passivo = df[
        df["partes"].apply(
            lambda partes: any(
                p.get("polo") == "PASSIVO" and p.get("cnpj") == term for p in partes
            )
        )
    ]

    # ========================== Arquivados x Distribuídos =========================================================

    data.update(
        {
            "dist_arq": extract_dist_vs_arq(df),
        }
    )

    # ========================== Indicadores Gerais ================================================================
    data.update(
        {
            "qtd_processos": df.shape[0],
            "qtd_polo_ativo": df_ativo.shape[0],
            "qtd_polo_passivo": df_passivo.shape[0],
            "valor_causa": df["valorCausa.valor"].sum(),
            "valor_causa_ativo": df_ativo["valorCausa.valor"].sum(),
            "valor_causa_passivo": df_passivo["valorCausa.valor"].sum(),
            "valor_execucao": df["statusPredictus.valorExecucao.valor"].sum(),
            "valor_execucao_ativo": df_ativo[
                "statusPredictus.valorExecucao.valor"
            ].sum(),
            "valor_execucao_passivo": df_passivo[
                "statusPredictus.valorExecucao.valor"
            ].sum(),
        }
    )

    # ========================== Distribuições =====================================================================
    data.update(
        {
            "distribuicao_ramo_direito": extract_distribution_by_column(
                df, "statusPredictus.ramoDireito", ["Ramo", "Total"], True,
            ),

            "distribuicao_status_processos": extract_distribution_by_column(
                df, "statusPredictus.statusProcesso", ["Status", "Total"]
            ),

            "distribuicao_tribunal": extract_distribution_by_column(
                df, "tribunal", ["Tribunal", "Total"], True,
            ),

            "distribuicao_julgamento": extract_distribution_by_column(
                df["statusPredictus.julgamentos"]
                .explode()
                .dropna()
                .apply(pd.Series),
                "tipoJulgamento",
                ["Julgamento", "Total"],
            ),

            "distribuicao_classes": extract_distribution_by_column(
                df, "classeProcessual.nome", ["Classe Processual", "Total"], True
            ),

            "distribuicao_segmento": extract_distribution_by_column(
                df, "segmento", ['Segmento', 'Total'], True,
            ),

            "distribuicao_grau": extract_distribution_by_column(
                df, "grauProcesso", ["Grau", "Total"]
            ),

            "distribuicao_assuntos": extract_distribution_by_column(
                df, "assuntosCNJ", ["Assunto", "Total"]
            )
        }
    )

    # ========================== Rankings ==========================================================================

    data.update(
        {
            "assuntos_principais": extract_top_principal_subjects(df, True),
            "assuntos_principais_ano": extract_principal_subjects_per_year(df),
            "top_10_partes": extract_top_parties(df, 10),
        },
    )

    # ========================== Dados para Mapa ===================================================================

    data.update(
        {
            "df_estado": extract_distribution_by_column(
                df, "uf", ["UF", "Total"],

            ),
        }
    )

    return data


def create_horizontal_bar_chart(data, title, x_col, y_col):
    with st.container(border=1):
        st.subheader(title)
        chart = px.bar(
            data,
            x=x_col,
            y=y_col,
            text=x_col,
            orientation="h",
            color_discrete_sequence=["#45A874"],
            labels={y_col: "", x_col: ""},
        )
        st.plotly_chart(chart, use_container_width=True)


def create_card(title, total_value, ativo_value, passivo_value, format_func=None):
    formatted_total = format_func(total_value) if format_func else f"{total_value:n}"
    with st.container(border=1):
        st.markdown(
            f"<h1 style='color: #21332C;'>{formatted_total}</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(title)
        formatted_ativo = (
            format_func(ativo_value) if format_func else f"{ativo_value:n}"
        )
        st.markdown(f"{formatted_ativo} como autor")
        st.progress(ativo_value / total_value if total_value else 0)
        formatted_passivo = (
            format_func(passivo_value) if format_func else f"{passivo_value:n}"
        )
        st.markdown(f"{formatted_passivo} como réu")
        st.progress(passivo_value / total_value if total_value else 0)


def create_donut_chart(data, title, names_col, values_col):
    with st.container(border=1):
        st.subheader(title)

        base_palette = [
            "#45A874",  # Verde Claro
            "#B49F74",  # Dourado
            "#DCD2BD",  # Bege
            "#2A4C3F",  # Verde
            "#F4F3EE",  # Off-White
        ]

        chart = px.pie(
            data,
            names=names_col,
            values=values_col,
            color_discrete_sequence=base_palette,
            hole=0.3,
        )
        # chart.update_traces(textinfo="label+percent+value")
        st.plotly_chart(chart, use_container_width=True)


def create_choropleth_map(
    data, geojson, locations_col, featureidkey, color_col, hover_col, title
):
    with st.container(border=1):
        st.subheader(title)
        mapa = px.choropleth(
            data,
            geojson=geojson,
            locations=locations_col,
            featureidkey=featureidkey,
            color=color_col,
            hover_name=hover_col,
            color_continuous_scale=[
                "rgba(69, 168, 116, 0.1)",
                "#45A874",
                "#2A4C3F",
                "#21332C",
            ],
        )
        mapa.update_geos(
            fitbounds="locations", visible=True, showcoastlines=False, showcountries=False
        )
        mapa.update_traces(marker_line_width=0.5)
        st.plotly_chart(mapa, use_container_width=True)


def create_ranking_chart(data, title, x_col, y_col):
    fig = px.bar(
        data,
        x=x_col,
        y=y_col,
        text=y_col,
        labels={x_col: "", y_col: "Percentual"},
        color_discrete_sequence=["#45A874"],
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(
        title=title,
        xaxis_title=None,
        yaxis_title="Percentual",
        showlegend=False,
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def create_dataframe(subheader, df, height):
    with st.container(border=1):
        st.subheader(subheader)

        styled_df = df.style.set_properties(
            **{
                "background-color": "white",
                "color": "black",
                "border": "1px solid black",
            }
        )

        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=height)


def create_table(subheader, df):
    st.subheader(subheader)
    st.table(df)

def create_vertical_bar_chart(df):
    with st.container(border=1):
        st.subheader(f"Processos Distribuídos x Processos Arquivados - Por Ano")
        fig = px.bar(
            df,
            x="Ano",
            y=["Distribuídos", "Arquivados"],
            barmode="group",
            text_auto=True,
            labels={"Ano": "Ano", "value": "Total de Processos", "variable": "Status"},
            color_discrete_sequence=["#45A874", "#2A4C3F"]
        )
        fig.update_xaxes(tickangle=45, categoryorder="category ascending")
        st.plotly_chart(fig, use_container_width=True)


def create_principal_subject_chart(df_assunto, key_prefix="assuntos"):
    anos_disponiveis = sorted(df_assunto["Ano"].unique(), reverse=True) if "Ano" in df_assunto.columns else []

    ano_selecionado = anos_disponiveis[0] if anos_disponiveis else None

    st.subheader(f"Principais Assuntos" + (f" em {ano_selecionado}" if ano_selecionado else ""))
    with st.container(border=1):
        if anos_disponiveis:
            ano_selecionado = st.selectbox(
                "Selecione o ano",
                anos_disponiveis,
                index=0,
                key=f"ano_selecionado_{key_prefix}"
            )
            df_filtered = df_assunto[df_assunto["Ano"] == ano_selecionado]
        else:
            df_filtered = df_assunto

        fig = px.bar(
            df_filtered,
            x="Assunto",
            y="Total",
            text="Total",
            labels={"Assunto": "Assunto", "Total": "Total"},
            color_discrete_sequence=["#45A874"],
            title=f"Principais Assuntos" + (f" em {ano_selecionado}" if ano_selecionado else "")
        )
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)


def render_dashboard(df, term):

    st.set_page_config(
        layout="wide",
        page_title="Visão Geral",
        page_icon="📊",
    )

    data = extract_data(df, term)

    st.markdown(
        "<h1 style='text-align: center;'>Visão Geral</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        create_card(
            "Processos encontrados",
            data["qtd_processos"],
            data["qtd_polo_ativo"],
            data["qtd_polo_passivo"],
        )

    with col2:
        create_card(
            "Valor das causas",
            data["valor_causa"],
            data["valor_causa_ativo"],
            data["valor_causa_passivo"],
            format_func=format_currency_brl,
        )

    with col3:
        create_card(
            "Valor das execuções",
            data["valor_execucao"],
            data["valor_execucao_ativo"],
            data["valor_execucao_passivo"],
            format_func=format_currency_brl,
        )

    with col1:
        create_horizontal_bar_chart(
            data["distribuicao_status_processos"],
            "Distribuição por Status do Processo",
            "Total",
            "Status",
        )

    with col2:
        create_donut_chart(
            data["distribuicao_ramo_direito"],
            "Distribuição por Ramo do Direito",
            "Ramo",
            "Total",
        )

    with col3:
        create_donut_chart(
            data["distribuicao_tribunal"],
            "Distribuição por Tribunal",
            "Tribunal",
            "Total",
        )


    with col1:
        create_horizontal_bar_chart(
            data["distribuicao_julgamento"],
            "Distribuição por Tipo de Julgamento",
            "Total",
            "Julgamento",
        )

    with col2:
        create_donut_chart(
            data["distribuicao_segmento"],
            "Distribuição por Segmento",
            "Segmento",
            "Total"
        )

    with col3:
        create_donut_chart(
            data["distribuicao_grau"],
            "Distribuição por Grau",
            "Grau",
            "Total",
        )


    col1, col2 = st.columns(2)

    with col1:
        create_dataframe("Assuntos Principais", data["assuntos_principais"], 245)

        create_choropleth_map(
            data["df_estado"],
            load_geojson('resource/brazil_states.geojson'),
            "UF",
            "properties.sigla",
            "Total",
            "UF",
            "Distribuição de Processo por Estado",
        )

        create_dataframe("Principais 10 Partes Envolvidas", data["top_10_partes"], 385)

    with col2:
        create_dataframe("Distribuição Por Classe Processual", data['distribuicao_classes'], 245)

        create_vertical_bar_chart(data['dist_arq'])

        create_dataframe("Principais 3 Assuntos por Ano", data["assuntos_principais_ano"], 385)





def main():
    arquivos_json = [
        "resource/dados_empresa1.json",
        "resource/dados_empresa2.json",
        "resource/dados_empresa3.json",
    ]

    # arquivos_json = [
    #     "src/dados_empresa1.json",
    # ]

    df = load_data(arquivos_json)

    term = "00000000000191"

    render_dashboard(df, term)


if __name__ == "__main__":
    main()
