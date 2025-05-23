# Bot Financeiro Telegram

Um bot para Telegram que ajuda a gerenciar suas finanças pessoais, registrando receitas e despesas, e oferecendo um dashboard para visualização de dados.

## Funcionalidades

- Registro de receitas e despesas
- Consulta de transações por mês
- Dashboard financeiro com gráficos e análises
- Simuladores de investimentos e metas financeiras
- **Novo**: Filtro por usuário no dashboard

## Dashboard com Filtro de Usuário

O novo dashboard permite filtrar os dados financeiros por usuário, oferecendo:

- Visualização personalizada das finanças de cada usuário
- Análise detalhada de receitas e despesas por usuário
- Comparação de dados entre diferentes usuários
- Privacidade para usuários em ambientes compartilhados

## Configuração

1. Clone o repositório
2. Instale as dependências: `pip install -r requirements.txt`
3. Crie um arquivo `.env` baseado no `env-example`
4. Configure seu token do Telegram e as credenciais do banco de dados
5. Execute o bot: `python bot_dashboard_unified.py`

## Acesso ao Dashboard

O dashboard estará disponível em:
```
http://seu-servidor:12000
```

Você pode alterar a porta no arquivo `.env` usando a variável `DASHBOARD_PORT`.

## Tecnologias Utilizadas

- Python
- python-telegram-bot
- PostgreSQL
- Dash
- Plotly
- Pandas
- scikit-learn