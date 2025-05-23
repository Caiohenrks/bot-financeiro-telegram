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

# Função para obter dados de receitas e despesas
def get_financial_data():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Obter receitas
    cursor.execute("""
        SELECT id, usuario_id, descricao, categoria, fonte, valor, data, created_at
        FROM receitas
        ORDER BY data DESC
    """)
    receitas = cursor.fetchall()
    
    # Obter despesas
    cursor.execute("""
        SELECT id, usuario_id, descricao, categoria, forma_pagamento, valor, data, created_at
        FROM despesas
        ORDER BY data DESC
    """)
    despesas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
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
                                                        dbc.Label("Valor inicial (R$)"),
                                                        dbc.Input(id="valor-inicial-input", type="number", value=1000, min=0, step=100)
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Aporte mensal (R$)"),
                                                        dbc.Input(id="aporte-mensal-input", type="number", value=200, min=0, step=50)
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Row([
                                                    dbc.Col([
                                                        dbc.Label("Taxa de juros anual (%)"),
                                                        dbc.Input(id="taxa-juros-input", type="number", value=10, min=0, max=100, step=0.5)
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Período (anos)"),
                                                        dbc.Input(id="periodo-input", type="number", value=5, min=1, max=50, step=1)
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Button("Calcular", id="calcular-investimento-button", color="primary", className="mt-3")
                                            ])
                                        ], width=4),
                                        dbc.Col([
                                            html.Div(id="resultado-investimento", className="p-3")
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
                                                        dbc.Label("Valor da meta (R$)"),
                                                        dbc.Input(id="valor-meta-input", type="number", value=50000, min=0, step=1000)
                                                    ], width=6),
                                                    dbc.Col([
                                                        dbc.Label("Valor mensal disponível (R$)"),
                                                        dbc.Input(id="valor-mensal-input", type="number", value=500, min=0, step=50)
                                                    ], width=6)
                                                ], className="mb-3"),
                                                dbc.Row([
                                                    dbc.Col([
                                                        dbc.Label("Taxa de juros anual (%)"),
                                                        dbc.Input(id="taxa-juros-meta-input", type="number", value=10, min=0, max=100, step=0.5)
                                                    ], width=12)
                                                ], className="mb-3"),
                                                dbc.Button("Calcular", id="calcular-meta-button", color="primary", className="mt-3")
                                            ])
                                        ], width=4),
                                        dbc.Col([
                                            html.Div(id="resultado-meta", className="p-3")
                                        ], width=8)
                                    ])
                                ])
                            ], className="mb-4")
                        ])
                    ])
                ], className="p-3")
            ], id="tabs", active_tab="tab-overview", 
            style={
                'border-bottom': f'1px solid {colors["grid"]}',
                'margin-bottom': '20px'
            })
        ])
    ]),
    
    dbc.Row([
        dbc.Col([
            html.Footer([
                html.P("Dashboard Financeiro © 2025", className="text-center text-muted")
            ], className="mt-4 mb-2")
        ])
    ])
], fluid=True)

# Callbacks para os cards de resumo
@callback(
    Output('summary-cards', 'children'),
    [Input('interval-component', 'n_intervals')]
)
def update_summary_cards(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Calcular resumo
    summary = get_financial_summary(df_receitas, df_despesas)
    
    # Criar cards
    cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                html.Div("Receitas", className="value-title"),
                html.Div(f"R$ {summary['total_receitas']:.2f}", className="value-card text-success")
            ])
        ], width=3),
        
        dbc.Col([
            dbc.Card([
                html.Div("Despesas", className="value-title"),
                html.Div(f"R$ {summary['total_despesas']:.2f}", className="value-card text-danger")
            ])
        ], width=3),
        
        dbc.Col([
            dbc.Card([
                html.Div("Saldo", className="value-title"),
                html.Div(f"R$ {summary['saldo']:.2f}", 
                       className=f"value-card {'text-success' if summary['saldo'] >= 0 else 'text-danger'}")
            ])
        ], width=3),
        
        dbc.Col([
            dbc.Card([
                html.Div("% Gastos/Receita", className="value-title"),
                html.Div(f"{summary['percentual_gastos']:.1f}%", className="value-card text-info")
            ])
        ], width=3)
    ])
    
    return cards

# Callback para o gráfico de despesas por categoria
@callback(
    [Output('despesas-categoria-graph', 'figure'),
     Output('receitas-fonte-graph', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_categoria_graphs(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Gráfico de pizza para despesas por categoria
    df_despesas_categoria = group_expenses_by_category(df_despesas)
    if not df_despesas_categoria.empty:
        fig_despesas = px.pie(
            df_despesas_categoria, 
            values='valor', 
            names='categoria',
            title='Despesas por Categoria',
            hole=0.4,
            color_discrete_sequence=colors['chart_colors'],
            template='plotly_dark'
        )
        fig_despesas.update_layout(
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    else:
        fig_despesas = go.Figure()
        fig_despesas.update_layout(
            title='Despesas por Categoria (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    # Gráfico de pizza para receitas por fonte
    df_receitas_fonte = group_income_by_source(df_receitas)
    if not df_receitas_fonte.empty:
        fig_receitas = px.pie(
            df_receitas_fonte, 
            values='valor', 
            names='fonte',
            title='Receitas por Fonte',
            hole=0.4,
            color_discrete_sequence=colors['chart_colors'],
            template='plotly_dark'
        )
        fig_receitas.update_layout(
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    else:
        fig_receitas = go.Figure()
        fig_receitas.update_layout(
            title='Receitas por Fonte (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig_despesas, fig_receitas

# Callback para o gráfico de receitas vs despesas
@callback(
    Output('receitas-despesas-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_receitas_despesas_graph(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Converter coluna de data para datetime
    if not df_receitas.empty:
        df_receitas['data'] = pd.to_datetime(df_receitas['data'])
        df_receitas['mes'] = df_receitas['data'].dt.strftime('%Y-%m')
        df_receitas_mensal = df_receitas.groupby('mes').agg({'valor': 'sum'}).reset_index()
        df_receitas_mensal['tipo'] = 'Receita'
    else:
        df_receitas_mensal = pd.DataFrame(columns=['mes', 'valor', 'tipo'])
    
    if not df_despesas.empty:
        df_despesas['data'] = pd.to_datetime(df_despesas['data'])
        df_despesas['mes'] = df_despesas['data'].dt.strftime('%Y-%m')
        df_despesas_mensal = df_despesas.groupby('mes').agg({'valor': 'sum'}).reset_index()
        df_despesas_mensal['tipo'] = 'Despesa'
    else:
        df_despesas_mensal = pd.DataFrame(columns=['mes', 'valor', 'tipo'])
    
    # Combinar receitas e despesas
    df_combined = pd.concat([df_receitas_mensal, df_despesas_mensal])
    
    # Gráfico de barras para receitas e despesas
    if not df_combined.empty:
        fig = px.bar(
            df_combined, 
            x='mes', 
            y='valor', 
            color='tipo',
            barmode='group',
            title='Receitas vs Despesas',
            color_discrete_map={'Receita': colors['success'], 'Despesa': colors['danger']},
            template='plotly_dark'
        )
        fig.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            legend_title='Tipo',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
    else:
        fig = go.Figure()
        fig.update_layout(
            title='Receitas vs Despesas (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig

# Callback para o gráfico de saldo acumulado
@callback(
    Output('saldo-acumulado-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_saldo_acumulado_graph(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Converter coluna de data para datetime
    if not df_receitas.empty:
        df_receitas['data'] = pd.to_datetime(df_receitas['data'])
        df_receitas['mes'] = df_receitas['data'].dt.strftime('%Y-%m')
        df_receitas_mensal = df_receitas.groupby('mes').agg({'valor': 'sum'}).reset_index()
    else:
        df_receitas_mensal = pd.DataFrame(columns=['mes', 'valor'])
    
    if not df_despesas.empty:
        df_despesas['data'] = pd.to_datetime(df_despesas['data'])
        df_despesas['mes'] = df_despesas['data'].dt.strftime('%Y-%m')
        df_despesas_mensal = df_despesas.groupby('mes').agg({'valor': 'sum'}).reset_index()
    else:
        df_despesas_mensal = pd.DataFrame(columns=['mes', 'valor'])
    
    # Mesclar receitas e despesas
    if not df_receitas_mensal.empty and not df_despesas_mensal.empty:
        df_merged = pd.merge(df_receitas_mensal, df_despesas_mensal, on='mes', how='outer', suffixes=('_receita', '_despesa'))
        df_merged = df_merged.fillna(0)
        
        # Calcular saldo mensal
        df_merged['saldo'] = df_merged['valor_receita'] - df_merged['valor_despesa']
        
        # Calcular saldo acumulado
        df_merged['saldo_acumulado'] = df_merged['saldo'].cumsum()
        
        # Gráfico de linha para saldo acumulado
        fig = px.line(
            df_merged, 
            x='mes', 
            y='saldo_acumulado',
            markers=True,
            title='Saldo Acumulado',
            template='plotly_dark'
        )
        
        # Adicionar linha de referência em zero
        fig.add_shape(
            type="line",
            x0=df_merged['mes'].min(),
            y0=0,
            x1=df_merged['mes'].max(),
            y1=0,
            line=dict(color="white", width=1, dash="dash"),
        )
        
        # Colorir área acima/abaixo de zero
        fig.add_traces(
            px.area(
                df_merged, 
                x='mes', 
                y='saldo_acumulado',
                color_discrete_sequence=['rgba(0, 204, 150, 0.2)' if df_merged['saldo_acumulado'].iloc[-1] >= 0 else 'rgba(255, 107, 107, 0.2)']
            ).data
        )
        
        fig.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
    else:
        fig = go.Figure()
        fig.update_layout(
            title='Saldo Acumulado (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig

# Callbacks para os gráficos da aba Análise Detalhada
@callback(
    [Output('maiores-gastos-graph', 'figure'),
     Output('maiores-receitas-graph', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_maiores_valores_graphs(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Gráfico de barras horizontais para maiores gastos
    df_top_despesas = get_top_expense_categories(df_despesas)
    if not df_top_despesas.empty:
        fig_despesas = px.bar(
            df_top_despesas, 
            y='categoria', 
            x='valor',
            orientation='h',
            title='Top 5 Categorias com Maiores Gastos',
            color_discrete_sequence=[colors['danger']],
            template='plotly_dark'
        )
        fig_despesas.update_layout(
            xaxis_title='Valor (R$)',
            yaxis_title='Categoria',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=True, gridcolor=colors['grid']),
            yaxis=dict(showgrid=False)
        )
    else:
        fig_despesas = go.Figure()
        fig_despesas.update_layout(
            title='Top 5 Categorias com Maiores Gastos (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    # Gráfico de barras horizontais para maiores receitas
    df_top_receitas = get_top_income_sources(df_receitas)
    if not df_top_receitas.empty:
        fig_receitas = px.bar(
            df_top_receitas, 
            y='fonte', 
            x='valor',
            orientation='h',
            title='Top 5 Fontes com Maiores Receitas',
            color_discrete_sequence=[colors['success']],
            template='plotly_dark'
        )
        fig_receitas.update_layout(
            xaxis_title='Valor (R$)',
            yaxis_title='Fonte',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=True, gridcolor=colors['grid']),
            yaxis=dict(showgrid=False)
        )
    else:
        fig_receitas = go.Figure()
        fig_receitas.update_layout(
            title='Top 5 Fontes com Maiores Receitas (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig_despesas, fig_receitas

@callback(
    [Output('gastos-mes-graph', 'figure'),
     Output('receitas-mes-graph', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_valores_mes_graphs(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Gráfico de linha para gastos por mês
    df_despesas_mes = group_expenses_by_month(df_despesas)
    if not df_despesas_mes.empty:
        fig_despesas = px.line(
            df_despesas_mes, 
            x='mes', 
            y='valor',
            markers=True,
            title='Gastos por Mês',
            color_discrete_sequence=[colors['danger']],
            template='plotly_dark'
        )
        fig_despesas.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
    else:
        fig_despesas = go.Figure()
        fig_despesas.update_layout(
            title='Gastos por Mês (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    # Gráfico de linha para receitas por mês
    df_receitas_mes = group_income_by_month(df_receitas)
    if not df_receitas_mes.empty:
        fig_receitas = px.line(
            df_receitas_mes, 
            x='mes', 
            y='valor',
            markers=True,
            title='Receitas por Mês',
            color_discrete_sequence=[colors['success']],
            template='plotly_dark'
        )
        fig_receitas.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
    else:
        fig_receitas = go.Figure()
        fig_receitas.update_layout(
            title='Receitas por Mês (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig_despesas, fig_receitas

@callback(
    Output('comparativo-anual-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_comparativo_anual_graph(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Agrupar por ano
    df_receitas_anual = group_by_year(df_receitas)
    df_despesas_anual = group_by_year(df_despesas)
    
    # Preparar dados para o gráfico
    if not df_receitas_anual.empty and not df_despesas_anual.empty:
        df_receitas_anual['tipo'] = 'Receita'
        df_despesas_anual['tipo'] = 'Despesa'
        
        df_combined = pd.concat([df_receitas_anual, df_despesas_anual])
        
        fig = px.bar(
            df_combined, 
            x='ano', 
            y='valor',
            color='tipo',
            barmode='group',
            title='Comparativo Anual: Receitas vs Despesas',
            color_discrete_map={'Receita': colors['success'], 'Despesa': colors['danger']},
            template='plotly_dark'
        )
        fig.update_layout(
            xaxis_title='Ano',
            yaxis_title='Valor (R$)',
            legend_title='Tipo',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
    else:
        fig = go.Figure()
        fig.update_layout(
            title='Comparativo Anual (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig

@callback(
    Output('relacao-ganhos-despesas-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_relacao_ganhos_despesas_graph(n_intervals):
    # Obter dados
    df_receitas, df_despesas = get_financial_data()
    
    # Calcular relação ganhos x despesas
    df_relacao = calculate_income_expense_ratio(df_receitas, df_despesas)
    
    if not df_relacao.empty:
        # Criar figura com dois eixos Y
        fig = go.Figure()
        
        # Adicionar barras para receitas e despesas
        fig.add_trace(go.Bar(
            x=df_relacao['mes'],
            y=df_relacao['valor_receita'],
            name='Receitas',
            marker_color=colors['success'],
            opacity=0.7
        ))
        
        fig.add_trace(go.Bar(
            x=df_relacao['mes'],
            y=df_relacao['valor_despesa'],
            name='Despesas',
            marker_color=colors['danger'],
            opacity=0.7
        ))
        
        # Adicionar linha para a relação
        fig.add_trace(go.Scatter(
            x=df_relacao['mes'],
            y=df_relacao['relacao'],
            name='Relação (Receita/Despesa)',
            mode='lines+markers',
            line=dict(color=colors['info'], width=3),
            yaxis='y2'
        ))
        
        # Adicionar linha de referência em 1 (equilíbrio)
        fig.add_shape(
            type="line",
            x0=df_relacao['mes'].iloc[0],
            y0=1,
            x1=df_relacao['mes'].iloc[-1],
            y1=1,
            line=dict(color="white", width=1, dash="dash"),
            yref='y2'
        )
        
        # Configurar layout com dois eixos Y
        fig.update_layout(
            title='Relação entre Ganhos e Despesas',
            xaxis=dict(
                title='Mês',
                showgrid=False,
                gridcolor=colors['grid']
            ),
            yaxis=dict(
                title='Valor (R$)',
                showgrid=True,
                gridcolor=colors['grid']
            ),
            yaxis2=dict(
                title='Relação (Receita/Despesa)',
                overlaying='y',
                side='right',
                showgrid=False,
                zeroline=False
            ),
            barmode='group',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            template='plotly_dark',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
        
        # Adicionar anotação para explicar a relação
        fig.add_annotation(
            x=0.5,
            y=-0.15,
            xref="paper",
            yref="paper",
            text="Relação > 1: Receitas maiores que despesas | Relação < 1: Despesas maiores que receitas",
            showarrow=False,
            font=dict(size=10, color=colors['text']),
            align="center",
            bgcolor=colors['card_background'],
            opacity=0.8
        )
    else:
        fig = go.Figure()
        fig.update_layout(
            title='Relação entre Ganhos e Despesas (Sem dados)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']}
        )
    
    return fig

# Callback para o simulador de investimentos
@callback(
    Output('resultado-investimento', 'children'),
    [Input('calcular-investimento-button', 'n_clicks')],
    [State('valor-inicial-input', 'value'),
     State('aporte-mensal-input', 'value'),
     State('taxa-juros-input', 'value'),
     State('periodo-input', 'value')]
)
def calcular_investimento(n_clicks, valor_inicial, aporte_mensal, taxa_juros, periodo):
    if n_clicks is None:
        return html.Div("Preencha os campos e clique em Calcular para ver o resultado.")
    
    try:
        # Validar inputs
        if valor_inicial is None or aporte_mensal is None or taxa_juros is None or periodo is None:
            return html.Div("Por favor, preencha todos os campos.")
        
        # Converter para números
        valor_inicial = float(valor_inicial)
        aporte_mensal = float(aporte_mensal)
        taxa_juros = float(taxa_juros)
        periodo = int(periodo)
        
        # Converter taxa anual para mensal
        taxa_mensal = (1 + taxa_juros/100) ** (1/12) - 1
        
        # Calcular montante
        montante = valor_inicial * (1 + taxa_mensal) ** (periodo * 12)
        
        # Calcular montante com aportes mensais
        for i in range(1, periodo * 12 + 1):
            montante += aporte_mensal * (1 + taxa_mensal) ** (periodo * 12 - i)
        
        # Calcular total investido
        total_investido = valor_inicial + (aporte_mensal * periodo * 12)
        
        # Calcular juros ganhos
        juros_ganhos = montante - total_investido
        
        # Criar tabela de resultados
        table = dbc.Table([
            html.Thead(
                html.Tr([
                    html.Th("Descrição"),
                    html.Th("Valor")
                ], className="table-dark")
            ),
            html.Tbody([
                html.Tr([
                    html.Td("Valor inicial:"),
                    html.Td(f"R$ {valor_inicial:.2f}")
                ]),
                html.Tr([
                    html.Td("Aporte mensal:"),
                    html.Td(f"R$ {aporte_mensal:.2f}")
                ]),
                html.Tr([
                    html.Td("Taxa de juros anual:"),
                    html.Td(f"{taxa_juros:.2f}%")
                ]),
                html.Tr([
                    html.Td("Período:"),
                    html.Td(f"{periodo} anos ({periodo * 12} meses)")
                ]),
                html.Tr([
                    html.Td("Total investido:"),
                    html.Td(f"R$ {total_investido:.2f}")
                ]),
                html.Tr([
                    html.Td("Juros ganhos:"),
                    html.Td(f"R$ {juros_ganhos:.2f}")
                ]),
                html.Tr([
                    html.Td("Montante final:"),
                    html.Td(f"R$ {montante:.2f}", className="fw-bold")
                ])
            ])
        ], bordered=True, hover=True, className="mb-4 table-dark")
        
        # Criar gráfico de evolução do investimento
        meses = list(range(0, periodo * 12 + 1))
        valores = []
        
        # Valor inicial
        valor_atual = valor_inicial
        valores.append(valor_atual)
        
        # Calcular evolução mês a mês
        for i in range(1, periodo * 12 + 1):
            valor_atual = valor_atual * (1 + taxa_mensal) + aporte_mensal
            valores.append(valor_atual)
        
        df_evolucao = pd.DataFrame({
            'mes': meses,
            'valor': valores
        })
        
        fig = px.line(
            df_evolucao, 
            x='mes', 
            y='valor',
            markers=True,
            title='Evolução do Investimento',
            template='plotly_dark'
        )
        fig.update_traces(line=dict(color=colors['success']))
        fig.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
        
        return html.Div([
            table,
            dcc.Graph(figure=fig),
            html.P(f"Com um investimento inicial de R$ {valor_inicial:.2f} e aportes mensais de R$ {aporte_mensal:.2f}, a uma taxa de {taxa_juros:.2f}% ao ano, você terá R$ {montante:.2f} após {periodo} anos.", 
                className="alert alert-success mt-3")
        ])
    except Exception as e:
        return html.Div([
            html.P(f"Ocorreu um erro: {str(e)}", className="alert alert-danger")
        ])

# Callback para o simulador de metas financeiras
@callback(
    Output('resultado-meta', 'children'),
    [Input('calcular-meta-button', 'n_clicks')],
    [State('valor-meta-input', 'value'),
     State('valor-mensal-input', 'value'),
     State('taxa-juros-meta-input', 'value')]
)
def calcular_meta(n_clicks, valor_meta, valor_mensal, juros):
    if n_clicks is None:
        return html.Div("Preencha os campos e clique em Calcular para ver o resultado.")
    
    try:
        # Validar inputs
        if valor_meta is None or valor_mensal is None or juros is None:
            return html.Div("Por favor, preencha todos os campos.")
        
        # Converter para números
        valor_meta = float(valor_meta)
        valor_mensal = float(valor_mensal)
        juros = float(juros)
        
        # Converter taxa anual para mensal
        taxa_mensal = (1 + juros/100) ** (1/12) - 1
        
        # Calcular número de meses necessários
        # Fórmula: FV = PMT * ((1 + r)^n - 1) / r
        # Resolvendo para n: n = log(1 + (FV * r / PMT)) / log(1 + r)
        if taxa_mensal > 0:
            n_meses = np.log(1 + (valor_meta * taxa_mensal / valor_mensal)) / np.log(1 + taxa_mensal)
        else:
            n_meses = valor_meta / valor_mensal
        
        # Arredondar para cima
        n_meses = np.ceil(n_meses)
        
        # Calcular anos e meses
        anos = int(n_meses // 12)
        meses_restantes = int(n_meses % 12)
        
        # Calcular montante final (pode ser ligeiramente diferente da meta devido ao arredondamento)
        montante = 0
        for i in range(1, int(n_meses) + 1):
            montante += valor_mensal * (1 + taxa_mensal) ** (int(n_meses) - i)
        
        # Calcular total investido
        total_investido = valor_mensal * n_meses
        
        # Calcular juros ganhos
        juros_ganhos = montante - total_investido
        
        # Criar tabela de resultados
        table = dbc.Table([
            html.Thead(
                html.Tr([
                    html.Th("Descrição"),
                    html.Th("Valor")
                ], className="table-dark")
            ),
            html.Tbody([
                html.Tr([
                    html.Td("Valor da meta:"),
                    html.Td(f"R$ {valor_meta:.2f}")
                ]),
                html.Tr([
                    html.Td("Valor mensal disponível:"),
                    html.Td(f"R$ {valor_mensal:.2f}")
                ]),
                html.Tr([
                    html.Td("Taxa de juros anual:"),
                    html.Td(f"{juros:.2f}%")
                ]),
                html.Tr([
                    html.Td("Tempo necessário:"),
                    html.Td(f"{anos} anos e {meses_restantes} meses ({int(n_meses)} meses no total)")
                ]),
                html.Tr([
                    html.Td("Total investido:"),
                    html.Td(f"R$ {total_investido:.2f}")
                ]),
                html.Tr([
                    html.Td("Juros ganhos:"),
                    html.Td(f"R$ {juros_ganhos:.2f}")
                ]),
                html.Tr([
                    html.Td("Montante final:"),
                    html.Td(f"R$ {montante:.2f}", className="fw-bold")
                ])
            ])
        ], bordered=True, hover=True, className="mb-4 table-dark")
        
        # Criar gráfico de evolução da meta
        meses = list(range(0, int(n_meses) + 1))
        valores = [0]  # Começar com zero
        
        # Calcular evolução mês a mês
        valor_atual = 0
        for i in range(1, int(n_meses) + 1):
            valor_atual = valor_atual * (1 + taxa_mensal) + valor_mensal
            valores.append(valor_atual)
        
        df_evolucao = pd.DataFrame({
            'mes': meses,
            'valor': valores
        })
        
        fig = px.line(
            df_evolucao, 
            x='mes', 
            y='valor',
            markers=True,
            title='Evolução para Atingir a Meta',
            template='plotly_dark'
        )
        
        # Adicionar linha horizontal para a meta
        fig.add_shape(
            type="line",
            x0=0,
            y0=valor_meta,
            x1=n_meses,
            y1=valor_meta,
            line=dict(color=colors['danger'], width=2, dash="dash"),
        )
        
        fig.update_traces(line=dict(color=colors['primary']))
        fig.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            paper_bgcolor=colors['card_background'],
            plot_bgcolor=colors['card_background'],
            font={'color': colors['text']},
            xaxis=dict(showgrid=False, gridcolor=colors['grid']),
            yaxis=dict(showgrid=True, gridcolor=colors['grid'])
        )
        
        return html.Div([
            table,
            dcc.Graph(figure=fig),
            html.P(f"Para atingir sua meta de R$ {valor_meta:.2f}, economizando R$ {valor_mensal:.2f} por mês com uma taxa de juros de {juros:.2f}% ao ano, você precisará de {anos} anos e {meses_restantes} meses.", 
                className="alert alert-info mt-3")
        ])
    except Exception as e:
        return html.Div([
            html.P(f"Ocorreu um erro: {str(e)}", className="alert alert-danger")
        ])

# Executar o servidor
if __name__ == '__main__':
    # Carregar variáveis de ambiente
    load_dotenv()
    
    # Obter a porta do arquivo .env ou usar 12000 como padrão
    port = int(os.getenv("DASHBOARD_PORT", 12000))
    
    print(f"Iniciando dashboard na porta {port}...")
    app.run(debug=True, host='0.0.0.0', port=port)