# 📲 Sistema de Disparo WhatsApp — Evolution API

Projeto estruturado em Python para disparo em massa no WhatsApp
com delay humano configurável, banco SQLite e log completo.

---

## 📁 Estrutura do Projeto

```
whatsapp_disparo/
├── main.py                    ← Ponto de entrada (menu interativo)
├── requirements.txt
├── contatos_exemplo.csv
│
├── config/
│   └── settings.py            ← URL da API, chave e instância
│
├── database/
│   ├── db.py                  ← Criação do banco SQLite
│   ├── contacts_repo.py       ← CRUD de contatos
│   └── campaigns_repo.py      ← CRUD de campanhas e logs
│
├── services/
│   ├── evolution_api.py       ← Comunicação com a Evolution API
│   └── disparo.py             ← Motor de disparo com delay humano
│
├── utils/
│   ├── logger.py              ← Log no terminal e em arquivo
│   └── formatter.py           ← Formatação de telefone + import CSV
│
├── data/
│   └── disparo.db             ← Banco SQLite (criado automaticamente)
│
└── logs/
    └── YYYY-MM-DD.log         ← Logs diários (criados automaticamente)
```

---

## ⚙️ Configuração

### 1. Instale as dependências

```bash
pip install -r requirements.txt
```

### 2. Configure a Evolution API

Edite o arquivo `config/settings.py`:

```python
EVOLUTION_API_URL = "http://localhost:8080"   # URL da sua instância
EVOLUTION_API_KEY = "SUA_API_KEY_AQUI"        # Sua Global API Key
INSTANCE_NAME    = "minha-instancia"          # Nome da instância
```

### 3. Crie e conecte a instância na Evolution API

Acesse o painel da Evolution API e:
1. Crie uma instância com o mesmo nome definido em `INSTANCE_NAME`
2. Escaneie o QR Code com o WhatsApp

---

## ▶️ Como usar

```bash
python main.py
```

O menu interativo vai guiar você por:

1. **Importar contatos** — via CSV ou manualmente
2. **Iniciar disparo** — configura campanha, lote e delays
3. **Ver relatórios** — status de contatos e campanhas

---

## 📋 Formato do CSV

```csv
nome,telefone
João Silva,11999999999
Maria Oliveira,11988888888
```

- A coluna `telefone` é obrigatória
- A coluna `nome` é opcional
- Números sem o código do país (55) são aceitos — o sistema adiciona automaticamente

---

## ⏱️ Como funciona o delay humano

O sistema divide os contatos em **lotes** e aplica dois tipos de delay:

| Delay | O que é | Exemplo |
|---|---|---|
| **Entre mensagens** | Pausa entre cada envio dentro do lote | 5 segundos |
| **Entre lotes** | Pausa após terminar um lote completo | 3 minutos (180s) |

Para simular comportamento humano, o sistema aplica uma **variação aleatória de ±20%** em cada delay. Ex: 5s → entre 4s e 6s.

---

## 💬 Personalização de mensagem

Use `{nome}` na mensagem para inserir o nome do contato:

```
Olá, {nome}! Temos uma oferta especial para você hoje. 🎁
```

---

## 🗄️ Banco de dados (SQLite)

O arquivo `data/disparo.db` é criado automaticamente com 3 tabelas:

- `contacts` — telefones e status (pendente/enviado/erro)
- `campaigns` — histórico de campanhas com configurações
- `messages_log` — log individual de cada mensagem enviada

---

## 📌 Próximos passos sugeridos

- [ ] Resposta automática via Webhook
- [ ] Suporte a mensagens com imagem/documento
- [ ] Agendamento de campanhas por data/hora
- [ ] Painel web (Flask/FastAPI) para gerenciar tudo
- [ ] Exportação de relatórios em CSV/Excel
