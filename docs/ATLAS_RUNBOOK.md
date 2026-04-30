# Runbook эксплуатации Apache Atlas

## Ожидаемые точки доступа

- Основной ingress Compose: `8090->80`, поэтому с хоста типично `${INGRESS_BASE_URL:-http://localhost:8090}/atlas/` (до авторизации возможен 401 или 503 пока Atlas поднимается).
- Дополнительно в `docker-compose.yml` может быть проброс `80:80`; тогда можно открывать и `http://localhost/atlas/` (без порта).
- Если UI редиректит на `http://localhost/...` без порта при использовании `:8090`, проверьте `Host`, `X-Forwarded-Host`, `X-Forwarded-Port` в `infra/ingress/nginx.conf` или откройте тот же путь через тот же порт, что слушает ingress.
- Внутри Docker-сети: `http://atlas_server:21000/` (без префикса `/atlas`). Этот URL использовать из Airflow и `entity_publish`, если задача запускается в Compose.

## Холодный рестарт стека

1. После полного restart дождаться `atlas_server` health `healthy` (первые минуты возможны `502`/`503` через ingress пока процесс Atlas не слушает `21000`).
2. Если Atlas отвечает, но через ingress нет — `docker compose restart ingress` (обновление upstream IP).
3. Прогон smoke: `scripts/smoke_ingress.sh` (при втором пробросе на порт `80` задайте опционально `INGRESS_ALT_BASE_URL=http://localhost`).

## Симптом: `502 Bad Gateway` от nginx для `/atlas/`

**Причина:** `apache_atlas` еще не слушает `21000` (холодный старт: HBase, Solr, сборка Solr-коллекций, подъём Jetty часто **5–15+ минут**; после строки `Starting Atlas server on port: 21000` в логе может долго не быть новых строк из‑за буферизации JVM). Реже: nginx кэшировал старый IP `atlas_server` после `docker compose up --force-recreate` (в ingress используется динамический `proxy_pass` через переменную + `resolver 127.0.0.11`).

**Про пустые логи в Docker Desktop:** у `sburn/apache-atlas` основной вывод в stdout, но UI иногда показывает буфер с задержкой; смотрите **`docker logs -f atlas_server`** в терминале.

**Проверки:**

1. `docker ps --filter name=atlas_server` — контейнер в состоянии `Up`, health `healthy` (на первом старте может занять несколько минут; в compose `start_period: 420s`).
2. Из любого контейнера в `dataops_net`: `bash -lc 'exec 3<>/dev/tcp/atlas_server/21000'` — команда не должна зависать на connection refused.
3. Прямой API: `curl -sS -o /dev/null -w '%{http_code}' -u admin:admin http://atlas_server:21000/api/atlas/v2/search?limit=1` — ожидается 200.

**Восстановление:**

1. Подождать прохождения healthcheck Atlas (`healthy` в `docker ps`), без паники на `health: starting` первые минуты.
2. Если Atlas уже `healthy`, а 502 сохраняется — перезапустить ingress (в основном compose контейнер **`dataops_ingress`**):
   - `docker compose restart ingress`
3. Если подъём «завис» **>20–30 минут** после `Starting Atlas server on port: 21000`, проверьте `docker stats atlas_server` (RAM/OOM). В логах прошлых запусков были `Backend Health: Unhealthy!` / ошибки Kafka‑ZK при аварийном shutdown — тогда иногда помогает **пересоздание** контейнера Atlas (данные embedded‑стека в слое контейнера; каталог метаданных для демо можно наполнить снова через ingestion): остановить overlay Atlas и `docker compose rm -f` / `up` заново по README в `infra/metadata/atlas/`.

## Симптом: UI редиректит на `http://localhost:21000/` или теряет префикс `/atlas/`

**Причина:** Atlas UI отдает абсолютные редиректы; браузер должен ходить только через префиксный маршрут ingress.

**Восстановление:** Проверить, что `infra/ingress/nginx.conf` прокидывает `Host`, `X-Forwarded-*`, `X-Forwarded-Prefix`, включает rewrite cookie path и `proxy_redirect`. Открывать UI только через `${INGRESS_BASE_URL}/atlas/`.

## Симптом: `entity_publish` падает с 401/403 при вызове ingress URL

**Причина:** Неверный base URL внутри контейнера при использовании хостового URL с `/atlas`, либо неверные учетные данные.

**Восстановление:** С хоста использовать `--atlas-base-url "${INGRESS_BASE_URL}/atlas"`; из контейнера в том же стеке — `--atlas-base-url http://atlas_server:21000` (тот же API путь `/api/atlas/v2/`).

## После изменений в Atlas metadata overlays

Для ingestion только из YAML обычно не требуется rebuild/pull. Повторно выполнить:

```bash
pip install -r infra/metadata/atlas/requirements.txt
python infra/metadata/atlas/scripts/entity_publish.py \
  --atlas-base-url "${INGRESS_BASE_URL}/atlas" \
  infra/metadata/atlas/ingestion/kafka_topics_batch.yml
```

## Связанные документы

- [ARCHITECTURE_ATLAS.md](ARCHITECTURE_ATLAS.md)
- [ATLAS_ENTITY_CONTRACT.md](ATLAS_ENTITY_CONTRACT.md)
- Ingress smoke: `scripts/smoke_ingress.sh`
