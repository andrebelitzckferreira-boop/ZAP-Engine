# Como Rodar

## Local

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
python setup_instancia.py
python -m panel.server
```

Abra `http://localhost:5000`.

## Painel

- Dashboard: status do WhatsApp, pendentes, enviados, respondidos e erros.
- Importar contatos: CSV/XLSX.
- Novo Disparo: mensagens, delays, limites, pausa/retomada/parada.
- Anti-Ban: limites diários, por hora, cooldown e aquecimento.
- IA & Chatbot: chave Groq, webhook e contexto comercial.

## Cloud

Para teste gratuito, use Render Free para o painel e Supabase Free para o banco. Configure `DATABASE_URL`, `PUBLIC_BASE_URL`, `PANEL_USERNAME`, `PANEL_PASSWORD`, `WEBHOOK_SECRET`, `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `INSTANCE_NAME` e `GROQ_API_KEY`.

Importante: planos gratuitos podem hibernar. Se a Evolution API dormir, o WhatsApp pode desconectar e pedir QR Code novamente.

## Executável Windows

1. Gere o build:

```bash
gerar_exe.bat
```

2. Inicie o sistema:

```bash
iniciar_sistema.bat
```

O executável final fica em `dist\ZAP_ENGINE.exe`.

Deixe o arquivo `.env` na mesma pasta do executável para que as variáveis sejam lidas corretamente.
