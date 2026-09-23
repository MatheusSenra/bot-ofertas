# Bot de Ofertas — guia para o Claude

Bot de Telegram (python-telegram-bot 21, httpx, SQLite) que posta ofertas do Mercado Livre
com link de afiliado num canal e converte links no privado. Visão geral e setup: README.md.

## Estrutura
- `bot_ofertas/bot.py` — entrada (`python -m bot_ofertas.bot`), loop de postagem, comandos /start /postar /status, conversão de links
- `bot_ofertas/ofertas.py` — escolha do próximo produto (lista → baixou de preço → mais vendidos) e `/postar <link>`
- `bot_ofertas/lista.py` — lê listas e links meli.la pelo JSON `polycards` da página (sem API oficial; sensível a mudança de layout)
- `bot_ofertas/mercadolivre.py` — API oficial (client_credentials; `/sites/.../search` e `/items` dão 403, por isso usa `/highlights` + `/products`)
- `bot_ofertas/affiliate.py` — link de afiliado = link do produto + `matt_tool`/`matt_word`
- `bot_ofertas/formatter.py` — HTML do post · `storage.py` — histórico SQLite · `config.py` — .env
- `scripts/testar_lista.py`, `scripts/testar_api.py` — diagnóstico com dados reais
- `deploy/bot-ofertas.service` — systemd · `docs/` — logo, apresentação em PDF e fontes (`bash docs/src/gerar_pdfs.sh`)

## Convenções
- Código, comentários, logs e mensagens do bot em português (pt-BR).
- Não há suíte de testes: valide com os scripts em `scripts/` e simulações com histórico temporário (nunca o `data/historico.db` real).
- Não contornar a verificação anti-robô do Mercado Livre; usar só API oficial e páginas públicas (listas/perfil social).

## Regras importantes
- O repositório é PÚBLICO: nunca commitar `.env`, dados do servidor, IDs de admin, códigos de afiliado ou links pessoais.
  `docs/*INTERNO*.pdf` e `docs/src/interno.html` são locais e ficam no `.gitignore`.
- O bot roda em produção num servidor Linux (systemd). Não rodar outra instância com o mesmo token
  (posts duplicados). Deploy: push → `git pull` + `systemctl restart bot-ofertas` no servidor.
- Postar no canal é público: confirmar com o dono antes de ações que publiquem.
