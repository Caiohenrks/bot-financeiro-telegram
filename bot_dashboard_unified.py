import os
import logging
import threading
import time
import psycopg2
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from datetime import datetime, date
import calendar

# Configuração de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Estados da conversa
DESCRICAO, CATEGORIA, FONTE, FORMA_PAGAMENTO, VALOR, DATA, CONSULTA_MES = range(7)
MESES_PT = [
    ["Janeiro"], ["Fevereiro"], ["Março"], ["Abril"], ["Maio"], ["Junho"],
    ["Julho"], ["Agosto"], ["Setembro"], ["Outubro"], ["Novembro"], ["Dezembro"]
]
MESES_MAP = {nome[0]: idx + 1 for idx, nome in enumerate(MESES_PT)}

# Conexão PostgreSQL
def setup_database():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id BIGINT PRIMARY KEY,
                first_name VARCHAR(100),
                username VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receitas (
                id SERIAL PRIMARY KEY,
                usuario_id BIGINT REFERENCES usuarios(id) ON DELETE CASCADE,
                descricao VARCHAR(255) NOT NULL,
                categoria VARCHAR(50) NOT NULL,
                fonte VARCHAR(50) NOT NULL,
                valor DECIMAL(10,2) NOT NULL,
                data DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS despesas (
                id SERIAL PRIMARY KEY,
                usuario_id BIGINT REFERENCES usuarios(id) ON DELETE CASCADE,
                descricao VARCHAR(255) NOT NULL,
                categoria VARCHAR(50) NOT NULL,
                forma_pagamento VARCHAR(50) NOT NULL,
                valor DECIMAL(10,2) NOT NULL,
                data DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        conn.commit()
        logging.info("✅ Banco de dados configurado com sucesso")
        return conn, cursor
    except Exception as e:
        logging.error("❌ Erro no banco de dados: %s", e)
        exit(1)

conn, cursor = setup_database()

# Categorias
CATEGORIAS = {
    'receita': [
        ["Salário", "Investimentos"],
        ["Freelance", "Vendas"],
        ["Aluguéis", "Dividendos","Renda Extra"]
    ],
    'despesa': [
        ["Alimentação", "Moradia"],
        ["Transporte", "Saúde"],
        ["Lazer", "Educação","Cartão de Crédito"],
    ]
}

FORMAS_PAGAMENTO = [
    ["Cartão Crédito", "Cartão Débito"],
    ["Dinheiro", "PIX"],
    ["Boleto", "Transferência"]
]

FONTES_RECEITA = [
    ["Principal", "Extra"],
    ["Investimento", "Bônus"],
    ["Outras"]
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        cursor.execute("SELECT 1 FROM usuarios WHERE id = %s", (user.id,))
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO usuarios (id, first_name, username)
                VALUES (%s, %s, %s)
            """, (user.id, user.first_name, user.username))
            logging.info(f"🧑‍💻 Novo usuário registrado: {user.id}")
        else:
            cursor.execute("""
                UPDATE usuarios
                SET first_name = %s, username = %s
                WHERE id = %s
            """, (user.first_name, user.username, user.id))
            logging.info(f"♻️ Dados do usuário atualizados: {user.id}")
        conn.commit()
    except Exception as e:
        logging.error(f"Erro ao registrar usuário: {e}")
        conn.rollback()
    await update.message.reply_text(
        "👋 Olá! O que você deseja registrar?",
        reply_markup=ReplyKeyboardMarkup(
            [["/receita", "/despesa"], ["/consulta_receita", "/consulta_despesa"], ["/dashboard"]],
            resize_keyboard=True
        )
    )

async def receita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["tipo"] = "receita"
    await update.message.reply_text("📥 Vamos registrar uma receita!\n\nPrimeiro, qual a descrição?")
    return DESCRICAO

async def despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["tipo"] = "despesa"
    await update.message.reply_text("📤 Vamos registrar uma despesa!\n\nPrimeiro, qual a descrição?")
    return DESCRICAO

async def consulta_receita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["consulta_tipo"] = "receita"
    await update.message.reply_text(
        "📅 Qual mês você quer consultar as receitas?",
        reply_markup=ReplyKeyboardMarkup(MESES_PT + [[KeyboardButton("/cancelar")]], resize_keyboard=True)
    )
    return CONSULTA_MES

async def consulta_despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["consulta_tipo"] = "despesa"
    await update.message.reply_text(
        "📅 Qual mês você quer consultar as despesas?",
        reply_markup=ReplyKeyboardMarkup(MESES_PT + [[KeyboardButton("/cancelar")]], resize_keyboard=True)
    )
    return CONSULTA_MES

async def dashboard_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia o link para o dashboard"""
    # Obter a porta do arquivo .env ou usar 12000 como padrão
    port = os.getenv("DASHBOARD_PORT", "12000")
    
    await update.message.reply_text(
        f"🔗 Acesse o dashboard financeiro: https://work-1-opmokccwzxepjryr.prod-runtime.all-hands.dev:{port}\n\n"
        "Lá você pode visualizar gráficos, análises detalhadas e simuladores financeiros.\n\n"
        "✨ Novo recurso: Agora você pode filtrar os dados por usuário para visualizar apenas suas próprias finanças!"
    )
    return ConversationHandler.END

async def mostrar_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = context.user_data.get("consulta_tipo")
    mes_nome = update.message.text.strip()
    user_id = update.effective_user.id
    ano_atual = date.today().year

    mes_num = MESES_MAP.get(mes_nome)
    if not mes_num:
        await update.message.reply_text("⚠️ Mês inválido! Use os botões.")
        return DATA

    primeiro_dia = date(ano_atual, mes_num, 1)
    ultimo_dia = date(ano_atual, mes_num, calendar.monthrange(ano_atual, mes_num)[1])

    if tipo == "receita":
        cursor.execute("""
            SELECT data, categoria, valor, descricao
            FROM receitas
            WHERE usuario_id = %s AND data BETWEEN %s AND %s
            ORDER BY data
        """, (user_id, primeiro_dia, ultimo_dia))
    else:
        cursor.execute("""
            SELECT data, categoria, valor, descricao
            FROM despesas
            WHERE usuario_id = %s AND data BETWEEN %s AND %s
            ORDER BY data
        """, (user_id, primeiro_dia, ultimo_dia))

    registros = cursor.fetchall()
    if not registros:
        await update.message.reply_text("📭 Nenhum registro encontrado para este mês.")
    else:
        linhas = [
            f"📌 {d.strftime('%d/%m/%Y')} - {c} - R${v:.2f} ({desc})"
            for d, c, v, desc in registros
        ]
        await update.message.reply_text("\n".join(linhas))

    context.user_data.clear()
    return ConversationHandler.END

async def descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["descricao"] = update.message.text
    tipo = context.user_data["tipo"]
    await update.message.reply_text(
        "🗂 Escolha a categoria:",
        reply_markup=ReplyKeyboardMarkup(
            CATEGORIAS[tipo] + [[KeyboardButton("/cancelar")]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return CATEGORIA

async def categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text
    tipo = context.user_data["tipo"]
    categorias_validas = sum(CATEGORIAS[tipo], [])
    if entrada not in categorias_validas:
        await update.message.reply_text("⚠️ Categoria inválida! Use os botões.")
        return CATEGORIA
    context.user_data["categoria"] = entrada

    if tipo == "receita":
        await update.message.reply_text(
            "🏦 Qual a fonte desta receita?",
            reply_markup=ReplyKeyboardMarkup(
                FONTES_RECEITA + [[KeyboardButton("/cancelar")]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return FONTE
    else:
        await update.message.reply_text(
            "💳 Qual a forma de pagamento?",
            reply_markup=ReplyKeyboardMarkup(
                FORMAS_PAGAMENTO + [[KeyboardButton("/cancelar")]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return FORMA_PAGAMENTO

async def fonte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text
    fontes_validas = sum(FONTES_RECEITA, [])
    if entrada not in fontes_validas:
        await update.message.reply_text("⚠️ Fonte inválida! Use os botões.")
        return FONTE
    context.user_data["fonte"] = entrada
    await update.message.reply_text(
        "💰 Qual o valor? (Ex: 1500.50)",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancelar")]], resize_keyboard=True)
    )
    return VALOR

async def forma_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text
    formas_validas = sum(FORMAS_PAGAMENTO, [])
    if entrada not in formas_validas:
        await update.message.reply_text("⚠️ Forma de pagamento inválida! Use os botões.")
        return FORMA_PAGAMENTO
    context.user_data["forma_pagamento"] = entrada
    await update.message.reply_text(
        "💰 Qual o valor? (Ex: 150.75)",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancelar")]], resize_keyboard=True)
    )
    return VALOR

import re
async def valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.replace(",", ".").strip()
    # Regex para aceitar apenas números positivos, com ou sem decimal
    if not re.match(r'^\d+(\.\d{1,2})?$', texto):
        await update.message.reply_text("⚠️ Valor inválido! Digite um número positivo (ex: 1234.56 ou 1234,56).")
        return VALOR
    valor = float(texto)
    if valor <= 0:
        await update.message.reply_text("⚠️ Valor deve ser maior que zero.")
        return VALOR
    context.user_data["valor"] = valor
    await update.message.reply_text(
        "📅 Data da transação:",
        reply_markup=ReplyKeyboardMarkup(
            [["Hoje", "Outra data"], [KeyboardButton("/cancelar")]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return DATA

async def data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Hoje":
        context.user_data["data"] = datetime.today().date()
        return await salvar(update, context)
    else:
        await update.message.reply_text(
            "📅 Digite a data (DD/MM/AAAA):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancelar")]], resize_keyboard=True)
        )
        return DATA

async def data_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = datetime.strptime(update.message.text, "%d/%m/%Y").date()
        if data > datetime.today().date():
            await update.message.reply_text("⚠️ Data futura! Use uma data válida.")
            return DATA
        context.user_data["data"] = data
        return await salvar(update, context)
    except ValueError:
        await update.message.reply_text("⚠️ Formato inválido! Use DD/MM/AAAA")
        return DATA

async def salvar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dados = context.user_data
    user_id = update.effective_user.id

    if dados["data"] > datetime.today().date():
        await update.message.reply_text("⚠️ Data futura não permitida! Use uma data válida.")
        return ConversationHandler.END

    try:
        if dados["tipo"] == "receita":
            cursor.execute("""
                INSERT INTO receitas (usuario_id, descricao, categoria, fonte, valor, data)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                dados["descricao"],
                dados["categoria"],
                dados["fonte"],
                dados["valor"],
                dados["data"]
            ))
        else:
            cursor.execute("""
                INSERT INTO despesas (usuario_id, descricao, categoria, forma_pagamento, valor, data)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                dados["descricao"],
                dados["categoria"],
                dados["forma_pagamento"],
                dados["valor"],
                dados["data"]
            ))
        conn.commit()
        await update.message.reply_text("✅ Registro salvo com sucesso!")
    except Exception as e:
        conn.rollback()
        logging.error("Erro ao salvar: %s", str(e))
        await update.message.reply_text("❌ Erro ao salvar! Tente novamente.")

    context.user_data.clear()
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END

def run_bot():
    """Função para executar o bot Telegram"""
    logging.info("Iniciando o bot Telegram...")
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("receita", receita),
            CommandHandler("despesa", despesa),
            CommandHandler("consulta_receita", consulta_receita),
            CommandHandler("consulta_despesa", consulta_despesa),
            CommandHandler("dashboard", dashboard_link)
        ],
        states={
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, descricao)],
            CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, categoria)],
            FONTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fonte)],
            FORMA_PAGAMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forma_pagamento)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, valor)],
            DATA: [
                MessageHandler(filters.Regex(r"^(Hoje|Outra data)$"), data),
                MessageHandler(filters.TEXT & ~filters.COMMAND, data_manual)
            ],
            CONSULTA_MES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mostrar_consulta)
            ]
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    app.run_polling()

def run_dashboard():
    """Função para executar o dashboard"""
    logging.info("Iniciando o dashboard...")
    # Importamos o dashboard aqui para evitar conflitos de importação
    import subprocess
    import sys
    
    # Obter a porta do arquivo .env ou usar 12000 como padrão
    port = os.getenv("DASHBOARD_PORT", "12000")
    logging.info(f"Dashboard será iniciado na porta {port}")
    
    # Executar o dashboard com filtro de usuários em um processo separado
    dashboard_process = subprocess.Popen(
        [sys.executable, "dashboard_user_filter.py"],
        stdout=open("dashboard.log", "w"),
        stderr=subprocess.STDOUT
    )
    
    logging.info(f"Dashboard iniciado com PID {dashboard_process.pid}")
    return dashboard_process

if __name__ == "__main__":
    # Iniciar o dashboard em uma thread separada
    dashboard_thread = threading.Thread(target=run_dashboard)
    dashboard_thread.daemon = True  # Isso garante que a thread será encerrada quando o programa principal terminar
    dashboard_thread.start()
    
    # Aguardar um momento para o dashboard iniciar
    time.sleep(2)
    
    # Iniciar o bot na thread principal
    run_bot()