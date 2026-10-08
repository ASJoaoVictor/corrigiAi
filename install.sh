#!/usr/bin/env bash
set -euo pipefail
set +x
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
fail() { printf '\n%s\n' "$1" >&2; exit 1; }
compose() { docker compose --project-directory "$PWD" -f "$PWD/compose.yaml" --env-file "$PWD/.env" "$@"; }
printf '[1/6] Verificando Docker...\n'
command -v docker >/dev/null 2>&1 && docker --version >/dev/null 2>&1 || fail 'Docker não foi encontrado. Instale Docker Engine e Docker Compose; consulte o README.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose não foi encontrado. Consulte o README.'
docker info >/dev/null 2>&1 || fail 'Não foi possível acessar o Docker. Verifique se ele está em execução e se seu usuário tem permissão para executá-lo.'
[[ -t 0 && -t 1 ]] || fail 'Execute este instalador em um terminal interativo.'
printf '[2/6] Preparando configuração...\nAs configurações serão solicitadas dentro do Docker após o build.\n'
printf '[3/6] Construindo aplicação e preparando modelos OCR. A primeira instalação pode demorar alguns minutos...\n'
docker build --tag corrigiai-local:latest . || fail 'Não foi possível construir a aplicação.'
docker run --rm -it --user "$(id -u):$(id -g)" --mount "type=bind,source=$PWD,target=/config" --entrypoint python corrigiai-local:latest scripts/install_common.py configure || fail 'Não foi possível configurar o ambiente. Execute novamente e confira os dados.'
printf '[4/6] Iniciando serviços...\n'
compose up -d --no-build web >/dev/null 2>&1 || fail 'Não foi possível iniciar os serviços. Confira .env, a porta 8000 e o Docker.'
printf '[5/6] Preparando banco...\n'
compose exec -T web flask --app run.py init-db >/dev/null 2>&1 || fail 'Não foi possível preparar o banco. Verifique DATABASE_URL e a conexão com o Supabase.'
printf '[6/6] Verificando aplicação...\n'
compose exec -T web python scripts/install_common.py health >/dev/null 2>&1 || fail 'A aplicação não respondeu dentro do tempo esperado. Diagnóstico: docker compose logs web (não compartilhe credenciais dos logs).'
printf '\n========================================\n        corrigiAi instalado\n========================================\nAplicação iniciada com sucesso.\nAcesso neste computador: http://localhost:8000\n'
# Only use the interface selected by the default route; avoid guessing among all IPs.
ip_local=''
if command -v ip >/dev/null 2>&1; then
    ip_local=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}') || true
fi
if [[ -n "$ip_local" ]]; then
    printf 'Possível acesso pelo celular na mesma rede: http://%s:8000\n' "$ip_local"
fi
printf 'Se necessário, consulte o IPv4 da interface Wi-Fi/Ethernet deste computador e use http://IP:8000.\nSe o celular não conseguir acessar, verifique se a porta 8000 está liberada no firewall do computador.\n'
