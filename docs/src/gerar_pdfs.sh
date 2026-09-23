#!/usr/bin/env bash
# Gera os PDFs a partir dos HTMLs usando o Edge em modo headless (Windows/Git Bash).
set -e
cd "$(dirname "$0")"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
gerar() {  # $1 = html, $2 = pdf de saída
  "$EDGE" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=15000 \
    --print-to-pdf="$(cygpath -w "$PWD/../$2")" "file:///$(cygpath -m "$PWD/$1")" 2>/dev/null
  echo "gerado: docs/$2"
}
[ -f interno.html ] && gerar interno.html "Bot-de-Ofertas_Documentacao-Tecnica_INTERNO.pdf"
[ -f apresentacao.html ] && gerar apresentacao.html "Eu-que-fiz-Ofertas_Apresentacao.pdf"
exit 0
