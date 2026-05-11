# 📲 Disparo WhatsApp — Evolution API

## ▶️ Como rodar (3 passos)

### Passo 1 — Suba o Docker
Abra o terminal na pasta do projeto e rode:
```
docker compose up -d
```
Aguarde baixar a imagem (~1 min na primeira vez).

---

### Passo 2 — Conecte o WhatsApp
```
python setup_instancia.py
```
Vai abrir automaticamente no navegador uma página com o **QR Code**.
Escaneie com o WhatsApp: **Menu → Dispositivos Conectados → Conectar dispositivo**

---

### Passo 3 — Use o sistema
```
python main.py
```
Menu interativo com importação de contatos e disparo em massa.

---

## ⚙️ Configurações (já preenchidas)

| Variável | Valor |
|---|---|
| API URL | http://localhost:8080 |
| API Key | evolution-key-2024 |
| Instância | meu-whatsapp |

Tudo definido no `docker-compose.yml` e `config/settings.py` — **não precisa mudar nada**.

---

## 📋 Formato do CSV para importar contatos

```
nome,telefone
João Silva,11999999999
Maria Oliveira,11988888888
```

Use `{nome}` na mensagem para personalizar: `Olá, {nome}! Temos uma oferta pra você.`

---

## ⏱️ Delay humano

No disparo você configura:
- **Msgs por lote** — ex: 10
- **Delay entre mensagens** — ex: 5 segundos
- **Delay entre lotes** — ex: 180 segundos (3 minutos)

O sistema aplica ±20% de variação aleatória pra parecer humano.
