# Bot de Ofertas: Mercado Livre → Telegram

Bot que posta ofertas do Mercado Livre num canal do Telegram usando seu link de
afiliado, e converte links enviados no privado em links de afiliado.

> ⚠️ **Aviso:** projeto independente e **não oficial**, sem vínculo com o Mercado Livre.
> A leitura de listas e links de compartilhamento depende do layout das páginas do
> Mercado Livre e pode parar de funcionar se o site mudar. Use respeitando os
> [termos do Programa de Afiliados](https://www.mercadolivre.com.br/l/afiliados-primeiros-passos)
> e da API do Mercado Livre. Os links de afiliado usam **os seus** parâmetros
> (`ML_AFFILIATE_TOOL` / `ML_AFFILIATE_WORD`), e as comissões ficam com quem roda o bot.

## Como funciona

A cada `POST_INTERVAL_MINUTES`, o bot posta **uma** oferta no canal. A escolha segue esta ordem:

1. **Produto das suas listas que ainda não foi postado.** Os de maior desconto vão primeiro.
2. **Produto das listas que baixou de preço.** Vale se o último post foi há pelo menos
   `REPOST_AFTER_DAYS` dias e o preço caiu `REPOST_MIN_DROP_PERCENT`% ou mais.
   O post sai como "📉 BAIXOU DE PREÇO!".
3. **Mais vendidos das categorias em `ML_CATEGORIES`.** As categorias se alternam a cada post,
   e produtos com desconto têm preferência. Um mesmo produto nunca é postado duas vezes.

O histórico fica em `data/historico.db` (SQLite).

No **privado**, qualquer link do Mercado Livre enviado ao bot volta como link de
afiliado. Isso inclui links curtos `meli.la` e links de outros afiliados, cujo
rastreamento é substituído pelo seu.

## Estrutura

```
bot_ofertas/
├── bot_ofertas/
│   ├── bot.py           # bot do Telegram: loop de postagem, comandos, conversão de links
│   ├── ofertas.py       # escolha do próximo produto (lista → baixou de preço → mais vendidos)
│   ├── formatter.py     # texto da mensagem
│   ├── storage.py       # histórico em SQLite
│   ├── lista.py         # leitura das listas de recomendação
│   ├── mercadolivre.py  # cliente da API (OAuth + endpoints)
│   ├── affiliate.py     # extração de ID e montagem do link de afiliado
│   └── config.py        # leitura do .env
├── scripts/
│   ├── testar_api.py    # diagnóstico da API
│   └── testar_lista.py  # teste das listas de recomendação
├── deploy/
│   └── bot-ofertas.service  # serviço systemd para rodar 24h em Linux
├── data/                # histórico (gerado em runtime)
├── .env.example
└── requirements.txt
```

## Configuração

### 1. Credenciais da API do Mercado Livre
1. Acesse <https://developers.mercadolivre.com.br/devcenter> e crie uma aplicação:
   - **Redirect URI:** qualquer URL HTTPS (ex.: `https://www.google.com.br`)
   - **Fluxos OAuth:** Authorization Code, Client Credentials e Refresh Token (sem PKCE)
   - **Negócios:** Mercado Livre
   - **Permissões:** "Publicação e sincronização" como Leitura, o resto "Sem acesso"
   - **Tópicos:** nenhum
2. Copie o **Client ID** e o **Client Secret** para `ML_CLIENT_ID` e `ML_CLIENT_SECRET`.

### 2. Parâmetros de afiliado
O Mercado Livre **não tem API para gerar link de afiliado**. O rastreamento é
feito pelos parâmetros `matt_tool` e `matt_word` na URL do produto.
1. No portal de Afiliados do Mercado Livre, gere um link para qualquer produto.
2. Abra o link gerado e veja a URL final. Ela terá `...?matt_tool=XXXX&matt_word=YYYY`.
3. Coloque esses valores em `ML_AFFILIATE_TOOL` e `ML_AFFILIATE_WORD`.

### 3. Listas de recomendação
No Mercado Livre, abra sua lista, deixe-a **pública**, toque em compartilhar e
coloque o link em `ML_LIST_URLS`. Para várias listas, separe por vírgula.

### 4. Bot do Telegram
1. Fale com o [@BotFather](https://t.me/BotFather), envie `/newbot` e copie o token para `TELEGRAM_BOT_TOKEN`.
2. Adicione o bot como **administrador** do canal, com permissão para publicar mensagens.
3. Em `TELEGRAM_CHANNEL_ID`, use `@nome_do_canal` se o canal for público. Se for privado,
   use o ID numérico (`-100...`). Para descobrir o ID, encaminhe um post do canal ao
   [@userinfobot](https://t.me/userinfobot).
4. Rode o bot, mande `/start` para ele no privado e coloque o ID que ele responder em
   `TELEGRAM_ADMIN_IDS`. Depois reinicie o bot.

### 5. Instalação

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        # Linux/macOS: cp .env.example .env
```

Preencha o `.env`.

## Rodando

```bash
python -m bot_ofertas.bot
```

Ao iniciar, o bot retoma o ritmo a partir do último post: se já passou
`POST_INTERVAL_MINUTES` desde ele, posta em 10 segundos. Senão, espera o restante do intervalo.

### Rodando 24h num servidor Linux

```bash
git clone https://github.com/MatheusSenra/bot-ofertas.git
cd bot-ofertas
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# copie o .env (e data/historico.db, se já tiver histórico) para o servidor
.venv/bin/python -m scripts.testar_lista   # confirme que o ML não bloqueia o IP do servidor
sudo cp deploy/bot-ofertas.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bot-ofertas
```

Logs: `journalctl -u bot-ofertas -f`. O arquivo de serviço assume o usuário
`ubuntu` e o projeto em `/home/ubuntu/bot-ofertas`. Ajuste se for diferente.
**Não rode duas cópias do bot com o mesmo token**, porque os posts saem duplicados.

### Comandos (no privado, só para quem está em `TELEGRAM_ADMIN_IDS`)
| Comando | O que faz |
|---|---|
| `/postar` | Posta a próxima oferta da fila agora, sem esperar o intervalo |
| `/postar <link>` | Posta **esse** produto agora (veja abaixo quais links funcionam) |
| `/status` | Mostra a próxima postagem e os últimos posts |

Qualquer usuário pode mandar links no privado para convertê-los.

**Links aceitos no `/postar <link>`:**
- ✅ **Link de compartilhar de afiliado** (`meli.la/...`, gerado pelo botão "Compartilhar"
  no app). É o recomendado e funciona para qualquer produto.
- ✅ Link de qualquer produto que esteja nas suas listas.
- ✅ Link de produto de catálogo (`.../p/MLB...`).
- ❌ Link de anúncio comum (`produto.mercadolivre.com.br/MLB-...`) fora das listas: a API
  bloqueia e a página exige verificação anti-robô.

## Testes e diagnóstico

```bash
python -m scripts.testar_lista        # produtos das listas, com preço e link
python -m scripts.testar_api          # autenticação e mais vendidos (padrão: celulares)
python -m scripts.testar_api MLB1648  # outra categoria
```

## De onde vêm os dados

- **Listas:** não existe API para listas. O bot lê a página pública, que já traz
  título, preço, desconto, cupom e imagem. Se o Mercado Livre mudar o layout, o
  ajuste é em `bot_ofertas/lista.py`.
- **Mais vendidos:** com token de aplicação, a busca (`/sites/MLB/search`) e os
  detalhes de anúncio (`/items`) retornam **403**. Por isso o bot usa o catálogo:
  `/highlights/MLB/category/{cat}` → `/products/{id}` (nome e fotos) →
  `/products/{id}/items` (preços; usa o anúncio novo mais barato).
- **Links:** página do produto (`mercadolivre.com.br/.../p/MLB...`) com `matt_tool` e `matt_word`.
