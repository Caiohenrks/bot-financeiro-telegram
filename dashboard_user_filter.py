import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import calendar
from dotenv import load_dotenv
import os
import warnings
from sklearn.linear_model import LinearRegression

# Suprimir avisos de depreciação do pandas
warnings.filterwarnings('ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações do banco de dados
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Função para conectar ao banco de dados
def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

# Função para obter lista de usuários
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT id, first_name, username
            FROM usuarios
            ORDER BY first_name
        """)
        users = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return users
    except Exception as e:
        print(f"Erro ao obter usuários: {e}")
        # Retornar uma lista vazia em caso de erro
        return []

# Função para obter dados de receitas e despesas com filtro de usuário
def get_financial_data(user_id=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obter receitas
        if user_id:
            cursor.execute("""
                SELECT id, usuario_id, descricao, categoria, fonte, valor, data, created_at
                FROM receitas
                WHERE usuario_id = %s
                ORDER BY data DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, usuario_id, descricao, categoria, fonte, valor, data, created_at
                FROM receitas
                ORDER BY data DESC
            """)
        receitas = cursor.fetchall()
        
        # Obter despesas
        if user_id:
            cursor.execute("""
                SELECT id, usuario_id, descricao, categoria, forma_pagamento, valor, data, created_at
                FROM despesas
                WHERE usuario_id = %s
                ORDER BY data DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, usuario_id, descricao, categoria, forma_pagamento, valor, data, created_at
                FROM despesas
                ORDER BY data DESC
            """)
        despesas = cursor.fetchall()
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao obter dados financeiros: {e}")
        receitas = []
        despesas = []
    
    # Converter para DataFrames
    df_receitas = pd.DataFrame(receitas) if receitas else pd.DataFrame(columns=['id', 'usuario_id', 'descricao', 'categoria', 'fonte', 'valor', 'data', 'created_at'])
    df_despesas = pd.DataFrame(despesas) if despesas else pd.DataFrame(columns=['id', 'usuario_id', 'descricao', 'categoria', 'forma_pagamento', 'valor', 'data', 'created_at'])
    
    # Adicionar tipo para facilitar a identificação
    if not df_receitas.empty:
        df_receitas['tipo'] = 'Receita'
    if not df_despesas.empty:
        df_despesas['tipo'] = 'Despesa'
    
    return df_receitas, df_despesas

# Função para calcular resumo financeiro
def get_financial_summary(df_receitas, df_despesas):
    # Total de receitas
    total_receitas = df_receitas['valor'].sum() if not df_receitas.empty else 0
    
    # Total de despesas
    total_despesas = df_despesas['valor'].sum() if not df_despesas.empty else 0
    
    # Saldo
    saldo = total_receitas - total_despesas
    
    # Percentual de gastos em relação à receita
    percentual_gastos = (total_despesas / total_receitas * 100) if total_receitas > 0 else 0
    
    return {
        'total_receitas': total_receitas,
        'total_despesas': total_despesas,
        'saldo': saldo,
        'percentual_gastos': percentual_gastos
    }

# Função para agrupar despesas por categoria
def group_expenses_by_category(df_despesas):
    if df_despesas.empty:
        return pd.DataFrame()
    
    # Agrupar por categoria
    df_grouped = df_despesas.groupby('categoria').agg({'valor': 'sum'}).reset_index()
    
    return df_grouped

# Função para agrupar receitas por fonte
def group_income_by_source(df_receitas):
    if df_receitas.empty:
        return pd.DataFrame()
    
    # Agrupar por fonte
    df_grouped = df_receitas.groupby('fonte').agg({'valor': 'sum'}).reset_index()
    
    return df_grouped

# Função para agrupar despesas por mês
def group_expenses_by_month(df_despesas):
    if df_despesas.empty:
        return pd.DataFrame()
    
    # Converter coluna de data para datetime
    df_despesas['data'] = pd.to_datetime(df_despesas['data'])
    
    # Agrupar por mês
    df_despesas['mes'] = df_despesas['data'].dt.strftime('%Y-%m')
    df_grouped = df_despesas.groupby('mes').agg({'valor': 'sum'}).reset_index()
    
    return df_grouped

# Função para agrupar receitas por mês
def group_income_by_month(df_receitas):
    if df_receitas.empty:
        return pd.DataFrame()
    
    # Converter coluna de data para datetime
    df_receitas['data'] = pd.to_datetime(df_receitas['data'])
    
    # Agrupar por mês
    df_receitas['mes'] = df_receitas['data'].dt.strftime('%Y-%m')
    df_grouped = df_receitas.groupby('mes').agg({'valor': 'sum'}).reset_index()
    
    return df_grouped

# Função para agrupar por ano
def group_by_year(df):
    if df.empty:
        return pd.DataFrame()
    
    # Converter coluna de data para datetime
    df['data'] = pd.to_datetime(df['data'])
    
    # Agrupar por ano
    df['ano'] = df['data'].dt.year
    df_grouped = df.groupby('ano').agg({'valor': 'sum'}).reset_index()
    
    return df_grouped

# Função para obter as categorias com maiores gastos
def get_top_expense_categories(df_despesas, top_n=5):
    if df_despesas.empty:
        return pd.DataFrame()
    
    # Agrupar por categoria
    df_grouped = df_despesas.groupby('categoria').agg({'valor': 'sum'}).reset_index()
    
    # Ordenar por valor e pegar os top_n
    df_grouped = df_grouped.sort_values('valor', ascending=False).head(top_n)
    
    return df_grouped

# Função para obter as fontes com maiores receitas
def get_top_income_sources(df_receitas, top_n=5):
    if df_receitas.empty:
        return pd.DataFrame()
    
    # Agrupar por fonte
    df_grouped = df_receitas.groupby('fonte').agg({'valor': 'sum'}).reset_index()
    
    # Ordenar por valor e pegar os top_n
    df_grouped = df_grouped.sort_values('valor', ascending=False).head(top_n)
    
    return df_grouped

# Função para calcular a relação ganhos x despesas
def calculate_income_expense_ratio(df_receitas, df_despesas):
    if df_receitas.empty or df_despesas.empty:
        return pd.DataFrame()
    
    # Converter coluna de data para datetime
    df_receitas['data'] = pd.to_datetime(df_receitas['data'])
    df_despesas['data'] = pd.to_datetime(df_despesas['data'])
    
    # Agrupar por mês
    df_receitas['mes'] = df_receitas['data'].dt.strftime('%Y-%m')
    df_despesas['mes'] = df_despesas['data'].dt.strftime('%Y-%m')
    
    df_receitas_mensal = df_receitas.groupby('mes').agg({'valor': 'sum'}).reset_index()
    df_despesas_mensal = df_despesas.groupby('mes').agg({'valor': 'sum'}).reset_index()
    
    # Mesclar receitas e despesas
    df_merged = pd.merge(df_receitas_mensal, df_despesas_mensal, on='mes', how='outer', suffixes=('_receita', '_despesa'))
    df_merged = df_merged.fillna(0)
    
    # Calcular relação (receita / despesa)
    df_merged['relacao'] = df_merged['valor_receita'] / df_merged['valor_despesa'].replace(0, np.nan)
    df_merged['relacao'] = df_merged['relacao'].fillna(0)
    
    return df_merged

# Cores para o tema escuro
colors = {
    'background': '#1E2130',
    'card_background': '#252E3F',
    'text': '#FFFFFF',
    'primary': '#4DA6FF',
    'secondary': '#FF6B9D',
    'success': '#00CC96',
    'danger': '#FF6B6B',
    'warning': '#FFA15A',
    'info': '#39C0C8',
    'grid': '#323848',
    'chart_colors': ['#4DA6FF', '#FF6B9D', '#00CC96', '#FFA15A', '#39C0C8', '#FF6B6B']
}

# Inicializar o app Dash com tema escuro personalizado
app = dash.Dash(
    __name__, 
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.CYBORG],  # Tema escuro do Bootstrap
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ]
)
server = app.server

# Estilo global
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Dashboard Financeiro</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background-color: ''' + colors['background'] + ''';
                color: ''' + colors['text'] + ''';
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .card {
                background-color: ''' + colors['card_background'] + ''';
                border: none;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                margin-bottom: 20px;
            }
            .card-header {
                background-color: rgba(0, 0, 0, 0.2);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                font-weight: bold;
                color: ''' + colors['text'] + ''';
            }
            .value-card {
                font-size: 2.5rem;
                font-weight: bold;
                text-align: center;
                padding: 20px;
            }
            .value-title {
                font-size: 1.2rem;
                text-align: center;
                opacity: 0.8;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Obter lista de usuários para o dropdown
users = get_users()
user_options = [{'label': 'Todos os usuários', 'value': 'all'}]
for user in users:
    display_name = user['first_name'] or user['username'] or f"Usuário {user['id']}"
    user_options.append({'label': display_name, 'value': user['id']})

# Layout do app
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("Dashboard Financeiro", 
                        className="text-center my-4",
                        style={
                            'font-size': '3rem',
                            'font-weight': 'bold',
                            'color': colors['primary'],
                            'text-shadow': '2px 2px 4px rgba(0, 0, 0, 0.5)',
                            'letter-spacing': '1px',
                            'padding': '20px 0',
                            'border-bottom': f'2px solid {colors["secondary"]}',
                            'margin-bottom': '30px'
                        })
            ], style={'background': 'linear-gradient(90deg, rgba(37, 46, 63, 0.8) 0%, rgba(77, 166, 255, 0.2) 50%, rgba(37, 46, 63, 0.8) 100%)'})
        ])
    ]),
    
    # Filtro de usuário
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Filtrar por Usuário"),
                dbc.CardBody([
                    dcc.Dropdown(
                        id='user-filter-dropdown',
                        options=user_options,
                        value='all',
                        clearable=False,
                        style={
                            'backgroundColor': colors['card_background'],
                            'color': '#000000',
                            'border': f'1px solid {colors["primary"]}'
                        }
                    )
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            dcc.Interval(
                id='interval-component',
                interval=60*1000,  # atualizar a cada 1 minuto
                n_intervals=0
            ),
            
            dbc.Tabs([
                # Aba de Visão Geral
                dbc.Tab(label="Visão Geral", tab_id="tab-overview", children=[
                    # Cards de resumo
                    html.Div(id='summary-cards', className="mb-4"),
                    
                    # Gráficos
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Despesas por Categoria"),
                                dbc.CardBody([
                                    dcc.Graph(id='despesas-categoria-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6),
                        
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Receitas por Fonte"),
                                dbc.CardBody([
                                    dcc.Graph(id='receitas-fonte-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6)
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Receitas vs Despesas"),
                                dbc.CardBody([
                                    dcc.Graph(id='receitas-despesas-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6),
                        
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Saldo Acumulado"),
                                dbc.CardBody([
                                    dcc.Graph(id='saldo-acumulado-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6)
                    ])
                ], className="p-3"),
                
                # Aba de Análise Detalhada
                dbc.Tab(label="Análise Detalhada", tab_id="tab-analysis", children=[
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Categorias com Maiores Gastos"),
                                dbc.CardBody([
                                    dcc.Graph(id='maiores-gastos-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6),
                        
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Fontes com Maiores Receitas"),
                                dbc.CardBody([
                                    dcc.Graph(id='maiores-receitas-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6)
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Gastos por Mês"),
                                dbc.CardBody([
                                    dcc.Graph(id='gastos-mes-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6),
                        
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Receitas por Mês"),
                                dbc.CardBody([
                                    dcc.Graph(id='receitas-mes-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ], width=6)
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Comparativo Anual"),
                                dbc.CardBody([
                                    dcc.Graph(id='comparativo-anual-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ])
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Relação Ganhos x Despesas"),
                                dbc.CardBody([
                                    dcc.Graph(id='relacao-ganhos-despesas-graph', style={"height": "400px"})
                                ])
                            ], className="mb-4")
                        ])
                    ])
                ], className="p-3"),
                
                # Aba de Simuladores
                dbc.Tab(label="Simuladores", tab_id="tab-simulators", children=[
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Simulador de Investimentos"),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.H5("Parâmetros", className="mb-3"),
                                            dbc.Form([
                                                dbc.Row([
                                                    dbc.Col([
                                                        dbc.Label("Valor Inicial (R$)"),
                                                        dbc.Input(
                                                            id="investimento-inicial",
                                                            type="number",
                                                            min=0,
                                                            step=100,
                                                            value=1000,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Aporte Mensal (R$)"),
                                                        dbc.Input(
                                                            id="aporte-mensal",
                                                            type="number",
                                                            min=0,
                                                            step=100,
                                                            value=200,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Row([
                                                    dbc.Col([
                                                        dbc.Label("Taxa de Juros Anual (%)"),
                                                        dbc.Input(
                                                            id="taxa-juros",
                                                            type="number",
                                                            min=0,
                                                            step=0.5,
                                                            value=10,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Período (anos)"),
                                                        dbc.Input(
                                                            id="periodo-anos",
                                                            type="number",
                                                            min=1,
                                                            max=50,
                                                            step=1,
                                                            value=10,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Button(
                                                    "Calcular",
                                                    id="calcular-investimento",
                                                    color="primary",
                                                    className="mt-3"
                                                )
                                            ])
                                        ], width=4),
                                        dbc.Col([
                                            html.H5("Resultado", className="mb-3"),
                                            html.Div(id="resultado-investimento"),
                                            dcc.Graph(id="grafico-investimento", style={"height": "400px"})
                                        ], width=8)
                                    ])
                                ])
                            ], className="mb-4")
                        ])
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Simulador de Metas Financeiras"),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.H5("Parâmetros", className="mb-3"),
                                            dbc.Form([
                                                dbc.Row([
                                                    dbc.Col([
                                                        dbc.Label("Valor da Meta (R$)"),
                                                        dbc.Input(
                                                            id="valor-meta",
                                                            type="number",
                                                            min=1000,
                                                            step=1000,
                                                            value=50000,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Valor Inicial (R$)"),
                                                        dbc.Input(
                                                            id="valor-inicial-meta",
                                                            type="number",
                                                            min=0,
                                                            step=100,
                                                            value=5000,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Row([
                                                    dbc.Col([
                                                        dbc.Label("Taxa de Juros Anual (%)"),
                                                        dbc.Input(
                                                            id="taxa-juros-meta",
                                                            type="number",
                                                            min=0,
                                                            step=0.5,
                                                            value=8,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Prazo (meses)"),
                                                        dbc.Input(
                                                            id="prazo-meta",
                                                            type="number",
                                                            min=1,
                                                            max=600,
                                                            step=1,
                                                            value=60,
                                                            style={"backgroundColor": colors['card_background'], "color": colors['text']}
                                                        )
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Button(
                                                    "Calcular",
                                                    id="calcular-meta",
                                                    color="primary",
                                                    className="mt-3"
                                                )
                                            ])
                                        ], width=4),
                                        dbc.Col([
                                            html.H5("Resultado", className="mb-3"),
                                            html.Div(id="resultado-meta"),
                                            dcc.Graph(id="grafico-meta", style={"height": "400px"})
                                        ], width=8)
                                    ])
                                ])
                            ], className="mb-4")
                        ])
                    ])
                ], className="p-3")
            ], id="tabs", active_tab="tab-overview")
        ])
    ]),
    
    html.Footer([
        html.P("Dashboard Financeiro © 2025", className="text-center mt-4 text-muted")
    ])
], fluid=True, style={"backgroundColor": colors['background'], "minHeight": "100vh"})

# Callback para atualizar os cards de resumo
@app.callback(
    Output('summary-cards', 'children'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_summary_cards(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, df_despesas = get_financial_data(user_id_filter)
    
    # Calcular resumo financeiro
    summary = get_financial_summary(df_receitas, df_despesas)
    
    # Criar cards
    cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                html.Div("Total de Receitas", className="value-title"),
                html.Div(f"R$ {summary['total_receitas']:,.2f}", className="value-card", style={"color": colors['success']})
            ], className="text-center")
        ], width=3),
        
        dbc.Col([
            dbc.Card([
                html.Div("Total de Despesas", className="value-title"),
                html.Div(f"R$ {summary['total_despesas']:,.2f}", className="value-card", style={"color": colors['danger']})
            ], className="text-center")
        ], width=3),
        
        dbc.Col([
            dbc.Card([
                html.Div("Saldo", className="value-title"),
                html.Div(
                    f"R$ {summary['saldo']:,.2f}", 
                    className="value-card", 
                    style={"color": colors['success'] if summary['saldo'] >= 0 else colors['danger']}
                )
            ], className="text-center")
        ], width=3),
        
        dbc.Col([
            dbc.Card([
                html.Div("% de Gastos", className="value-title"),
                html.Div(
                    f"{summary['percentual_gastos']:.1f}%", 
                    className="value-card", 
                    style={
                        "color": colors['success'] if summary['percentual_gastos'] < 80 else 
                                colors['warning'] if summary['percentual_gastos'] < 100 else 
                                colors['danger']
                    }
                )
            ], className="text-center")
        ], width=3)
    ])
    
    return cards

# Callback para o gráfico de despesas por categoria
@app.callback(
    Output('despesas-categoria-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_expense_category_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    _, df_despesas = get_financial_data(user_id_filter)
    
    # Agrupar despesas por categoria
    df_grouped = group_expenses_by_category(df_despesas)
    
    if df_grouped.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados de despesas",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar gráfico de pizza
    fig = px.pie(
        df_grouped, 
        values='valor', 
        names='categoria',
        color_discrete_sequence=colors['chart_colors'],
        hole=0.4
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>R$ %{value:.2f}<br>%{percent}'
    )
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

# Callback para o gráfico de receitas por fonte
@app.callback(
    Output('receitas-fonte-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_income_source_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, _ = get_financial_data(user_id_filter)
    
    # Agrupar receitas por fonte
    df_grouped = group_income_by_source(df_receitas)
    
    if df_grouped.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados de receitas",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar gráfico de pizza
    fig = px.pie(
        df_grouped, 
        values='valor', 
        names='fonte',
        color_discrete_sequence=colors['chart_colors'],
        hole=0.4
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>R$ %{value:.2f}<br>%{percent}'
    )
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

# Callback para o gráfico de receitas vs despesas
@app.callback(
    Output('receitas-despesas-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_income_expense_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, df_despesas = get_financial_data(user_id_filter)
    
    # Agrupar por mês
    df_receitas_mensal = group_income_by_month(df_receitas)
    df_despesas_mensal = group_expenses_by_month(df_despesas)
    
    if df_receitas_mensal.empty and df_despesas_mensal.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados para exibir",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar figura
    fig = go.Figure()
    
    # Adicionar barras de receitas
    if not df_receitas_mensal.empty:
        fig.add_trace(go.Bar(
            x=df_receitas_mensal['mes'],
            y=df_receitas_mensal['valor'],
            name='Receitas',
            marker_color=colors['success'],
            hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
        ))
    
    # Adicionar barras de despesas
    if not df_despesas_mensal.empty:
        fig.add_trace(go.Bar(
            x=df_despesas_mensal['mes'],
            y=df_despesas_mensal['valor'],
            name='Despesas',
            marker_color=colors['danger'],
            hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
        ))
    
    # Atualizar layout
    fig.update_layout(
        barmode='group',
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title="Mês",
            tickangle=-45,
            tickformat="%b %Y"
        ),
        yaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return fig

# Callback para o gráfico de saldo acumulado
@app.callback(
    Output('saldo-acumulado-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_accumulated_balance_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, df_despesas = get_financial_data(user_id_filter)
    
    if df_receitas.empty and df_despesas.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados para exibir",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Converter datas para datetime
    if not df_receitas.empty:
        df_receitas['data'] = pd.to_datetime(df_receitas['data'])
    if not df_despesas.empty:
        df_despesas['data'] = pd.to_datetime(df_despesas['data'])
    
    # Criar DataFrame com todas as datas
    all_dates = pd.DataFrame()
    
    if not df_receitas.empty:
        receitas_por_data = df_receitas.groupby('data')['valor'].sum().reset_index()
        receitas_por_data['tipo'] = 'receita'
        all_dates = pd.concat([all_dates, receitas_por_data[['data', 'valor', 'tipo']]])
    
    if not df_despesas.empty:
        despesas_por_data = df_despesas.groupby('data')['valor'].sum().reset_index()
        despesas_por_data['tipo'] = 'despesa'
        all_dates = pd.concat([all_dates, despesas_por_data[['data', 'valor', 'tipo']]])
    
    # Ordenar por data
    all_dates = all_dates.sort_values('data')
    
    # Calcular saldo acumulado
    saldo_acumulado = []
    saldo = 0
    
    for _, row in all_dates.iterrows():
        if row['tipo'] == 'receita':
            saldo += row['valor']
        else:
            saldo -= row['valor']
        saldo_acumulado.append(saldo)
    
    all_dates['saldo_acumulado'] = saldo_acumulado
    
    # Agrupar por mês para simplificar o gráfico
    all_dates['mes'] = all_dates['data'].dt.strftime('%Y-%m')
    saldo_mensal = all_dates.groupby('mes').tail(1)[['mes', 'saldo_acumulado']]
    
    # Criar figura
    fig = go.Figure()
    
    # Adicionar linha de saldo acumulado
    fig.add_trace(go.Scatter(
        x=saldo_mensal['mes'],
        y=saldo_mensal['saldo_acumulado'],
        mode='lines+markers',
        name='Saldo Acumulado',
        line=dict(color=colors['primary'], width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
    ))
    
    # Adicionar linha de referência (zero)
    fig.add_shape(
        type="line",
        x0=saldo_mensal['mes'].iloc[0],
        y0=0,
        x1=saldo_mensal['mes'].iloc[-1],
        y1=0,
        line=dict(
            color="gray",
            width=1,
            dash="dash",
        )
    )
    
    # Atualizar layout
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            title="Mês",
            tickangle=-45
        ),
        yaxis=dict(
            title="Saldo Acumulado (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return fig

# Callback para o gráfico de categorias com maiores gastos
@app.callback(
    Output('maiores-gastos-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_top_expenses_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    _, df_despesas = get_financial_data(user_id_filter)
    
    # Obter top categorias
    df_top = get_top_expense_categories(df_despesas)
    
    if df_top.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados de despesas",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar gráfico de barras horizontais
    fig = px.bar(
        df_top,
        y='categoria',
        x='valor',
        orientation='h',
        color='categoria',
        color_discrete_sequence=colors['chart_colors'],
        text='valor'
    )
    
    fig.update_traces(
        texttemplate='R$ %{x:.2f}',
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>R$ %{x:.2f}'
    )
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        ),
        yaxis=dict(
            title="",
            categoryorder='total ascending'
        ),
        showlegend=False
    )
    
    return fig

# Callback para o gráfico de fontes com maiores receitas
@app.callback(
    Output('maiores-receitas-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_top_income_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, _ = get_financial_data(user_id_filter)
    
    # Obter top fontes
    df_top = get_top_income_sources(df_receitas)
    
    if df_top.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados de receitas",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar gráfico de barras horizontais
    fig = px.bar(
        df_top,
        y='fonte',
        x='valor',
        orientation='h',
        color='fonte',
        color_discrete_sequence=colors['chart_colors'],
        text='valor'
    )
    
    fig.update_traces(
        texttemplate='R$ %{x:.2f}',
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>R$ %{x:.2f}'
    )
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        ),
        yaxis=dict(
            title="",
            categoryorder='total ascending'
        ),
        showlegend=False
    )
    
    return fig

# Callback para o gráfico de gastos por mês
@app.callback(
    Output('gastos-mes-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_monthly_expenses_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    _, df_despesas = get_financial_data(user_id_filter)
    
    # Agrupar por mês
    df_mensal = group_expenses_by_month(df_despesas)
    
    if df_mensal.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados de despesas",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar gráfico de linha
    fig = px.line(
        df_mensal,
        x='mes',
        y='valor',
        markers=True,
        line_shape='spline',
        color_discrete_sequence=[colors['danger']]
    )
    
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
    )
    
    # Adicionar média móvel
    if len(df_mensal) > 2:
        df_mensal['media_movel'] = df_mensal['valor'].rolling(window=3, min_periods=1).mean()
        
        fig.add_trace(go.Scatter(
            x=df_mensal['mes'],
            y=df_mensal['media_movel'],
            mode='lines',
            name='Média Móvel (3 meses)',
            line=dict(color=colors['warning'], width=2, dash='dash'),
            hovertemplate='<b>%{x}</b><br>Média: R$ %{y:.2f}'
        ))
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title="Mês",
            tickangle=-45
        ),
        yaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return fig

# Callback para o gráfico de receitas por mês
@app.callback(
    Output('receitas-mes-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_monthly_income_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, _ = get_financial_data(user_id_filter)
    
    # Agrupar por mês
    df_mensal = group_income_by_month(df_receitas)
    
    if df_mensal.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados de receitas",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar gráfico de linha
    fig = px.line(
        df_mensal,
        x='mes',
        y='valor',
        markers=True,
        line_shape='spline',
        color_discrete_sequence=[colors['success']]
    )
    
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
    )
    
    # Adicionar média móvel
    if len(df_mensal) > 2:
        df_mensal['media_movel'] = df_mensal['valor'].rolling(window=3, min_periods=1).mean()
        
        fig.add_trace(go.Scatter(
            x=df_mensal['mes'],
            y=df_mensal['media_movel'],
            mode='lines',
            name='Média Móvel (3 meses)',
            line=dict(color=colors['info'], width=2, dash='dash'),
            hovertemplate='<b>%{x}</b><br>Média: R$ %{y:.2f}'
        ))
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title="Mês",
            tickangle=-45
        ),
        yaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return fig

# Callback para o gráfico comparativo anual
@app.callback(
    Output('comparativo-anual-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_yearly_comparison_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, df_despesas = get_financial_data(user_id_filter)
    
    # Agrupar por ano
    df_receitas_anual = group_by_year(df_receitas)
    df_despesas_anual = group_by_year(df_despesas)
    
    if df_receitas_anual.empty and df_despesas_anual.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados para exibir",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar figura
    fig = go.Figure()
    
    # Adicionar barras de receitas
    if not df_receitas_anual.empty:
        fig.add_trace(go.Bar(
            x=df_receitas_anual['ano'].astype(str),
            y=df_receitas_anual['valor'],
            name='Receitas',
            marker_color=colors['success'],
            hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
        ))
    
    # Adicionar barras de despesas
    if not df_despesas_anual.empty:
        fig.add_trace(go.Bar(
            x=df_despesas_anual['ano'].astype(str),
            y=df_despesas_anual['valor'],
            name='Despesas',
            marker_color=colors['danger'],
            hovertemplate='<b>%{x}</b><br>R$ %{y:.2f}'
        ))
    
    # Atualizar layout
    fig.update_layout(
        barmode='group',
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title="Ano",
            tickangle=0
        ),
        yaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return fig

# Callback para o gráfico de relação ganhos x despesas
@app.callback(
    Output('relacao-ganhos-despesas-graph', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('user-filter-dropdown', 'value')]
)
def update_income_expense_ratio_graph(n_intervals, user_id):
    # Obter dados financeiros
    user_id_filter = None if user_id == 'all' else user_id
    df_receitas, df_despesas = get_financial_data(user_id_filter)
    
    # Calcular relação
    df_relacao = calculate_income_expense_ratio(df_receitas, df_despesas)
    
    if df_relacao.empty:
        # Retornar gráfico vazio
        fig = go.Figure()
        fig.update_layout(
            title="Sem dados suficientes para calcular a relação",
            template="plotly_dark",
            plot_bgcolor=colors['card_background'],
            paper_bgcolor=colors['card_background'],
            font=dict(color=colors['text']),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400
        )
        return fig
    
    # Criar figura
    fig = go.Figure()
    
    # Adicionar linha de relação
    fig.add_trace(go.Scatter(
        x=df_relacao['mes'],
        y=df_relacao['relacao'],
        mode='lines+markers',
        name='Relação Receita/Despesa',
        line=dict(color=colors['primary'], width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>Relação: %{y:.2f}'
    ))
    
    # Adicionar linha de referência (1.0)
    fig.add_shape(
        type="line",
        x0=df_relacao['mes'].iloc[0],
        y0=1,
        x1=df_relacao['mes'].iloc[-1],
        y1=1,
        line=dict(
            color="gray",
            width=1,
            dash="dash",
        )
    )
    
    # Atualizar layout
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            title="Mês",
            tickangle=-45
        ),
        yaxis=dict(
            title="Relação Receita/Despesa",
            gridcolor=colors['grid']
        )
    )
    
    return fig

# Callback para o simulador de investimentos
@app.callback(
    [Output('resultado-investimento', 'children'),
     Output('grafico-investimento', 'figure')],
    [Input('calcular-investimento', 'n_clicks')],
    [State('investimento-inicial', 'value'),
     State('aporte-mensal', 'value'),
     State('taxa-juros', 'value'),
     State('periodo-anos', 'value')]
)
def calcular_investimento(n_clicks, investimento_inicial, aporte_mensal, taxa_juros, periodo_anos):
    if n_clicks is None:
        # Valores padrão
        investimento_inicial = 1000
        aporte_mensal = 200
        taxa_juros = 10
        periodo_anos = 10
    
    # Converter taxa anual para mensal
    taxa_mensal = (1 + taxa_juros/100) ** (1/12) - 1
    
    # Calcular para cada mês
    meses = periodo_anos * 12
    valores = []
    valor_atual = investimento_inicial
    
    for i in range(meses + 1):
        if i > 0:  # Após o primeiro mês
            valor_atual = valor_atual * (1 + taxa_mensal) + aporte_mensal
        valores.append(valor_atual)
    
    # Valor final
    valor_final = valores[-1]
    total_investido = investimento_inicial + aporte_mensal * meses
    juros_ganhos = valor_final - total_investido
    
    # Criar resultado
    resultado = dbc.Card([
        dbc.CardBody([
            html.H5("Resultado da Simulação", className="card-title"),
            html.P([
                html.Strong("Valor Final: "), f"R$ {valor_final:,.2f}"
            ], className="card-text"),
            html.P([
                html.Strong("Total Investido: "), f"R$ {total_investido:,.2f}"
            ], className="card-text"),
            html.P([
                html.Strong("Juros Ganhos: "), f"R$ {juros_ganhos:,.2f}"
            ], className="card-text"),
            html.P([
                html.Strong("Rentabilidade: "), f"{(juros_ganhos/total_investido*100):,.2f}%"
            ], className="card-text")
        ])
    ])
    
    # Criar gráfico
    df = pd.DataFrame({
        'mes': range(meses + 1),
        'valor': valores,
        'investido': [investimento_inicial + aporte_mensal * i for i in range(meses + 1)]
    })
    
    fig = go.Figure()
    
    # Adicionar linha de valor acumulado
    fig.add_trace(go.Scatter(
        x=df['mes'],
        y=df['valor'],
        mode='lines',
        name='Valor Acumulado',
        line=dict(color=colors['primary'], width=3),
        hovertemplate='<b>Mês %{x}</b><br>R$ %{y:.2f}'
    ))
    
    # Adicionar linha de valor investido
    fig.add_trace(go.Scatter(
        x=df['mes'],
        y=df['investido'],
        mode='lines',
        name='Valor Investido',
        line=dict(color=colors['secondary'], width=3, dash='dash'),
        hovertemplate='<b>Mês %{x}</b><br>R$ %{y:.2f}'
    ))
    
    # Atualizar layout
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title="Mês",
            gridcolor=colors['grid']
        ),
        yaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return resultado, fig

# Callback para o simulador de metas financeiras
@app.callback(
    [Output('resultado-meta', 'children'),
     Output('grafico-meta', 'figure')],
    [Input('calcular-meta', 'n_clicks')],
    [State('valor-meta', 'value'),
     State('valor-inicial-meta', 'value'),
     State('taxa-juros-meta', 'value'),
     State('prazo-meta', 'value')]
)
def calcular_meta(n_clicks, valor_meta, valor_inicial, taxa_juros, prazo_meses):
    if n_clicks is None:
        # Valores padrão
        valor_meta = 50000
        valor_inicial = 5000
        taxa_juros = 8
        prazo_meses = 60
    
    # Converter taxa anual para mensal
    taxa_mensal = (1 + taxa_juros/100) ** (1/12) - 1
    
    # Calcular aporte mensal necessário
    # Fórmula: PMT = (FV - PV * (1 + r)^n) / (((1 + r)^n - 1) / r)
    if taxa_mensal > 0:
        aporte_mensal = (valor_meta - valor_inicial * (1 + taxa_mensal) ** prazo_meses) / (((1 + taxa_mensal) ** prazo_meses - 1) / taxa_mensal)
    else:
        aporte_mensal = (valor_meta - valor_inicial) / prazo_meses
    
    # Calcular para cada mês
    valores = []
    valor_atual = valor_inicial
    
    for i in range(prazo_meses + 1):
        if i > 0:  # Após o primeiro mês
            valor_atual = valor_atual * (1 + taxa_mensal) + aporte_mensal
        valores.append(valor_atual)
    
    # Valor final
    valor_final = valores[-1]
    total_investido = valor_inicial + aporte_mensal * prazo_meses
    juros_ganhos = valor_final - total_investido
    
    # Criar resultado
    resultado = dbc.Card([
        dbc.CardBody([
            html.H5("Resultado da Simulação", className="card-title"),
            html.P([
                html.Strong("Aporte Mensal Necessário: "), f"R$ {aporte_mensal:,.2f}"
            ], className="card-text"),
            html.P([
                html.Strong("Valor Final: "), f"R$ {valor_final:,.2f}"
            ], className="card-text"),
            html.P([
                html.Strong("Total Investido: "), f"R$ {total_investido:,.2f}"
            ], className="card-text"),
            html.P([
                html.Strong("Juros Ganhos: "), f"R$ {juros_ganhos:,.2f}"
            ], className="card-text")
        ])
    ])
    
    # Criar gráfico
    df = pd.DataFrame({
        'mes': range(prazo_meses + 1),
        'valor': valores,
        'meta': [valor_meta] * (prazo_meses + 1)
    })
    
    fig = go.Figure()
    
    # Adicionar linha de valor acumulado
    fig.add_trace(go.Scatter(
        x=df['mes'],
        y=df['valor'],
        mode='lines',
        name='Valor Acumulado',
        line=dict(color=colors['primary'], width=3),
        hovertemplate='<b>Mês %{x}</b><br>R$ %{y:.2f}'
    ))
    
    # Adicionar linha de meta
    fig.add_trace(go.Scatter(
        x=df['mes'],
        y=df['meta'],
        mode='lines',
        name='Meta',
        line=dict(color=colors['warning'], width=2, dash='dash'),
        hovertemplate='<b>Meta:</b> R$ %{y:.2f}'
    ))
    
    # Atualizar layout
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=colors['card_background'],
        paper_bgcolor=colors['card_background'],
        font=dict(color=colors['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title="Mês",
            gridcolor=colors['grid']
        ),
        yaxis=dict(
            title="Valor (R$)",
            gridcolor=colors['grid']
        )
    )
    
    return resultado, fig

# Iniciar o servidor
if __name__ == '__main__':
    # Obter a porta do arquivo .env ou usar 12000 como padrão
    port = int(os.getenv("DASHBOARD_PORT", "12000"))
    app.run(debug=True, host='0.0.0.0', port=port)