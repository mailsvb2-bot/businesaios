# BusinesAIOS — норматив мультимессенджерской платформы

Статус: **нормативное дополнение** к `docs/SYSTEM_TZ_CANONICAL.md`.

Этот документ устраняет историческую неоднозначность, при которой Telegram мог выглядеть главным или обязательным runtime системы. Во всех вопросах каналов, provider-коннекторов и production-развёртывания этот норматив имеет приоритет над историческими Telegram-центричными описаниями.

## 1. Сущность платформы

BusinesAIOS — не Telegram-бот и не продукт, привязанный к одному интерфейсу.

BusinesAIOS — платформа автономного управления подключёнными организациями с возможностью подключать множество коммуникационных каналов и внешних провайдеров.

Каналы включают, но не ограничиваются:

- Telegram;
- WhatsApp;
- email;
- SMS;
- web-chat;
- VK и другие социальные/мессенджерные провайдеры;
- телефонию и голосовые каналы;
- CRM, сайты и внешние API как смежные connector surfaces.

Ни один канал не является обязательным, каноническим или привилегированным.

## 2. Закон независимости от канала

Внутреннее ядро не должно принимать бизнес-решения по признаку конкретного мессенджера.

Каждый внешний канал обязан быть преобразован в канонический provider/connector contract до передачи события в DecisionCore и RuntimeExecutor.

Минимальная нормализованная модель входящего сообщения содержит:

- tenant/organization identity;
- business identity;
- provider key и channel;
- external actor/conversation identity;
- message/event identity;
- timestamp;
- text/structured payload;
- attachments;
- trace/correlation metadata;
- verification evidence.

Канал может влиять только на transport capabilities и формат доставки. Он не может обходить Decision Sovereignty, RuntimeGuard, execute-once ledger или канонический effects boundary.

## 3. Существующий канонический connector layer

Следующие слои являются основой мультимессенджерской платформы и не должны дублироваться отдельным Telegram-ядром:

- `connectors/platform/` — capability/maturity contracts, registry, health, retry, timeout, quota, circuit breaker, failover, sandbox, secret binding и observability;
- `application/business_autonomy/provider_catalog.py` — каталог подключаемых провайдеров;
- `application/business_autonomy/provider_admin_service.py` — onboarding, activation, secret lifecycle, runtime routes и provider administration;
- `application/business_autonomy/provider_messaging_binding.py` — нормализация messaging capabilities;
- `runtime/business_autonomy/provider_inbound_webhook_service.py` и provider webhook runtime — входящие provider events;
- `runtime/business_autonomy/provider_queue_execution.py` — channel-agnostic queue execution;
- `runtime/business_autonomy/provider_live_sync_runtime.py` и vendor transports — исходящий sync/transport execution;
- provider health, incidents, replay guard, retries, pagination and response parsers.

Подключение нового мессенджера должно расширять provider catalog, transport binding, webhook/parser and capability contracts. Оно не должно создавать параллельный decision engine или альтернативный execution path.

## 4. Production runtime

Обязательные процессы платформы:

1. `businesaios-api.service`
   - web/API surface;
   - control plane;
   - provider onboarding;
   - webhook-based inbound channels;
   - health/readiness.

2. `businesaios-worker.service`
   - channel-agnostic background queues;
   - autonomous/evolution cycle;
   - outbound provider work;
   - retries and scheduled execution.

Отдельный connector unit разрешён только когда конкретный transport требует собственного долгоживущего polling/streaming процесса.

Пример разрешённого optional unit:

- `businesaios-connector-telegram.service` для Telegram long polling.

Наличие Telegram connector unit не делает Telegram обязательным и не меняет core runtime contract.

Webhook-based providers должны использовать API/provider webhook runtime. Создание фиктивного постоянно работающего процесса на каждый webhook-провайдер запрещено без реальной эксплуатационной необходимости.

## 5. Deployment invariants

Production installer обязан:

- всегда устанавливать API + Worker как core runtime;
- не требовать Telegram token для запуска платформы;
- не включать Telegram connector по умолчанию;
- включать optional connector units только явной конфигурацией;
- хранить provider secrets вне репозитория;
- сохранять независимые health/log surfaces для core и optional connector processes;
- мигрировать исторические `businesaios-telegram.service` и `businesaios-evolution.service` в API/Worker naming without running duplicate processes.

## 6. Provider maturity

Запись в provider catalog означает, что канал известен платформе и имеет контракт подключения. Это не равнозначно полной live-network готовности.

Для каждого provider отдельно фиксируются:

- capability maturity;
- webhook support;
- live probe support;
- prepared-only или live transport;
- verification support;
- idempotency/retry guarantees;
- required secrets;
- operational health.

Документация и UI не должны выдавать capability shell или prepared-only transport за полностью готовую production-интеграцию.

## 7. Запрещённые регрессии

Архитектурной ошибкой считаются:

- описание BusinesAIOS как Telegram-проекта;
- обязательный `RUN_MODE=telegram` в production template;
- deployment без API runtime;
- использование Telegram service как главного platform process;
- channel-specific business decisions вне DecisionCore;
- отдельный незащищённый execution path для любого messenger provider;
- утверждение о полной поддержке канала без соответствующего maturity/live proof.
