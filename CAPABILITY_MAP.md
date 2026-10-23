# Карта возможностей ClientPlatform → BusinessAIOS

Донор: mailsvb2-bot/clientplatform @ b2fdf2d0 (clientplatform/application, 141 модулей) + services/privacy_*. Цель: businesaios main cf0c5bdd + патч oct23.

Статусы: ported_core (ядро сценария перенесено этой серией, с тестами и live-прогоном; не полный паритет), ported (есть канонический владелец), ported_mapped (владелец записан в манифесте этой серией), partial, missing, obsolete-duplicate. Классификация эвристическая по префиксам модулей + ручная проверка владельцев (git grep); это НЕ доказательство паритета.

## Итог по модулям application/

До: {'partial': 111, 'ported': 30} → {'partial': 78.7, 'ported': 21.3}
После: {'ported_mapped': 17, 'partial': 86, 'ported': 30, 'ported_core': 8} → {'ported_mapped': 12.1, 'partial': 61.0, 'ported': 21.3, 'ported_core': 5.7}

Отдельно: services/privacy_controls + privacy_export_links (PD export): до — partial (core/privacy/data_rights без пользовательского входа), после — ported_core: /export_data (сводка) и /delete_my_data (двухшаговое удаление через DataRightsService.delete_user, квитанция без ПДн); gzip-ссылка и удаление из не-event хранилищ (реестр заказов, ledger) — нет.

## Манифест phase18

До: 40 слайсов (33 mapped / 7 inventory). После: 49 слайсов — +9 новых implemented в этой серии (privacy.personal_data_export, messaging.managed_bot_provisioning, commerce.orders_postgres_and_fulfilment, events.bookings_and_reminders, participant.home_cabinet, growth.partner_search, privacy.pd_deletion, commerce.offer_ladder, admin.business_ops_summary); каждый с явным списком missing. Перенесены в mapped: ads.yandex_direct_owner_flow, commerce.offerings_program_delivery.

## Кластеры

| Кластер | Модулей | До | После | Владелец в BusinessAIOS / пробел |
|---|---|---|---|---|
| Реклама / Яндекс Директ | 17 | partial | ported_mapped | interfaces/ads (AdsWriteGateway, yandex_direct_governed_execution, publication_proof), application/analytics/yandex_direct_growth_projection |
| Activity ladder / удержание | 3 | partial | partial | core/retention (pricing_ladder, offer_steps); нет activity directions |
| Внешние коннекторы | 6 | partial | partial | interfaces/ads/*, connectors/platform |
| Admin ops / поддержка | 7 | partial | partial | core/policies/telegram/handlers/admin, support.* (mapped); + /ops сводка (business_ops_summary@v1) |
| Продажи / Sales AI | 14 | ported | ported | sales.* слайсы mapped, commercial engagement |
| Кокпит владельца | 21 | partial | partial | platform.owner_cockpit_workspace (mapped) |
| Бронирования + напоминания | 2 | partial | ported_core | application/business_flows/bookings.py + bookings@v1 (/add_slot,/slots,/book,/my_bookings,/cancel_booking); напоминания 24ч/1ч pull-режимом, push через воркер — нет |
| Bot provisioning / мессенджеры | 7 | partial | partial | runtime/business_autonomy/messenger_cutover_admission.py (cutover-допуск), interfaces/telegram; нет managed-bot/BotFather state machine |
| Bot provisioning (managed bot) | 3 | partial | ported_core | application/business_flows/bot_provisioning.py + bot_provisioning@v1 (/connect_bot, /bot_status, /cancel_bot); реальный вызов Telegram getMe/setWebhook при verify — нет |
| Лестница предложений | 1 | partial | ported_core | application/business_flows/ladder.py + offer_ladder@v1 (/ladder_add,/ladder); evidence score вводится владельцем |
| Креативы/визуал | 14 | ported | ported | visual.* слайсы mapped; creative studio intake |
| UX участника | 6 | partial | partial | core/policies/telegram router, messenger.canonical_navigation_parity; + /me личный кабинет (bookings@v1 op=home) |
| Клиенты/таймлайн | 2 | ported | ported | customer.timeline mapped, CustomerRegistry |
| События/бронирования | 24 | partial | partial | event landing/promotion (mapped слайсы); bookings — см. отдельный кластер; event sessions/announcements/followups — нет |
| Заказы/программы/фулфилмент | 7 | partial | partial | application/commerce/phase18_* (Order/Invoice/Checkout в Event Store, PG-бэкенд), lesson delivery; + PostgresJsonRegistryBackend (BUSINESAIOS_CLIENT_OUTCOME_BACKEND=postgres) и record_fulfilment (FULFILLED по доказательству доставки); автоматического fulfilment worker — нет; аудиокурсы — вне scope (отдельный будущий подключаемый бизнес), в патчах отсутствуют |
| Поиск партнёров | 3 | partial | partial | application/partner (PartnerRegistry, growth_advisory); нет discovery-коннектора |
| Поиск партнёров (скоринг) | 2 | partial | ported_core | application/business_flows/partners.py + partners@v1 (/partner_add,/partners); discovery-коннектор и outreach — нет |
| UCR интеграция | 2 | partial | partial | interfaces/ucr/gateway.py (клиент REST /v1, fail-closed) + effects_clients/ucr_gateway_transport.py; sidecar и attendance_* не перенесены, проверено только против loopback-фейка |

## Модули

| Модуль | Кластер | До | После |
|---|---|---|---|
| acquisition_destination | Реклама / Яндекс Директ | partial | ported_mapped |
| activity | Activity ladder / удержание | partial | partial |
| activity_directions | Activity ladder / удержание | partial | partial |
| ad_channel_directory | Внешние коннекторы | partial | partial |
| ad_connections | Внешние коннекторы | partial | partial |
| ad_goal_autopilot | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_goal_publication | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_oauth_sessions | Внешние коннекторы | partial | partial |
| ad_provider_session | Внешние коннекторы | partial | partial |
| ad_publication_assets | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_publication_customization | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_spend | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_spend_consent | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_spend_control | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_spend_operations | Реклама / Яндекс Директ | partial | ported_mapped |
| ad_spend_runtime | Реклама / Яндекс Директ | partial | ported_mapped |
| admin_ops | Admin ops / поддержка | partial | partial |
| ai_commerce | Продажи / Sales AI | ported | ported |
| attribution | Реклама / Яндекс Директ | partial | ported_mapped |
| automation_policy | Кокпит владельца | partial | partial |
| booking_reminders | Бронирования + напоминания | partial | ported_core |
| bookings | Бронирования + напоминания | partial | ported_core |
| bot_gateway | Bot provisioning / мессенджеры | partial | partial |
| bot_provisioning | Bot provisioning (managed bot) | partial | ported_core |
| business_profile | Кокпит владельца | partial | partial |
| capability_parity | Admin ops / поддержка | partial | partial |
| cockpit | Кокпит владельца | partial | partial |
| cockpit_action_routing | Кокпит владельца | partial | partial |
| cockpit_automation | Кокпит владельца | partial | partial |
| cockpit_calendar | Кокпит владельца | partial | partial |
| cockpit_calendar_management | Кокпит владельца | partial | partial |
| cockpit_connections | Кокпит владельца | partial | partial |
| cockpit_customers | Кокпит владельца | partial | partial |
| cockpit_events | Кокпит владельца | partial | partial |
| cockpit_growth_analytics | Кокпит владельца | partial | partial |
| cockpit_home | Кокпит владельца | partial | partial |
| cockpit_money | Кокпит владельца | partial | partial |
| cockpit_sales | Кокпит владельца | partial | partial |
| cockpit_sales_management | Кокпит владельца | partial | partial |
| cockpit_services | Кокпит владельца | partial | partial |
| cockpit_settings | Кокпит владельца | partial | partial |
| commercial_ladder | Лестница предложений | partial | ported_core |
| connections | Внешние коннекторы | partial | partial |
| control | Admin ops / поддержка | partial | partial |
| control_callbacks | Admin ops / поддержка | partial | partial |
| creative_generation | Креативы/визуал | ported | ported |
| creative_growth_analytics | Креативы/визуал | ported | ported |
| creative_growth_optimization | Креативы/визуал | ported | ported |
| creative_growth_optimizer | Креативы/визуал | ported | ported |
| creative_studio | Креативы/визуал | ported | ported |
| creative_studio_publication | Креативы/визуал | ported | ported |
| creative_winner | Креативы/визуал | ported | ported |
| customer_activity | UX участника | partial | partial |
| customer_role_guard | UX участника | partial | partial |
| customer_timeline | Клиенты/таймлайн | ported | ported |
| customers | Клиенты/таймлайн | ported | ported |
| dispatch_worker | Кокпит владельца | partial | partial |
| editable_advertising | Реклама / Яндекс Директ | partial | ported_mapped |
| email_connections | Внешние коннекторы | partial | partial |
| event_analytics | События/бронирования | partial | partial |
| event_announcements | События/бронирования | partial | partial |
| event_commercial_consent | События/бронирования | partial | partial |
| event_conference_join | События/бронирования | partial | partial |
| event_content_assets | События/бронирования | partial | partial |
| event_content_plans | События/бронирования | partial | partial |
| event_customer_projection | События/бронирования | partial | partial |
| event_delivery_targets | События/бронирования | partial | partial |
| event_followup_settings | События/бронирования | partial | partial |
| event_followups | События/бронирования | partial | partial |
| event_growth | События/бронирования | partial | partial |
| event_landing_builder | События/бронирования | partial | partial |
| event_notifications | События/бронирования | partial | partial |
| event_owner_flow | События/бронирования | partial | partial |
| event_promotion | События/бронирования | partial | partial |
| event_public_surface | События/бронирования | partial | partial |
| event_registration_channels | События/бронирования | partial | partial |
| event_reminder_channels | События/бронирования | partial | partial |
| event_sessions | События/бронирования | partial | partial |
| event_warmups | События/бронирования | partial | partial |
| event_wizard | События/бронирования | partial | partial |
| events | События/бронирования | partial | partial |
| existing_bot_onboarding | Bot provisioning / мессенджеры | partial | partial |
| external_products | Заказы/программы/фулфилмент | partial | partial |
| growth_cockpit | Кокпит владельца | partial | partial |
| managed_bot_onboarding | Bot provisioning (managed bot) | partial | ported_core |
| managed_bot_owner | Bot provisioning (managed bot) | partial | ported_core |
| max_dispatch_pacing | Bot provisioning / мессенджеры | partial | partial |
| messenger_channels | Bot provisioning / мессенджеры | partial | partial |
| messenger_switching | Bot provisioning / мессенджеры | partial | partial |
| native_customer_interactions | UX участника | partial | partial |
| native_event_wizard | События/бронирования | partial | partial |
| native_member_interactions | UX участника | partial | partial |
| native_messenger_onboarding | Bot provisioning / мессенджеры | partial | partial |
| native_messenger_setup | Bot provisioning / мессенджеры | partial | partial |
| outcomes | Заказы/программы/фулфилмент | partial | partial |
| owner_booking_journey | События/бронирования | partial | partial |
| owner_input | Кокпит владельца | partial | partial |
| owner_onboarding | Кокпит владельца | partial | partial |
| pagination | UX участника | partial | partial |
| partner_attribution | Поиск партнёров | partial | partial |
| partner_copy | Поиск партнёров | partial | partial |
| partner_growth | Поиск партнёров (скоринг) | partial | ported_core |
| partner_runtime | Поиск партнёров | partial | partial |
| partner_scoring | Поиск партнёров (скоринг) | partial | ported_core |
| platform_directory | Admin ops / поддержка | partial | partial |
| program_builder | Заказы/программы/фулфилмент | partial | partial |
| program_media | Заказы/программы/фулфилмент | partial | partial |
| programs | Заказы/программы/фулфилмент | partial | partial |
| progress | Заказы/программы/фулфилмент | partial | partial |
| promotion_attribution | Реклама / Яндекс Директ | partial | ported_mapped |
| promotion_creatives | Реклама / Яндекс Директ | partial | ported_mapped |
| promotions | Реклама / Яндекс Директ | partial | ported_mapped |
| public_business_entry | UX участника | partial | partial |
| retention | Activity ladder / удержание | partial | partial |
| revenue_attribution | Заказы/программы/фулфилмент | partial | partial |
| sales_agent | Продажи / Sales AI | ported | ported |
| sales_ai_drafts | Продажи / Sales AI | ported | ported |
| sales_ai_orchestration | Продажи / Sales AI | ported | ported |
| sales_ai_settings | Продажи / Sales AI | ported | ported |
| sales_followups | Продажи / Sales AI | ported | ported |
| sales_handoff | Продажи / Sales AI | ported | ported |
| sales_intelligence | Продажи / Sales AI | ported | ported |
| sales_metrics | Продажи / Sales AI | ported | ported |
| sales_operations | Продажи / Sales AI | ported | ported |
| sales_orchestration | Продажи / Sales AI | ported | ported |
| sales_state_machine | Продажи / Sales AI | ported | ported |
| sales_ui | Продажи / Sales AI | ported | ported |
| sales_workspace | Продажи / Sales AI | ported | ported |
| support_cases | Admin ops / поддержка | partial | partial |
| tenancy | Admin ops / поддержка | partial | partial |
| ucr_attendance_observations | UCR интеграция | partial | partial |
| ucr_attendance_pilot | UCR интеграция | partial | partial |
| visual_aesthetic_director | Креативы/визуал | ported | ported |
| visual_brand_discovery | Креативы/визуал | ported | ported |
| visual_creatives | Креативы/визуал | ported | ported |
| visual_scene_plan_receipts | Креативы/визуал | ported | ported |
| visual_scene_planning | Креативы/визуал | ported | ported |
| visual_scene_variants | Креативы/визуал | ported | ported |
| visual_style_preferences | Креативы/визуал | ported | ported |
| yandex_campaign_diagnostics | Реклама / Яндекс Директ | partial | ported_mapped |
| yandex_growth_analytics | Реклама / Яндекс Директ | partial | ported_mapped |
## Per-function parity (donor ClientPlatform application/*)

Out of scope (excluded from denominator): 68 functions / 1569 lines: programs — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; program_media — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; progress — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; program_builder — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; connections: 1 functions (prepare_lesson_dispatch) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; control: 3 functions (create_single_lesson_program, prepare_native_program_delivery, prepare_program_delivery) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; event_warmups: 1 functions (_program_topics) — training programs not ported (user decision 11:33); native_customer_interactions: 2 functions (_programs_message, _program_message) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; native_member_interactions: 26 functions (_programs_message, _program_reference, _program_kind_label, _program_draft_message, _program_draft_archive_confirm, _program_draft_archive_result, _program_lessons_message, _program_lesson_detail_message, _program_lesson_title_edit_message, _program_lesson_title_result, _program_lesson_content_kinds_message, _program_lesson_content_edit_message, _program_lesson_content_result, _program_lesson_move_result, _program_lesson_archive_confirm, _program_lesson_archive_result, _program_direction_message, _program_title_input, _program_create_help, _program_create_result, _program_lesson_help, _program_lesson_kind_message, _program_lesson_result, _program_publish_result, _program_deliver_help, _program_deliver_result) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; native_event_wizard: 2 functions (_topics_choice_message, _event_topics) — topics come from training programs (not ported, 11:33)

Donor functions: 1499, function lines: 37924.

| status | functions | % | lines | % |
|---|---|---|---|---|
| ported | 252 | 16.8% | 7571 | 20.0% |
| obsolete | 75 | 5.0% | 799 | 2.1% |
| remaining | 1172 | 78.2% | 29554 | 77.9% |

**Parity (ported+obsolete): 327/1499 = 21.8% by count; 8370/37924 = 22.1% by lines.**

Modules with ported/obsolete functions:

| module.function | status | target / reason |
|---|---|---|
| ad_connections.ad_connections_enabled | ported | runtime/ads/connector_wiring.py ad_connections_enabled (BUSINESAIOS_AD_CONNECTIONS, default off) |
| ad_connections.yandex_direct_provider_configured | ported | runtime/ads/connector_wiring.py yandex_direct_configured |
| ad_connections._client_id | ported | runtime/ads/connector_wiring.py env YANDEX_DIRECT_CLIENT_ID |
| ad_connections._client_secret | ported | runtime/ads/connector_wiring.py SecretVault ref YANDEX_DIRECT_CLIENT_SECRET_REF |
| ad_connections._redirect_uri | ported | runtime/ads/connector_wiring.py explicit redirect_uri parameter |
| ad_connections._vault | ported | interfaces/ads/ports.py SecretVault (existing owner) |
| ad_connections.start_yandex_direct_oauth | ported | runtime/ads/connector_wiring.py via oauth_state.build_state + authorize_builder |
| ad_connections.complete_yandex_direct_oauth | ported | runtime/ads/connector_wiring.py state tenant/age check + YandexOAuthExchanger + TokenStore |
| ad_connections.list_ad_connections | ported | runtime/ads/connector_wiring.py registry truth + TokenStore presence, no token material |
| ad_connections.disconnect_ad_connection | ported | runtime/ads/connector_wiring.py TokenStore.delete |
| admin_ops._utc_now | obsolete | duplicate: clock is injected by the runtime (event timestamps), no module-level clock helper needed |
| admin_ops._value | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._text | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._body | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._currency | ported | application/business_flows/admin.py parse_money currency whitelist |
| admin_ops._amount_minor | ported | application/business_flows/admin.py parse_money |
| admin_ops._idempotency_key | ported | application/business_flows/admin.py stable_id(pay, reference) |
| admin_ops._begin_payment_write | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._serialize_payment_write | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._payment_evidence_from_row | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._evidence_by_key | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._insert_payment_evidence | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._resolve | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._audit | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._payment_from_row | ported | application/business_flows/admin.py replay payment_recorded |
| admin_ops._payment_row | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._validate_payment_outcome | ported | application/business_flows/admin.py record_payment terms check |
| admin_ops._replay_payment | ported | application/business_flows/admin.py record_payment replay branch |
| admin_ops._resolve_payment_offering | ported | application/business_flows/admin.py offering_unknown check against prices |
| admin_ops.record_payment | ported | application/business_flows/admin.py record_payment (reference-idempotent, conflicting reuse rejected) |
| admin_ops.refund_payment | ported | application/business_flows/admin.py refund_payment (bounded by remaining, refund-ref idempotent) |
| admin_ops.list_payments | ported | application/business_flows/admin.py /payments |
| admin_ops.set_offering_price | ported | application/business_flows/admin.py set_price |
| admin_ops.list_offering_prices | ported | application/business_flows/admin.py /price (list) |
| admin_ops._price_from_row | ported | application/business_flows/admin.py replay price_set |
| admin_ops.get_admin_setting | ported | application/business_flows/admin.py replay().settings + /setting |
| admin_ops.set_admin_setting | ported | application/business_flows/admin.py set_setting (business_admin@v1 fact = audit) |
| admin_ops.get_autopilot_enabled | ported | application/business_flows/admin.py State.autopilot |
| admin_ops.toggle_autopilot | ported | application/business_flows/admin.py set_autopilot toggle |
| admin_ops.set_autopilot_enabled | ported | application/business_flows/admin.py set_autopilot on|off (idempotent) |
| admin_ops._automation_money_text | ported | application/business_flows/admin.py money |
| admin_ops.format_automation_action_approval | ported | application/business_flows/admin.py format_approval |
| admin_ops.get_current_automation_action_approvals | ported | application/business_flows/admin.py /approvals |
| admin_ops.approve_pending_automation_action | ported | application/business_flows/admin.py decide_approval approve |
| admin_ops.reject_pending_automation_action | ported | application/business_flows/admin.py decide_approval reject |
| admin_ops.revoke_approved_automation_action | ported | application/business_flows/admin.py decide_approval revoke |
| admin_ops._percentile | obsolete | duplicate: existing owners runtime/platform/event_store/sqlite_perf_reporter.percentile and core/admin/read_models/latency._percentile |
| admin_ops.payment_summary | ported | application/business_flows/admin.py payment_summary/render_summary |
| booking_reminders.schedule_booking_reminders | ported | bookings.reminder_plan/due_reminders + /send_reminders dispatch |
| bookings.create_booking_slot | ported | application/business_flows/bookings.py + bookings@v1 (slots, book, cancel, mine, list) |
| bookings.list_booking_slots | ported | application/business_flows/bookings.py + bookings@v1 (slots, book, cancel, mine, list) |
| bookings.list_customer_businesses | ported | application/business_flows/bookings.py + bookings@v1 (slots, book, cancel, mine, list) |
| bookings.list_customer_booking_slots | ported | application/business_flows/bookings.py + bookings@v1 (slots, book, cancel, mine, list) |
| bookings.get_customer_booking | ported | application/business_flows/bookings.py + bookings@v1 (slots, book, cancel, mine, list) |
| bookings._finalize_customer_booking_claim | obsolete | SQL-transaction helper; event-sourced replay replaces it |
| bookings.book_customer_slot_in_transaction | obsolete | same |
| bookings.book_customer_slot_by_customer_in_transaction | obsolete | same |
| bookings.book_customer_slot | ported | application/business_flows/bookings.py + bookings@v1 (slots, book, cancel, mine, list) |
| bot_provisioning.create_botfather_provisioning | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning.submit_botfather_secret_references | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning.cancel_botfather_provisioning | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning.get_bot_provisioning | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning.list_bot_provisioning_requests | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning._begin_verification | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning._complete_verification | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning._fail_verification | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| bot_provisioning._rollback_then_fail_verification | obsolete | same |
| bot_provisioning._annotate_rollback_failure | obsolete | no DB rollback in event-sourced model |
| bot_provisioning.finalize_botfather_provisioning | ported | application/business_flows/bot_provisioning.py state machine + getMe verify_identity |
| cockpit._allowed | ported | application.business_flows.cockpit.render is_owner |
| cockpit._nav_item | ported | application.business_flows.cockpit._rows |
| cockpit.cockpit_navigation | ported | application.business_flows.cockpit.with_navigation |
| cockpit.resolve_cockpit_context | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit.resolve_cockpit_section_start_payload | ported | application.business_flows.cockpit.parse |
| cockpit.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_action_routing._strict_uuid_from_token | obsolete | web/SQL plumbing (timestamps, UUID tokens, request hashes, web URLs) not needed for event-sourced Telegram screens |
| cockpit_action_routing.build_cockpit_action_start_payload | ported | application.business_flows.cockpit cpm:<screen>[:arg] callback |
| cockpit_action_routing.build_cockpit_section_start_payload | ported | application.business_flows.cockpit cpm:<screen> |
| cockpit_action_routing.parse_cockpit_action_start_payload | ported | application.business_flows.cockpit.parse |
| cockpit_automation._local_timestamp | obsolete | web/SQL plumbing (timestamps, UUID tokens, request hashes, web URLs) not needed for event-sourced Telegram screens |
| cockpit_automation._money_display | ported | application.business_flows.admin.money |
| cockpit_automation._approval_item | ported | application.business_flows.admin.format_approval |
| cockpit_automation.build_cockpit_automation | ported | application.business_flows.cockpit screen automation |
| cockpit_automation._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_automation.resolve_cockpit_automation | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_automation.set_cockpit_autopilot | ported | application.business_flows.admin.set_autopilot |
| cockpit_automation.decide_cockpit_automation_approval | ported | application.business_flows.admin.decide_approval |
| cockpit_automation.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_calendar._bounded_limit | obsolete | SQL LIMIT clamp; paging via cockpit._paged |
| cockpit_calendar.build_cockpit_calendar | ported | application.business_flows.cockpit screen calendar |
| cockpit_calendar.resolve_cockpit_calendar | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_calendar.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_calendar_management._current_calendar_manager | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_calendar_management.build_cockpit_calendar_management | ported | application.business_flows.cockpit screen calendar |
| cockpit_calendar_management._resolve_manager | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_calendar_management.create_cockpit_calendar_slot | ported | application.business_flows.bookings.parse_slot / event_wizard |
| cockpit_calendar_management.cancel_cockpit_calendar_slot | ported | application.business_flows.bookings.cancel |
| cockpit_calendar_management.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_connections.build_cockpit_connections | ported | application.business_flows.cockpit screen connections |
| cockpit_connections._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_connections.resolve_cockpit_connections | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_connections.issue_cockpit_messenger_setup | ported | runtime.handler_impl.domains.business_flow_ops.handle_bot_provisioning |
| cockpit_connections.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_customers._display_name | ported | application.business_flows.cockpit._extra_screen customers (short id, no PII) |
| cockpit_customers._money_text | ported | application.business_flows.admin.money |
| cockpit_customers._timeline_items | ported | application.business_flows.cockpit screen customer |
| cockpit_customers.build_cockpit_customer_page | ported | application.business_flows.cockpit.customers + screen customers |
| cockpit_customers.build_cockpit_customer_detail | ported | application.business_flows.cockpit screen customer |
| cockpit_customers._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_customers.resolve_cockpit_customer_page | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_customers.resolve_cockpit_customer_detail | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_customers.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_customers.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_customers.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_events._public_base_url | obsolete | web/SQL plumbing (timestamps, UUID tokens, request hashes, web URLs) not needed for event-sourced Telegram screens |
| cockpit_events._money_display | ported | application.business_flows.admin.money |
| cockpit_events._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_events._can_manage | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_events._active_commercial_consents | ported | application.business_flows.cockpit screen events (consent count) |
| cockpit_events.resolve_events_snapshot | ported | application.business_flows.cockpit screen events |
| cockpit_events.resolve_cockpit_events | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_events.resolve_cockpit_event_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_events._request_hash | obsolete | web/SQL plumbing (timestamps, UUID tokens, request hashes, web URLs) not needed for event-sourced Telegram screens |
| cockpit_events.create_cockpit_event | ported | application.business_flows.event_wizard.step |
| cockpit_events.cancel_cockpit_event | ported | application.business_flows.bookings.cancel |
| cockpit_events.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_events.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_home._now | obsolete | web/SQL plumbing (timestamps, UUID tokens, request hashes, web URLs) not needed for event-sourced Telegram screens |
| cockpit_home._money_display | ported | application.business_flows.admin.money |
| cockpit_home._section_for_action | ported | application.business_flows.cockpit.PARENTS |
| cockpit_home._home_action | ported | application.business_flows.cockpit screen menu |
| cockpit_home._source_unavailable | obsolete | web/SQL plumbing (timestamps, UUID tokens, request hashes, web URLs) not needed for event-sourced Telegram screens |
| cockpit_home.build_cockpit_home | ported | application.business_flows.cockpit screens menu/today |
| cockpit_home.resolve_cockpit_home | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_home.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_money._display | ported | application.business_flows.admin.money |
| cockpit_money._major_to_minor | ported | application.business_flows.admin.parse_money |
| cockpit_money._current | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_money._active_offerings | ported | application.business_flows.admin.State.prices |
| cockpit_money.build_cockpit_money | ported | application.business_flows.cockpit screen money |
| cockpit_money._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_money.resolve_cockpit_money | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_money.record_cockpit_payment | ported | application.business_flows.admin.record_payment |
| cockpit_money.refund_cockpit_payment | ported | application.business_flows.admin.refund_payment |
| cockpit_money.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_sales._bounded_limit | obsolete | SQL LIMIT clamp |
| cockpit_sales._due_projection | ported | application.business_flows.sales.due_actions |
| cockpit_sales._project_sales_item | ported | application.business_flows.sales.render |
| cockpit_sales.build_cockpit_sales | ported | application.business_flows.sales.render |
| cockpit_sales.resolve_cockpit_sales | ported | runtime.handler_impl.domains.business_flow_ops.handle_sales_pipeline |
| cockpit_sales.as_dict | obsolete | web API serializer |
| cockpit_sales_management._business_zone | obsolete | fixed tenant tz in sales.set_next |
| cockpit_sales_management._current_sales_manager | obsolete | actor resolution by route owner_only |
| cockpit_sales_management._resolve_manager | obsolete | actor resolution by route owner_only |
| cockpit_sales_management._due_local_value | obsolete | MSK formatting in render |
| cockpit_sales_management._local_due_to_utc | ported | application.business_flows.sales.set_next (MSK→epoch) |
| cockpit_sales_management._management_item | ported | application.business_flows.sales.render |
| cockpit_sales_management.resolve_cockpit_sales_lead | ported | application.business_flows.sales.pick |
| cockpit_sales_management._require_open | ported | application.business_flows.sales.reduce (closed leads rejected) |
| cockpit_sales_management.set_cockpit_sales_stage | ported | application.business_flows.sales.apply_event |
| cockpit_sales_management.reopen_cockpit_sales_lead | ported | application.business_flows.sales.reopen |
| cockpit_sales_management.set_cockpit_sales_next_action | ported | application.business_flows.sales.set_next |
| cockpit_sales_management.add_cockpit_sales_note | ported | application.business_flows.sales.add_note |
| cockpit_sales_management.as_dict | obsolete | web API serializer |
| cockpit_services._money_display | ported | application.business_flows.admin.money |
| cockpit_services._money_input | ported | application.business_flows.admin.parse_money |
| cockpit_services._major_to_minor | ported | application.business_flows.admin.parse_money |
| cockpit_services._current | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_services._offerings | ported | application.business_flows.admin.State.prices |
| cockpit_services.build_cockpit_services | ported | application.business_flows.cockpit screen services |
| cockpit_services._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_services.resolve_cockpit_services | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_services.create_cockpit_service | ported | application.business_flows.admin.set_price (offering created with price) |
| cockpit_services.set_cockpit_service_price | ported | application.business_flows.admin.set_price |
| cockpit_services.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| cockpit_settings.build_cockpit_settings | ported | application.business_flows.cockpit screen settings |
| cockpit_settings._resolve_actor | obsolete | actor/role resolution is done once by the route (owner_only) + DecisionCore; per-screen resolvers are redundant |
| cockpit_settings.resolve_cockpit_settings | ported | runtime.handler_impl.domains.business_flow_ops._cockpit |
| cockpit_settings.update_cockpit_settings | ported | application.business_flows.admin.set_setting |
| cockpit_settings.as_dict | obsolete | dataclass→dict serializer for the web API; Telegram screens render text directly |
| commercial_ladder.create_commercial_ladder | ported | offer_ladder@v1 |
| commercial_ladder.add_commercial_ladder_step | ported | offer_ladder@v1 |
| commercial_ladder.get_commercial_offer_candidates | ported | offer_ladder@v1 |
| event_followups.commercial_event_followups_enabled | ported | application.business_flows.event_series.due_messages (offer_url + consent gate) |
| event_followups._value | obsolete | SQLite row accessor; event-sourced projection |
| event_followups._stage_offsets | ported | application.business_flows.event_series.FOLLOWUP_STAGES |
| event_followups._public_base_url | obsolete | web unsubscribe URL replaced by /offers_off command |
| event_followups._offer_url | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series (admin setting offer_url) |
| event_followups._unsubscribe_url | ported | application.business_flows.event_series.due_messages (/offers_off) |
| event_followups._followup_slot_key | ported | application.business_flows.event_series.due_messages key |
| event_followups._followup_position | ported | application.business_flows.event_series.FOLLOWUP_STAGES |
| event_followups._stored_followup_content | ported | application.business_flows.event_series.replay texts |
| event_followups._template_body | ported | application.business_flows.event_series._FOLLOWUP_TEMPLATES |
| event_followups._subject | obsolete | email subject; email channel not in Telegram-first scope (same as _resolve_email_target, left unported) |
| event_followups.event_followup_template_previews | ported | application.business_flows.event_series.previews |
| event_followups.get_event_followup_content_plan | ported | application.business_flows.event_series.previews |
| event_followups.set_event_followup_text | ported | application.business_flows.event_series.set_text |
| event_followups.reset_event_followup_text | ported | application.business_flows.event_series.reset_text |
| event_followups._render | ported | application.business_flows.event_series._template |
| event_followups._candidate_from_row | ported | application.business_flows.event_series.segment_of |
| event_followups._resolve_messenger_target | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series (to_user_id, Telegram) |
| event_followups._resolve_target | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series (to_user_id) |
| event_followups._dispatch_key | ported | application.business_flows.event_series.due_messages key |
| event_followups._stage_dispatch_state | ported | application.business_flows.event_series.replay sent |
| event_followups._next_due_stage | ported | application.business_flows.event_series.due_messages |
| event_followups._delivery_payload | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series send_tracked |
| event_followups._automation_followup_authorized | ported | application.business_flows.event_series.due_messages consent |
| event_followups._materialize | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series dispatch |
| event_followups._cancel_legacy_after_messages | obsolete | legacy queue rows do not exist in event store |
| event_followups._cancel_invalid_commercial_messages | ported | application.business_flows.event_series.due_messages (re-evaluated each dispatch) |
| event_followups.cancel_commercial_followups_for_registration_in_transaction | ported | application.business_flows.event_series.consent (offers_off stops series) |
| event_followups._load_scan_cursor | obsolete | SQL scan cursor; replay over facts |
| event_followups._store_scan_cursor | obsolete | SQL scan cursor; replay over facts |
| event_followups._scan_candidate_rows | obsolete | SQL scan; replay over facts |
| event_followups.materialize_due_event_followups_in_transaction | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series dispatch |
| event_followups.materialize_due_event_followups | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series dispatch |
| event_warmups._clean | ported | application.business_flows.event_series.safe_warmup_text |
| event_warmups._safe_warmup_text | ported | application.business_flows.event_series.safe_warmup_text |
| event_warmups._scheduled_at | ported | application.business_flows.event_series.due_messages |
| event_warmups._slot_key | ported | application.business_flows.event_series.due_messages key |
| event_warmups.build_event_warmup_plan | ported | application.business_flows.event_series.previews |
| event_warmups._base_plan | ported | application.business_flows.event_series.DEFAULT_WARMUP_DAYS |
| event_warmups.get_event_warmup_plan | ported | application.business_flows.event_series.previews |
| event_warmups.save_event_warmup_plan | ported | application.business_flows.event_series.parse_warmup_days |
| event_warmups.get_saved_event_warmup_plan | ported | application.business_flows.event_series.replay warmup_days |
| event_warmups.set_event_warmup_text | ported | application.business_flows.event_series.set_text |
| event_warmups.reset_event_warmup_text | ported | application.business_flows.event_series.reset_text |
| event_warmups._public_base_url | obsolete | web links not used: warm-ups forbid links |
| event_warmups._resolve_target | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series (to_user_id) |
| event_warmups._join_url | obsolete | web join links forbidden in organizational warm-ups |
| event_warmups._render_for_registration | ported | application.business_flows.event_series._template |
| event_warmups._dispatch_key | ported | application.business_flows.event_series.due_messages key |
| event_warmups._materialize | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series dispatch |
| event_warmups.materialize_due_event_warmups_in_transaction | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series dispatch |
| event_warmups.materialize_due_event_warmups | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series dispatch |
| existing_bot_onboarding._bot_id_from_token | ported | telegram_self_check(token=) getMe |
| existing_bot_onboarding.connect_existing_telegram_bot | ported | /connect_bot + /bot_secret + /verify_bot |
| native_event_wizard._button | ported | application.business_flows.event_wizard.step rows |
| native_event_wizard._back_row | ported | application.business_flows.event_wizard.step back |
| native_event_wizard._session | ported | application.business_flows.event_wizard.draft_title |
| native_event_wizard._context | ported | application.business_flows.event_wizard.step |
| native_event_wizard._save | ported | application.business_flows.event_wizard.draft |
| native_event_wizard._update | ported | application.business_flows.event_wizard.step (callback carries state) |
| native_event_wizard._date_label | ported | application.business_flows.event_wizard.step |
| native_event_wizard._date_picker_message | ported | application.business_flows.event_wizard.step (step 1) |
| native_event_wizard._start_time_message | ported | application.business_flows.event_wizard.step (step 2) |
| native_event_wizard._duration_message | ported | application.business_flows.event_wizard.step (step 3) |
| native_event_wizard._timezone_message | obsolete | business timezone fixed per tenant (Europe/Moscow) in bookings.parse_slot |
| native_event_wizard._event_description | obsolete | slot has title only; description lives in owner texts |
| native_event_wizard._warmup_message | ported | application.business_flows.event_wizard.step (step 4) |
| native_event_wizard.begin_native_event_wizard | ported | application.business_flows.event_wizard.draft |
| native_event_wizard.handle_native_event_wizard_text | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series op=wizard_start |
| native_event_wizard._accept_warmup_days | ported | application.business_flows.event_wizard.step -> event_series.parse_warmup_days |
| native_event_wizard._finish | ported | application.business_flows.event_wizard.step -> bookings.parse_slot |
| native_event_wizard.handle_native_event_wizard_action | ported | runtime.handler_impl.domains.business_flow_ops.handle_event_series op=wizard |
| native_event_wizard.abandon_native_event_wizard | ported | application.business_flows.event_wizard.draft_title (wizard_done) |
| native_member_interactions._compact | obsolete | whitespace helper for donor bridge tokens; no bridge tokens in businesaios |
| native_member_interactions._bridge_token | obsolete | donor cross-messenger bridge token; businesaios identity is TelegramCtx + tenant routing |
| native_member_interactions._active_customer_identity_exists | obsolete | donor SQL identity lookup; replaced by DecisionCore ctx.is_admin/role |
| native_member_interactions._member_context | obsolete | donor TenantContext construction; replaced by TelegramCtx |
| native_member_interactions.resolve_native_member | obsolete | donor member resolution over its SQL schema; businesaios resolves owner via ctx.is_admin before proposing |
| native_member_interactions.parse_native_member_interaction | ported | application/business_flows/cockpit.py parse (cpm:action[:args]) |
| native_member_interactions.recognizes_native_member_interaction | ported | application/business_flows/cockpit.py recognizes |
| native_member_interactions._button | ported | application/business_flows/cockpit.py _rows (40-char labels) |
| native_member_interactions._menu_rows | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._canonical_home_rows | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._menu_message | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._menu_all_message | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._back_row | ported | application/business_flows/cockpit.py HOME |
| native_member_interactions._native_parent_command | ported | application/business_flows/cockpit.py PARENTS |
| native_member_interactions._with_parent_navigation | ported | application/business_flows/cockpit.py with_navigation |
| native_member_interactions._permission_message | ported | application/business_flows/cockpit.py render(is_owner=False) |
| native_member_interactions._stale_message | ported | application/business_flows/cockpit.py render (ValueError→stale) |
| native_member_interactions._work_message | ported | application/business_flows/cockpit.py work screen |
| native_member_interactions._growth_message | ported | application/business_flows/cockpit.py growth screen |
| native_member_interactions._manage_message | ported | application/business_flows/cockpit.py manage screen |
| native_member_interactions._page_number | ported | application/business_flows/cockpit.py page_number |
| native_member_interactions._today_message | ported | application/business_flows/cockpit.py today screen (projection counts) |
| native_member_interactions._bookings_message | ported | application/business_flows/cockpit.py bookings screen (paged) |
| native_member_interactions._messengers_message | ported | application/business_flows/cockpit.py messengers screen (bot provisioning states) |
| native_member_interactions.render_native_member_interaction | ported | business_flow_ops._cockpit |
| native_member_interactions.process_native_member_interaction | ported | business_flow_ops._cockpit via DecisionCore → executor send_message (reply_markup) |
| pagination.paginate | ported | existing messenger pagination (core/policies/telegram router) |
| pagination.has_previous | ported | existing messenger pagination (core/policies/telegram router) |
| pagination.has_next | ported | existing messenger pagination (core/policies/telegram router) |
| partner_attribution.resolve_partner_referral | ported | partners.resolve_referral |
| partner_attribution.record_partner_referral_open | ported | partners.referral_token (open-recording via /start not wired) |
| partner_copy.validate_partner_content | ported | partners.pitch (deterministic, deny-phrase check) |
| partner_copy._ready_post | ported | partners.pitch (deterministic, deny-phrase check) |
| partner_copy._compact | ported | partners.pitch (deterministic, deny-phrase check) |
| partner_copy._bounded | ported | partners.pitch (deterministic, deny-phrase check) |
| partner_copy.generate | ported | partners.pitch (deterministic, deny-phrase check) |
| partner_copy.generate | ported | partners.pitch (deterministic, deny-phrase check) |
| partner_runtime.list_partner_candidates | ported | /partners |
| partner_runtime.get_partner_candidate_view | ported | /partner_pitch |
| partner_runtime.set_partner_candidate_status | ported | partners.set_status |
| partner_scoring.score_partner | ported | partners.rank |
| partner_scoring._audience_score | ported | partners.rank |
| partner_scoring._semantic_overlap | ported | partners.rank |
| partner_scoring._norm | ported | partners.rank |
| sales_followups.schedule_sales_followup | ported | application.business_flows.sales.set_next (owner reminder) |
| sales_followups.get_active_sales_followup | ported | application.business_flows.sales.due_actions |
| sales_handoff.open_sales_handoff | ported | application.business_flows.sales.apply_event 'handoff' |
| sales_handoff.list_sales_handoffs | ported | application.business_flows.sales.render (нужен человек) |
| sales_handoff.resolve_sales_handoff | ported | application.business_flows.sales.apply_event 'resume' |
| sales_metrics.get_sales_funnel_snapshot | ported | application.business_flows.sales.funnel |
| sales_operations.transition_sales_lead | ported | application.business_flows.sales.apply_event |
| sales_operations.set_sales_next_action | ported | application.business_flows.sales.set_next |
| sales_operations.add_sales_note | ported | application.business_flows.sales.add_note |
| sales_state_machine.apply_sales_conversation_event | ported | application.business_flows.sales.apply_event/reduce |
| sales_ui.list_sales_work | ported | application.business_flows.sales.render |
| sales_ui.get_sales_work_item | ported | runtime.handler_impl.domains.business_flow_ops.handle_sales_pipeline op=card |
| sales_ui.list_recent_closed_sales_work | ported | application.business_flows.sales.ordered (closed last) |
| sales_ui.list_commercial_ladders | ported | application.business_flows.ladder.replay |
| sales_ui.list_commercial_ladder_steps | ported | application.business_flows.ladder.replay |
| sales_workspace.sales_workspace_snapshot | ported | application.business_flows.sales.render |
| sales_workspace.list_sales_workspace | ported | application.business_flows.sales.render |
| sales_workspace.list_sales_workspace_handoffs | ported | application.business_flows.sales.render |
| sales_workspace.list_sales_workspace_recent_closed | ported | application.business_flows.sales.ordered |
| sales_workspace.list_sales_workspace_ladders | ported | application.business_flows.ladder.replay |
| sales_workspace.list_sales_workspace_ladder_steps | ported | application.business_flows.ladder.replay |
| sales_workspace.get_sales_workspace_item | ported | runtime.handler_impl.domains.business_flow_ops.handle_sales_pipeline op=card |
| sales_workspace.set_sales_workspace_next_action | ported | application.business_flows.sales.set_next |
| sales_workspace.add_sales_workspace_note | ported | application.business_flows.sales.add_note |
| sales_workspace.transition_sales_workspace | ported | application.business_flows.sales.apply_event |
| sales_workspace.reopen_sales_workspace | ported | application.business_flows.sales.reopen |
| sales_workspace.resolve_sales_workspace_handoff | ported | application.business_flows.sales.apply_event 'resume' |

Remaining by module (functions / lines):

native_member_interactions 185/6114, admin_ops 38/1467, visual_creatives 33/828, visual_scene_variants 22/712, ad_connections 21/649, event_landing_builder 24/633, growth_cockpit 18/466, customer_timeline 14/456, sales_ai_orchestration 21/406, ad_publication_assets 15/405, automation_policy 26/405, event_registration_channels 6/381, ad_goal_publication 8/380, event_notifications 8/377, visual_brand_discovery 21/370, event_followup_settings 12/354, external_products 15/349, yandex_growth_analytics 24/349, dispatch_worker 11/343, native_messenger_onboarding 11/334, ad_goal_autopilot 8/331, activity 19/327, owner_input 4/325, ad_spend_runtime 13/312, ucr_attendance_observations 12/300, promotions 14/299, event_commercial_consent 9/296, events 12/291, retention 9/291, partner_runtime 11/287, event_owner_flow 12/276, sales_intelligence 7/274, native_customer_interactions 14/270, native_event_wizard 6/267, creative_studio_publication 17/262, customer_activity 10/255, sales_orchestration 7/247, event_conference_join 12/240, control 8/229, visual_scene_planning 6/229, event_delivery_targets 4/228, yandex_campaign_diagnostics 10/226, partner_growth 9/216, ad_spend 11/210, owner_booking_journey 6/209, bot_gateway 10/208, ad_spend_operations 7/206, promotion_creatives 7/203, event_growth 14/193, capability_parity 11/186, public_business_entry 5/185, cockpit_growth_analytics 11/180, event_public_surface 5/178, event_sessions 8/178, managed_bot_owner 8/175, creative_winner 7/174, creative_growth_optimizer 5/173, managed_bot_onboarding 11/173, messenger_switching 10/173, editable_advertising 10/166, ad_spend_control 7/160, creative_studio 8/154, event_analytics 9/145, promotion_attribution 4/143, ucr_attendance_pilot 4/136, event_followups 5/132, event_content_plans 7/131, event_content_assets 4/129, event_announcements 8/120, creative_generation 10/111, event_warmups 4/109, creative_growth_analytics 4/108, activity_directions 9/104, ad_spend_consent 5/101, ai_commerce 4/101, cockpit_customers 5/101, connections 9/99, messenger_channels 5/98, customers 8/93, support_cases 8/93, event_customer_projection 2/91, visual_aesthetic_director 6/91, event_promotion 3/89, email_connections 2/87, event_wizard 6/87, acquisition_destination 4/79, visual_scene_plan_receipts 5/79, sales_ai_settings 7/78, owner_onboarding 5/73, sales_agent 4/73, ad_provider_session 5/69, platform_directory 5/68, revenue_attribution 3/65, max_dispatch_pacing 2/64, sales_ai_drafts 5/62, tenancy 9/60, event_reminder_channels 1/57, ad_publication_customization 3/55, ad_channel_directory 3/53, creative_growth_optimization 2/52, sales_workspace 7/48, cockpit_events 2/42, partner_attribution 2/38, attribution 2/34, business_profile 5/34, sales_followups 3/34, sales_handoff 2/33, cockpit_calendar_management 2/31, cockpit_home 2/30, customer_role_guard 2/30, outcomes 1/28, ad_oauth_sessions 1/20, cockpit_sales_management 2/20, existing_bot_onboarding 3/20, native_messenger_setup 3/18, sales_operations 3/18, cockpit_services 2/16, visual_style_preferences 3/16, sales_ui 2/13, control_callbacks 2/5

