# Cutover ClientPlatform → BusinesAIOS (волна 12) — runbook

Статус: документ и флаги. Реальный cutover в рамках порта **не выполнялся**:
он требует операционных доказательств с прода (остановленный legacy-воркер,
токен в vault, готовый ingress), которых в песочнице нет.

## Флаги (все по умолчанию выключены, fail-closed)
| Флаг | Значение | Где читается |
|---|---|---|
| `BUSINESAIOS_ALLOW_NETWORK` | `1` — разрешить сетевые эффекты | runtime/_internal/http_transport.py |
| `BUSINESAIOS_UCR_GATEWAY_ENABLED` | `1` — включить клиент UCR /v1 | interfaces/ucr/gateway.py |
| `BUSINESAIOS_UCR_GATEWAY_URL` | https://… (http только loopback) | interfaces/ucr/gateway.py |
| `BUSINESAIOS_UCR_GATEWAY_TOKEN_REFERENCE` | `env:ИМЯ` (vault: не поддержан) | interfaces/ucr/gateway.py |
| `BUSINESAIOS_UCR_GATEWAY_TIMEOUT_SEC`, `_MAX_RESPONSE_BYTES` | лимиты | interfaces/ucr/gateway.py |

Транспорт UCR внедряется исполнителем: `runtime/_internal/effects_clients/ucr_gateway_transport.py`
(внутри запечатанного сетевого периметра, переиспользует `sync_request`).

## Порядок переключения (по одному каналу)
1. Остановить legacy-воркер и polling канала в ClientPlatform; зафиксировать доказательство.
2. Положить новый credential в хранилище секретов (ProviderAdmin), не меняя бот/группу.
3. Поднять ingress BusinesAIOS, проверить callback-хост.
4. Прогнать `runtime/business_autonomy/messenger_cutover_admission.check_cutover_admission`
   с реальными `ChannelTransferEvidence` для выбранного провайдера. Только `allowed` → дальше.
5. Включить `BUSINESAIOS_ALLOW_NETWORK=1`, регистрировать webhook через ProviderWebhookReconciler.
6. Smoke: `/start`, `/cockpit`, `/series`, `/leads` в боте; проверить журнал фактов.
7. Откат: выключить флаг, вернуть legacy-воркер (данные в ClientPlatform не удалялись).

## Миграция данных
Автоматического переноса БД ClientPlatform нет (SQL-курсоры донора помечены obsolete
в parity.json). Перенос записей — отдельная задача с выгрузкой и replay в факты.
