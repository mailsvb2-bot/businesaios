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
| Реклама / Яндекс Директ | 17 | partial | ported_mapped | interfaces/ads (AdsWriteGateway, yandex_direct_governed_execution, publication_proof), application/analytics/yandex_direct_growth_projection; + business_flows/ad_spend_guard, ad_media (normalize_image, Pillow опционально), ad_publication_jobs (DryRun по умолчанию, реальные траты не подключены), yandex_growth |
| Activity ladder / удержание | 3 | partial | partial | core/retention (pricing_ladder, offer_steps); business_flows/catalog.py (профиль, предложения create/archive/rename/restore, форматы); нет offering process/retention batch и complete_profile |
| Внешние коннекторы | 6 | partial | partial | interfaces/ads/*, connectors/platform |
| Admin ops / поддержка | 7 | partial | partial | core/policies/telegram/handlers/admin, support.* (mapped); + /ops сводка (business_ops_summary@v1); + business_flows/delivery_routing.py (control: выбор маршрута доставки, статусы подключений, сводка) |
| Продажи / Sales AI | 14 | ported | ported | sales.* слайсы mapped, commercial engagement; + business_flows/sales_orchestration.py (план/handoff/кандидат лестницы, outbound только после approve) |
| Кокпит владельца | 21 | partial | partial | platform.owner_cockpit_workspace (mapped) |
| Бронирования + напоминания | 2 | partial | ported_core | application/business_flows/bookings.py + bookings@v1 (/add_slot,/slots,/book,/my_bookings,/cancel_booking); напоминания 24ч/1ч pull-режимом, push через воркер — нет |
| Bot provisioning / мессенджеры | 7 | partial | partial | runtime/business_autonomy/messenger_cutover_admission.py (cutover-допуск), interfaces/telegram; нет managed-bot/BotFather state machine |
| Bot provisioning (managed bot) | 3 | partial | ported_core | application/business_flows/bot_provisioning.py + bot_provisioning@v1 (/connect_bot, /bot_status, /cancel_bot); реальный вызов Telegram getMe/setWebhook при verify — нет |
| Лестница предложений | 1 | partial | ported_core | application/business_flows/ladder.py + offer_ladder@v1 (/ladder_add,/ladder); evidence score вводится владельцем |
| Креативы/визуал | 14 | ported | ported | visual.* слайсы mapped; creative studio intake; + business_flows/visual_scene.py (scene contract, ChatClient опционально) |
| UX участника | 6 | partial | partial | core/policies/telegram router, messenger.canonical_navigation_parity; + /me личный кабинет (bookings@v1 op=home); + business_flows/customer_activity.py (сводка активности клиентов) |
| Клиенты/таймлайн | 2 | ported | ported | customer.timeline mapped, CustomerRegistry |
| События/бронирования | 24 | partial | partial | event landing/promotion (mapped слайсы); bookings — см. отдельный кластер; event sessions/announcements/followups — нет |
| Заказы/программы/фулфилмент | 7 | partial | partial | application/commerce/phase18_* (Order/Invoice/Checkout в Event Store, PG-бэкенд), lesson delivery; + PostgresJsonRegistryBackend (BUSINESAIOS_CLIENT_OUTCOME_BACKEND=postgres) и record_fulfilment (FULFILLED по доказательству доставки); автоматического fulfilment worker — нет; аудиокурсы — вне scope (отдельный будущий подключаемый бизнес), в патчах отсутствуют |
| Поиск партнёров | 3 | partial | partial | application/partner (PartnerRegistry, growth_advisory) + business_flows/partners.py + partner_outreach.py (authorize/queue/reply-match gates, фактами, без отправки); нет discovery-коннектора (start/rerun campaign) |
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

Out of scope (excluded from denominator): 69 functions / 1588 lines: programs — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; program_media — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; progress — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; program_builder — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; connections: 1 functions (prepare_lesson_dispatch) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; control: 3 functions (create_single_lesson_program, prepare_native_program_delivery, prepare_program_delivery) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; event_warmups: 1 functions (_program_topics) — training programs not ported (user decision 11:33); native_customer_interactions: 2 functions (_programs_message, _program_message) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; native_member_interactions: 27 functions (_programs_message, _program_reference, _program_kind_label, _program_draft_message, _program_draft_archive_confirm, _program_draft_archive_result, _program_lessons_message, _program_lesson_detail_message, _program_lesson_title_edit_message, _program_lesson_title_result, _program_lesson_content_kinds_message, _program_lesson_content_edit_message, _program_lesson_content_result, _program_lesson_move_result, _program_lesson_archive_confirm, _program_lesson_archive_result, _program_direction_message, _program_title_input, _program_create_help, _program_create_result, _program_lesson_help, _program_lesson_kind_message, _program_lesson_result, _program_publish_result, _program_deliver_help, _program_deliver_result, _behavior_message) — training programs belong to the future pluggable courses business (user decision 2026-10-23), not ClientPlatform/businesaios; native_event_wizard: 2 functions (_topics_choice_message, _event_topics) — topics come from training programs (not ported, 11:33)

Donor functions: 1498, function lines: 37905.

| status | functions | % | lines | % |
|---|---|---|---|---|
| ported | 768 | 51.3% | 22761 | 60.0% |
| obsolete | 174 | 11.6% | 3763 | 9.9% |
| remaining | 556 | 37.1% | 11381 | 30.0% |

**Parity (ported+obsolete): 942/1498 = 62.9% by count; 26524/37905 = 70.0% by lines.**

Modules with ported/obsolete functions:

| module.function | status | target / reason |
|---|---|---|
| activity._audit_offering_action | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.customer_invite_error_message | ported | application/business_flows/invites.py (hashed one-time codes, /invite_new, /join) |
| activity.save_business_profile | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.get_business_profile | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.enable_business_capability | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.disable_business_capability | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.list_business_capabilities | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.create_business_offering | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.rename_business_offering | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.archive_business_offering | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.restore_business_offering | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.list_business_offerings | ported | application/business_flows/catalog.py (offerings@facts): save_profile/profile_text, create/retire/rename/restore_offering, active_offerings, toggle_format/formats_text (formats = capability switch); fact itself is the audit record |
| activity.issue_customer_invite | ported | application/business_flows/invites.py (hashed one-time codes, /invite_new, /join) |
| activity.claim_customer_invite | ported | application/business_flows/invites.py (hashed one-time codes, /invite_new, /join) |
| activity.extract_customer_invite_token | ported | application/business_flows/invites.py (hashed one-time codes, /invite_new, /join) |
| activity.claim_customer_invite_identity | ported | application/business_flows/invites.py claim() |
| ad_channel_directory._https_env | ported | owner_panels.AdChannel/ad_channels/ad_channel/_https_env: same 4 channels, texts, https-only env URLs; readiness injected from runtime.ads.connector_wiring |
| ad_channel_directory.advertising_channels | ported | owner_panels.AdChannel/ad_channels/ad_channel/_https_env: same 4 channels, texts, https-only env URLs; readiness injected from runtime.ads.connector_wiring |
| ad_channel_directory.advertising_channel | ported | owner_panels.AdChannel/ad_channels/ad_channel/_https_env: same 4 channels, texts, https-only env URLs; readiness injected from runtime.ads.connector_wiring |
| ad_connections.ad_connections_enabled | ported | runtime/ads/connector_wiring.py (governed OAuth lifecycle, production_ready truth) |
| ad_connections.yandex_direct_provider_configured | ported | runtime/ads/connector_wiring.py (governed OAuth lifecycle, production_ready truth) |
| ad_connections._client_id | ported | runtime/ads/connector_wiring.py env YANDEX_DIRECT_CLIENT_ID |
| ad_connections._client_secret | ported | runtime/ads/connector_wiring.py SecretVault ref YANDEX_DIRECT_CLIENT_SECRET_REF |
| ad_connections._redirect_uri | ported | runtime/ads/connector_wiring.py explicit redirect_uri parameter |
| ad_connections._provider | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._vault | ported | interfaces/ads/ports.py SecretVault (existing owner) |
| ad_connections._auth_error | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._refresh_token_bundle | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._managed_from_row | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._managed_get | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._reserve_managed_campaign | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._claim_failed_managed_creation | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._bind_managed_campaign | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._mark_managed_failure | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._mark_managed_refresh_failure | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections.start_yandex_direct_oauth | ported | runtime/ads/connector_wiring.py (governed OAuth lifecycle, production_ready truth) |
| ad_connections.complete_yandex_direct_oauth | ported | runtime/ads/connector_wiring.py (governed OAuth lifecycle, production_ready truth) |
| ad_connections.list_ad_connections | ported | runtime/ads/connector_wiring.py (governed OAuth lifecycle, production_ready truth) |
| ad_connections.list_yandex_direct_campaigns | ported | interfaces/ads/read_service.py AdsReadService.list_campaigns (existing owner, token via TokenStore) |
| ad_connections.ensure_yandex_managed_campaign | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections.create_ad_publication_draft | ported | application/business_flows/ad_proposals.py (/ad_draft, /ads, /ad_publish gated by production_ready; no provider call) |
| ad_connections.create_managed_ad_publication_draft | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections.confirm_ad_publication | ported | application/business_flows/ad_proposals.py (/ad_draft, /ads, /ad_publish gated by production_ready; no provider call) |
| ad_connections.disconnect_ad_connection | ported | runtime/ads/connector_wiring.py (governed OAuth lifecycle, production_ready truth) |
| ad_connections.list_ad_publications | ported | application/business_flows/ad_proposals.py (/ad_draft, /ads, /ad_publish gated by production_ready; no provider call) |
| ad_connections._fail_claimed_job | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._managed_name_for_job | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections._publish_job | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_connections.process_one_ad_publication | ported | ad_publication_jobs.py: Session refresh-once, managed campaign ledger (created disabled), job queue/claim/submit; DryRunDirectProvider, no spend |
| ad_goal_autopilot._minimum_weekly_minor | ported | ad_proposals.consent: exact weekly cap >= BUSINESAIOS_AD_MIN_WEEKLY_MINOR via owner approval |
| ad_goal_autopilot._caps | ported | ad_proposals.consent: exact weekly cap >= BUSINESAIOS_AD_MIN_WEEKLY_MINOR via owner approval |
| ad_goal_autopilot.prepare_goal_spend_consent | ported | ad_proposals.consent: exact weekly cap >= BUSINESAIOS_AD_MIN_WEEKLY_MINOR via owner approval |
| ad_goal_publication._publish_text | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication._sync_copy | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication._remember_media_error | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication._attach_media | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication._sync_submitted_media | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication.submit_goal_publication | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication.process_one_pending_video_asset | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_goal_publication.value | ported | ad_publication_jobs.submit/attach_media/process_pending_video; draft-only, dry-run provider |
| ad_publication_assets._normalized_image | ported | ad_media.normalize_image; Pillow optional (installed on box, not added to repo requirements) |
| ad_publication_assets._publication_job | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets._reserve_upload | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets._reservation_result | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets._mark_upload_ambiguous | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets._complete_upload | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets._provider_failure | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.attach_image_bytes | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.attach_image_file | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.attach_video_bytes | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.list_reusable_images | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.reuse_image_reference | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.remove_asset | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.get_asset_for_worker | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_publication_assets.remember_provider_ids | ported | ad_media.py fact-replay ledger; dry-run uploader; magic-byte+size/duration validation; Pillow resize NOT ported |
| ad_spend_control._now | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) guard() |
| ad_spend_control.evaluate_ad_spend_guard | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) guard() |
| ad_spend_runtime._timestamp | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime._value | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime._report_timezone | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime.provider_report_date | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime._provider | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime._load_authorization_system | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime._read_provider_evidence | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime.fresh_provider_snapshot | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime.evaluate_runtime_spend_guard | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime.production_pre_mutation_guard | ported | ad_proposals.publish_decision: fail-closed pre-mutation guard (approval + connector truth) |
| ad_spend_runtime._active_authorization_ids | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime._fail_closed | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| ad_spend_runtime.sweep_active_ad_spend_authorizations | ported | application/business_flows/ad_spend_guard.py (pure fail-closed guard, read-only snapshot, dry-run stop facts; tests/unit/business_flows/test_ad_spend_guard.py) |
| admin_ops._publication_effective_timestamp | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops._format_publication_timestamp | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops._publication_business_zone | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops._publication_schedule_utc | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.encode_publication_schedule_version | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops.decode_publication_schedule_version | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops.format_publication_calendar_lines | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops._utc_now | obsolete | duplicate: clock is injected by the runtime (event timestamps), no module-level clock helper needed |
| admin_ops._value | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._text | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._body | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._currency | ported | application/business_flows/admin.py parse_money currency whitelist |
| admin_ops._amount_minor | ported | application/business_flows/admin.py parse_money |
| admin_ops._idempotency_key | ported | application/business_flows/admin.py stable_id(pay, reference) |
| admin_ops._provider | obsolete | provider payment evidence is owned by core.payments (manual records carry no provider evidence) |
| admin_ops._external_reference | ported | application/business_flows/admin.py record_payment reference/idempotency (stable_id) |
| admin_ops._payment_stamp | obsolete | provider payment evidence is owned by core.payments (manual records carry no provider evidence) |
| admin_ops._request_fingerprint | ported | application/business_flows/admin.py record_payment reference/idempotency (stable_id) |
| admin_ops._begin_payment_write | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._serialize_payment_write | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._payment_evidence_from_row | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._evidence_by_key | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._evidence_for_payment | obsolete | provider payment evidence is owned by core.payments (manual records carry no provider evidence) |
| admin_ops._provider_evidence | obsolete | provider payment evidence is owned by core.payments (manual records carry no provider evidence) |
| admin_ops._insert_payment_evidence | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._resolve | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._audit | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._native_idempotent_entity_id | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.create_publication_draft | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops._publication_schedule_mutation_id | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops._publication_schedule_request_hash | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops._record_publication_schedule_mutation | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops._publication_schedule_replay | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops.schedule_publication | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.cancel_publication_schedule | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.publish_publication | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.list_publications | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.retire_publication | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.get_publication_calendar_projection | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops.list_publication_calendar | ported | application/business_flows/publications.py (/posts, /post_*) |
| admin_ops._publication_from_row | obsolete | SQLite row/version/mutation-ledger helpers; stable-id facts in business_admin@v1 give idempotency and replay |
| admin_ops._payment_from_row | ported | application/business_flows/admin.py replay payment_recorded |
| admin_ops._payment_row | obsolete | SQLite row/transaction/audit-table helper; event-sourced replay of business_admin@v1 facts replaces rows, locking and the audit table |
| admin_ops._outcome_idempotency_key | ported | application/business_flows/admin.py record_payment reference/idempotency (stable_id) |
| admin_ops._validate_payment_outcome | ported | application/business_flows/admin.py record_payment terms check |
| admin_ops._replay_payment | ported | application/business_flows/admin.py record_payment replay branch |
| admin_ops._resolve_payment_offering | ported | application/business_flows/admin.py offering_unknown check against prices |
| admin_ops._assert_provider_reference_available | ported | application/business_flows/admin.py record_payment reference/idempotency (stable_id) |
| admin_ops.record_payment | ported | application/business_flows/admin.py record_payment (reference-idempotent, conflicting reuse rejected) |
| admin_ops.refund_payment | ported | application/business_flows/admin.py refund_payment (bounded by remaining, refund-ref idempotent) |
| admin_ops.list_payments | ported | application/business_flows/admin.py /payments |
| admin_ops.set_offering_price | ported | application/business_flows/admin.py set_price |
| admin_ops.list_offering_prices | ported | application/business_flows/admin.py /price (list) |
| admin_ops._price_from_row | ported | application/business_flows/admin.py replay price_set |
| admin_ops.get_subscription_state | obsolete | platform subscription/paywall is owned by the port's access flow (/pay, «Полный доступ»); donor row was a fixed 'base' plan stub |
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
| admin_ops.record_interaction_metric | obsolete | duplicate: interaction latency metrics/alerts already owned by core/observability/perf_span + core/admin/read_models/latency + admin_latency handler |
| admin_ops.interaction_snapshot | obsolete | duplicate: interaction latency metrics/alerts already owned by core/observability/perf_span + core/admin/read_models/latency + admin_latency handler |
| admin_ops._percentile | obsolete | duplicate: existing owners runtime/platform/event_store/sqlite_perf_reporter.percentile and core/admin/read_models/latency._percentile |
| admin_ops.refresh_interaction_alerts | obsolete | duplicate: interaction latency metrics/alerts already owned by core/observability/perf_span + core/admin/read_models/latency + admin_latency handler |
| admin_ops.list_open_alerts | obsolete | duplicate: interaction latency metrics/alerts already owned by core/observability/perf_span + core/admin/read_models/latency + admin_latency handler |
| admin_ops.payment_summary | ported | application/business_flows/admin.py payment_summary/render_summary |
| admin_ops.business_admin_insights | obsolete | duplicate: owner insights served by /ops summary and cpm:growth-report; SQL count helper not needed |
| admin_ops.recent_audit_events | ported | application/business_flows/admin.py audit_lines (/audit) |
| admin_ops.purge_old_interaction_metrics | obsolete | duplicate: interaction latency metrics/alerts already owned by core/observability/perf_span + core/admin/read_models/latency + admin_latency handler |
| admin_ops.count | obsolete | duplicate: owner insights served by /ops summary and cpm:growth-report; SQL count helper not needed |
| automation_policy._now | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.save_automation_policy_draft | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.approve_automation_policy | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.revoke_effective_automation_policy | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.get_latest_automation_policy | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.get_effective_automation_policy | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.check_automation_action | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.request_automation_action_approval | ported | application/business_flows/automation_policy.py (/policy_draft, /policy_approve, /policy_revoke, /policy_check fail-closed) |
| automation_policy.get_automation_action_approval | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.list_current_automation_action_approvals | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.list_pending_automation_action_approvals | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.approve_automation_action | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.reject_automation_action | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.revoke_automation_action_approval | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.get_automation_action_authorization | ported | automation_policy.authorize: exact approval binding before executor effect |
| automation_policy._business_timezone | ported | timezone from catalog profile (/profile_set) instead of business_profiles SQL |
| automation_policy._event_action_scope | ported | automation_policy.SCOPES + in_quiet_hours in check() |
| automation_policy._growth_action_scope | ported | automation_policy.SCOPES + in_quiet_hours in check() |
| automation_policy._replace_action_scope | ported | automation_policy.SCOPES + in_quiet_hours in check() |
| automation_policy._drop_action_scope | ported | automation_policy.SCOPES + in_quiet_hours in check() |
| automation_policy._commit_composed_owner_policy | obsolete | SQL-transaction composition; event-sourced draft/approve facts replace it |
| automation_policy.set_owner_event_autosend_policy_in_conn | obsolete | conn-bound autosend toggle; replaced by policy facts + /followups; email channel effect blocked pending owner decision |
| automation_policy._safe_growth_policy_spec | ported | automation_policy.SCOPES + in_quiet_hours in check() |
| automation_policy.set_owner_autopilot_enabled | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.toggle_owner_autopilot | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
| automation_policy.is_owner_autopilot_enabled | ported | admin.py approvals (/approvals, /approve, /reject, /revoke) and /autopilot |
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
| control._shared_telegram_connection | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control._managed_telegram_connection | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control._preferred_telegram_connection | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control._single_active_native_connection | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control._preferred_customer_delivery_route | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control.business_connection_statuses | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control.business_delivery_summary | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| control.count | ported | application/business_flows/delivery_routing.py: route/connection selection + status/summary projections (pure; missing shared connection -> connection_proposed fact, vault: ref) |
| customer_activity._utc_now | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity._iso | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity._parse_dt | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity._row_value | obsolete | DB row accessor; records are plain dicts in customer_activity.py |
| customer_activity._staff_subjects | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity._load_activity | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity.tenant_customer_activity | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity.platform_customer_activity | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity.record_customer_contact | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_activity._after | ported | application/business_flows/customer_activity.py: summarize/tenant_activity/platform_activity/record_customer_contact (pure, staff+admin excluded, no shadow identities) |
| customer_timeline._bounded_text | ported | application/business_flows/customer_timeline.py + cpm:cust-time (bookings+attendance only; payments/attribution not customer-linked) |
| customer_timeline.get_customer_timeline | ported | application/business_flows/customer_timeline.py + cpm:cust-time (bookings+attendance only; payments/attribution not customer-linked) |
| customer_timeline.format_customer_timeline_lines | ported | application/business_flows/customer_timeline.py + cpm:cust-time (bookings+attendance only; payments/attribution not customer-linked) |
| customer_timeline.__post_init__ | ported | application/business_flows/customer_timeline.py + cpm:cust-time (bookings+attendance only; payments/attribution not customer-linked) |
| dispatch_worker._sanitize_error | obsolete | bai-port records only error_type (type name) in ambiguous/failed events, never the exception message, so credential redaction of messages is unnecessary (stricter) |
| dispatch_worker._effective_max_attempts | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| dispatch_worker._release_claims | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| dispatch_worker._claims_releasable_after_cancel | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| dispatch_worker._release_prepared_dispatch | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| dispatch_worker._provider_claim_can_cross_provider_boundary | obsolete | no durable lease->send gap in bai-port: sends happen in the same DecisionCore execution right after fact replay (e.g. bookings.due_reminders re-checks status=booked); partner outreach never auto-contacts |
| dispatch_worker._validated_runtime_link | obsolete | bai-port has no bearer staff URLs: cpm:* commands stay Telegram callbacks routed to business_ops_summary; nothing to materialize or URL-validate |
| dispatch_worker._materialize_native_interaction_links | obsolete | bai-port has no bearer staff URLs: cpm:* commands stay Telegram callbacks routed to business_ops_summary; nothing to materialize or URL-validate |
| dispatch_worker._mark_non_replay_boundary | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| dispatch_worker.run_dispatch_batch | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| dispatch_worker.__call__ | obsolete | replaced by bai-port executor/outbox, body-checked: runtime/execution/executor_commit (enqueue_once dedupe, claim_or_skip with claim TTL, mark_delivered, move_to_dead_letter) + executor_stages (post-authorization exception -> project_action_ambiguous_event 'dispatch_outcome_unknown', no silent success/replay; DecisionCore authorization required via _require_authorized); donor SQL-lease batch worker/two-phase adapter not part of bai-port architecture |
| event_announcements._schedule_lines | ported | owner_panels.schedule_lines/safe_template verbatim; announcement() builds template from slot/series; registration_url -> promo deep link (/start cpa_) |
| event_announcements._safe_template | ported | owner_panels.schedule_lines/safe_template verbatim; announcement() builds template from slot/series; registration_url -> promo deep link (/start cpa_) |
| event_announcements._event_for_owner | obsolete | DB EventRepository owner lookup; bai-port resolves the slot from bookings@v1 replay behind owner-only route |
| event_announcements._sessions_for_event | obsolete | DB EventRepository owner lookup; bai-port resolves the slot from bookings@v1 replay behind owner-only route |
| event_announcements._template_from_event | ported | owner_panels.schedule_lines/safe_template verbatim; announcement() builds template from slot/series; registration_url -> promo deep link (/start cpa_) |
| event_announcements.draft_event_announcement_template | ported | owner_panels.schedule_lines/safe_template verbatim; announcement() builds template from slot/series; registration_url -> promo deep link (/start cpa_) |
| event_announcements.registration_url | ported | owner_panels.schedule_lines/safe_template verbatim; announcement() builds template from slot/series; registration_url -> promo deep link (/start cpa_) |
| event_followup_settings._now | obsolete | _now: event clock injected as now_ms; channel switches: only Telegram delivery exists in port (no email/max/vk channel) |
| event_followup_settings._cancel_pending_followups | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings._cancel_pending_for_channel | obsolete | _now: event clock injected as now_ms; channel switches: only Telegram delivery exists in port (no email/max/vk channel) |
| event_followup_settings._cancel_pending_for_segment | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings._audit | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings._audit_strategy | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings.get_business_event_followup_settings | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings.get_business_event_followups_enabled | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings.set_business_event_followups_enabled | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings.set_business_event_followup_segment_enabled | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
| event_followup_settings.set_business_event_followup_channel_enabled | obsolete | _now: event clock injected as now_ms; channel switches: only Telegram delivery exists in port (no email/max/vk channel) |
| event_followup_settings.toggle_business_event_followups | ported | application/business_flows/event_series.py followup_settings/followup_allowed (/followups) |
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
| event_landing_builder._sentences | ported | application/business_flows/event_landing.py |
| event_landing_builder._line_items | ported | application/business_flows/event_landing.py |
| event_landing_builder._faq_items | ported | application/business_flows/event_landing.py |
| event_landing_builder._event_context | ported | application/business_flows/event_landing.py |
| event_landing_builder.build_event_landing_template | ported | application/business_flows/event_landing.py |
| event_landing_builder.get_event_landing_profile | ported | application/business_flows/event_landing.py |
| event_landing_builder.get_event_landing_editor_state | ported | application/business_flows/event_landing.py |
| event_landing_builder.ensure_event_landing_draft | ported | application/business_flows/event_landing.py |
| event_landing_builder._landing_ai_input | ported | application/business_flows/event_landing.py |
| event_landing_builder._landing_ai_claim_digest | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder._landing_ai_payload | ported | application/business_flows/event_landing.py |
| event_landing_builder._ai_unavailable_for_claim_status | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder.prepare_event_landing_ai_confirmation | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder.generate_event_landing_ai | ported | application/business_flows/event_landing.py |
| event_landing_builder.resolve_event_landing_ai_ambiguity | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder.reset_event_landing_template | ported | application/business_flows/event_landing.py |
| event_landing_builder.update_event_landing_section | ported | application/business_flows/event_landing.py |
| event_landing_builder.set_event_landing_theme | ported | application/business_flows/event_landing.py |
| event_landing_builder.publish_event_landing | ported | application/business_flows/event_landing.py |
| event_landing_builder.restore_simple_event_landing | ported | application/business_flows/event_landing.py |
| event_landing_builder.issue_event_landing_preview | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder._optional_landing_storage_missing | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder.get_public_event_landing | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_landing_builder.get_public_event_landing_preview | obsolete | donor claim/ambiguity ledger and storage probes: replaced by idempotent facts + strict-JSON fail-closed AI; public web preview not hosted in Telegram-only target |
| event_notifications._public_base_url | obsolete | no public web join page in bai-port: join/manage via bot /my_bookings; reminders derived from facts at dispatch time so channel-link reconcile is inherent (nothing materialized to reconcile) |
| event_notifications._event_url | obsolete | no public web join page in bai-port: join/manage via bot /my_bookings; reminders derived from facts at dispatch time so channel-link reconcile is inherent (nothing materialized to reconcile) |
| event_notifications._session_local_start_label | ported | bookings.due_reminders/sent_reminders (24h/3h/15m, key slot+offset+revision) + event_notifications.render/reminder_text; reschedule=bookings.reschedule bumps revision voiding unsent reminders and re-plans, booked customer notified; facts replace outbox rows |
| event_notifications._render | ported | bookings.due_reminders/sent_reminders (24h/3h/15m, key slot+offset+revision) + event_notifications.render/reminder_text; reschedule=bookings.reschedule bumps revision voiding unsent reminders and re-plans, booked customer notified; facts replace outbox rows |
| event_notifications._materialize | ported | bookings.due_reminders/sent_reminders (24h/3h/15m, key slot+offset+revision) + event_notifications.render/reminder_text; reschedule=bookings.reschedule bumps revision voiding unsent reminders and re-plans, booked customer notified; facts replace outbox rows |
| event_notifications.enqueue_event_notifications | ported | bookings.due_reminders/sent_reminders (24h/3h/15m, key slot+offset+revision) + event_notifications.render/reminder_text; reschedule=bookings.reschedule bumps revision voiding unsent reminders and re-plans, booked customer notified; facts replace outbox rows |
| event_notifications.reschedule_event_notifications_in_transaction | ported | bookings.due_reminders/sent_reminders (24h/3h/15m, key slot+offset+revision) + event_notifications.render/reminder_text; reschedule=bookings.reschedule bumps revision voiding unsent reminders and re-plans, booked customer notified; facts replace outbox rows |
| event_notifications.reconcile_future_event_notifications_for_customer | obsolete | no public web join page in bai-port: join/manage via bot /my_bookings; reminders derived from facts at dispatch time so channel-link reconcile is inherent (nothing materialized to reconcile) |
| event_promotion.event_advertising_url | ported | owner_panels.promotion_snapshot: registrations over series, registrations_from_ads via promotion attribution, advertising link = campaign deep link |
| event_promotion.get_event_promotion_snapshot | ported | owner_panels.promotion_snapshot: registrations over series, registrations_from_ads via promotion attribution, advertising link = campaign deep link |
| event_registration_channels.extract_event_registration_channel_link_token | ported | event_channels.py: ecv_ token extract, marketing platform validation, issue sha256-digest single-use platform-bound 60..3600s tokens for an active booking, consume with not-found/platform/consumed/expired/other-account checks + marketing consent flag; facts in bookings@v1 |
| event_registration_channels._marketing_platforms | ported | event_channels.py: ecv_ token extract, marketing platform validation, issue sha256-digest single-use platform-bound 60..3600s tokens for an active booking, consume with not-found/platform/consumed/expired/other-account checks + marketing consent flag; facts in bookings@v1 |
| event_registration_channels.issue_event_registration_channel_links_in_transaction | ported | event_channels.py: ecv_ token extract, marketing platform validation, issue sha256-digest single-use platform-bound 60..3600s tokens for an active booking, consume with not-found/platform/consumed/expired/other-account checks + marketing consent flag; facts in bookings@v1 |
| event_registration_channels._validated_connection_id | obsolete | bai-port has no per-business connections table; platform is fixed by the inbound adapter that delivered /start ecv_ |
| event_registration_channels.consume_event_registration_channel_link_in_transaction | ported | event_channels.py: ecv_ token extract, marketing platform validation, issue sha256-digest single-use platform-bound 60..3600s tokens for an active booking, consume with not-found/platform/consumed/expired/other-account checks + marketing consent flag; facts in bookings@v1 |
| event_registration_channels.consume_event_registration_channel_link | ported | event_channels.py: ecv_ token extract, marketing platform validation, issue sha256-digest single-use platform-bound 60..3600s tokens for an active booking, consume with not-found/platform/consumed/expired/other-account checks + marketing consent flag; facts in bookings@v1 |
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
| event_wizard.parse_session_count | ported | application/business_flows/event_wizard.py |
| event_wizard.normalize_event_timezone | ported | application/business_flows/event_wizard.py |
| event_wizard._normalise_date_token | obsolete | button wizard: date/time/duration picked via stateless cpe: callbacks, free-text window parsing unnecessary |
| event_wizard.parse_session_window | obsolete | button wizard: date/time/duration picked via stateless cpe: callbacks, free-text window parsing unnecessary |
| event_wizard.validate_session_sequence | ported | application/business_flows/event_wizard.py |
| event_wizard.normalize_session_join_url | ported | application/business_flows/event_wizard.py |
| events.create_event_in_transaction | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.create_event | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.publish_event_in_transaction | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.set_event_join_target_in_transaction | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.set_event_join_target | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.publish_event | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.cancel_event | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.register_public_attendee_in_transaction | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.cancel_public_registration_by_token_in_transaction | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.cancel_public_registration_by_token | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.register_public_attendee | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| events.get_public_event | ported | public_events.py fact lifecycle/registration (notifications planned via event_dispatch facts, executor-owned) |
| existing_bot_onboarding._bot_id_from_token | ported | telegram_self_check(token=) getMe |
| existing_bot_onboarding.connect_existing_telegram_bot | ported | /connect_bot + /bot_secret + /verify_bot |
| external_products.provision_external_product_connector | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.verify_and_activate_external_product_connector | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.bind_external_product_customer | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.record_external_observation_feedback | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.get_external_observation_value_snapshot | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.disable_external_product_connector | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.verify_external_product_signature | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.parse_external_product_event | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.authenticate_external_product_webhook | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.ingest_authenticated_external_product_event | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products.ingest_external_product_webhook | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products._parse_occurred_at | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products._parse_observation | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products._parse_money | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| external_products._parse_acquisition | ported | external_products.py (pure, same checks/reason codes, schema v1 strict, idempotent per connector+event_id with fingerprint conflict) + business_catalog_ops._external_products; secrets via env:/vault: refs resolved in runtime/integration/external_product_secrets (SecretVault); ingress = business_admin@v1 op xp_ingest through DecisionCore (no FastAPI route mounted) |
| growth_cockpit._attention | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| growth_cockpit._bounded_action_text | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| growth_cockpit._customer_work_actions | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| growth_cockpit.get_customer_work_actions | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| growth_cockpit._action_queue | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| growth_cockpit._next_action | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| growth_cockpit.get_growth_cockpit | ported | application/business_flows/growth_cockpit.py + cpm:growth-now (no ad spend/attribution facts) |
| max_dispatch_pacing._reserve_max_provider_slot | ported | body-verified: runtime/business_autonomy/provider_pacing.py ProviderPacingCoordinator, same 550ms dialog / 40ms connection spacing, CAS reservation; applied in provider_queue_execution for max_messaging |
| max_dispatch_pacing.pace_max_provider_boundary | ported | body-verified: runtime/business_autonomy/provider_pacing.py ProviderPacingCoordinator, same 550ms dialog / 40ms connection spacing, CAS reservation; applied in provider_queue_execution for max_messaging |
| native_event_wizard._button | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._back_row | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._session | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._context | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._save | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._update | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._date_label | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._date_picker_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._start_time_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._duration_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._timezone_message | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._event_description | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._venue_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._room_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._warmup_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._mode_message | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard.begin_native_event_wizard | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard.handle_native_event_wizard_text | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard._accept_count | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._accept_room | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._accept_warmup_days | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._finish | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard._warmup_preview | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_event_wizard.handle_native_event_wizard_action | ported | application/business_flows/event_wizard.py + business_flow_ops wizard/place |
| native_event_wizard.abandon_native_event_wizard | obsolete | stateless callback wizard: no server-side draft session/context store; topics/description handled by /landing |
| native_member_interactions._compact | obsolete | whitespace helper for donor bridge tokens; no bridge tokens in businesaios |
| native_member_interactions._bridge_token | obsolete | donor cross-messenger bridge token; businesaios identity is TelegramCtx + tenant routing |
| native_member_interactions._active_customer_identity_exists | obsolete | donor SQL identity lookup; replaced by DecisionCore ctx.is_admin/role |
| native_member_interactions._member_context | obsolete | donor TenantContext construction; replaced by TelegramCtx |
| native_member_interactions.resolve_native_member | obsolete | donor member resolution over its SQL schema; businesaios resolves owner via ctx.is_admin before proposing |
| native_member_interactions.parse_native_member_interaction | ported | application/business_flows/cockpit.py parse (cpm:action[:args]) |
| native_member_interactions.recognizes_native_member_interaction | ported | application/business_flows/cockpit.py recognizes |
| native_member_interactions._pending_owner_input | obsolete | stateful pending owner input replaced by slash commands with arguments (no hidden conversational state to expire) |
| native_member_interactions._owner_input_invalid_message | obsolete | stateful pending owner input replaced by slash commands with arguments (no hidden conversational state to expire) |
| native_member_interactions._begin_owner_input_message | obsolete | stateful pending owner input replaced by slash commands with arguments (no hidden conversational state to expire) |
| native_member_interactions._button | ported | application/business_flows/cockpit.py _rows (40-char labels) |
| native_member_interactions._menu_rows | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._business_name | ported | cockpit.Snapshot.business |
| native_member_interactions._native_projection_unavailable_action | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._native_growth_action_button | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._native_primary_action | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._canonical_home_rows | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._menu_message | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._menu_all_message | ported | application/business_flows/cockpit.py menu screen |
| native_member_interactions._back_row | ported | application/business_flows/cockpit.py HOME |
| native_member_interactions._native_parent_command | ported | application/business_flows/cockpit.py PARENTS |
| native_member_interactions._resolved_sales_lead_parent | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._with_parent_navigation | ported | application/business_flows/cockpit.py with_navigation |
| native_member_interactions._permission_message | ported | application/business_flows/cockpit.py render(is_owner=False) |
| native_member_interactions._stale_message | ported | application/business_flows/cockpit.py render (ValueError→stale) |
| native_member_interactions._work_message | ported | application/business_flows/cockpit.py work screen |
| native_member_interactions._work_more_message | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._sales_reference_item | ported | sales: /leads /lead_add /lead_card /lead_next /leads_due /lead_ai (sales.py, sales_ai.py) |
| native_member_interactions._sales_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._reactivation_message | ported | retention.py: /retention, /reactivate |
| native_member_interactions._reactivation_approve_message | ported | retention.py: /retention, /reactivate |
| native_member_interactions._native_minor_amount_text | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._ad_spend_message | ported | ads: /ads /ad_draft /ad_consent /ad_publish(blocked) /ad_stats /ad_report (ad_proposals.py, ad_analytics.py) |
| native_member_interactions._sales_recent_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._sales_handoffs_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._sales_primary_button | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._sales_lead_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._sales_actions_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._sales_result_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._sales_input_help | ported | sales: /leads /lead_add /lead_card /lead_next /leads_due /lead_ai (sales.py, sales_ai.py) |
| native_member_interactions._sales_followup_message | ported | sales_followups.py: /lead_followups status, /lead_followup plan (1/24/72h, night->08:00), cancel, /lead_optout confirm, /send_followups via original Telegram channel; inbound reply cancels |
| native_member_interactions._sales_followup_help | ported | sales_followups.py: /lead_followups status, /lead_followup plan (1/24/72h, night->08:00), cancel, /lead_optout confirm, /send_followups via original Telegram channel; inbound reply cancels |
| native_member_interactions._sales_followup_optout_help | ported | sales_followups.py: /lead_followups status, /lead_followup plan (1/24/72h, night->08:00), cancel, /lead_optout confirm, /send_followups via original Telegram channel; inbound reply cancels |
| native_member_interactions._sales_mutation_message | ported | application/business_flows/cockpit_sales.py (sales_pipeline reducer) |
| native_member_interactions._next_message | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._clients_sales_message | ported | sales: /leads /lead_add /lead_card /lead_next /leads_due /lead_ai (sales.py, sales_ai.py) |
| native_member_interactions._ad_materials_message | ported | ads: /ads /ad_draft /ad_consent /ad_publish(blocked) /ad_stats /ad_report (ad_proposals.py, ad_analytics.py) |
| native_member_interactions._ads_message | ported | ads: /ads /ad_draft /ad_consent /ad_publish(blocked) /ad_stats /ad_report (ad_proposals.py, ad_analytics.py) |
| native_member_interactions._growth_message | ported | application/business_flows/cockpit.py growth screen |
| native_member_interactions._growth_sales_message | ported | sales: /leads /lead_add /lead_card /lead_next /leads_due /lead_ai (sales.py, sales_ai.py) |
| native_member_interactions._growth_analysis_message | ported | ads: /ads /ad_draft /ad_consent /ad_publish(blocked) /ad_stats /ad_report (ad_proposals.py, ad_analytics.py) |
| native_member_interactions._event_action_command | ported | application/business_flows/cockpit_events.py (cpm:ev-conduct/ev-att/ev-texts over event_series) |
| native_member_interactions._event_projection_fallback | ported | application/business_flows/cockpit_events.py (cpm:ev-conduct/ev-att/ev-texts over event_series) |
| native_member_interactions._events_message | ported | application/business_flows/cockpit_events.py (cpm:ev-conduct/ev-att/ev-texts over event_series) |
| native_member_interactions._event_conduct_message | ported | application/business_flows/cockpit_events.py (cpm:ev-conduct/ev-att/ev-texts over event_series) |
| native_member_interactions._event_landing_item | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_status_text | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_message | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_texts_message | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_style_message | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_edit_message | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_edit_result | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_ai_confirm_message | obsolete | AI claim confirmation/ambiguity ledger replaced by idempotent draft facts (same as event_landing_builder) |
| native_member_interactions._event_landing_ai_result | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_ai_resolve_message | obsolete | AI claim confirmation/ambiguity ledger replaced by idempotent draft facts (same as event_landing_builder) |
| native_member_interactions._event_landing_ai_resolve_result | obsolete | AI claim confirmation/ambiguity ledger replaced by idempotent draft facts (same as event_landing_builder) |
| native_member_interactions._event_landing_theme_result | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_reset_result | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_preview_message | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_publish_result | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_landing_simple_result | ported | /landing (business_flow_ops._landing over event_landing) |
| native_member_interactions._event_content_message | ported | event editing: /landing sections + /event_place + /setting (event_landing.py, event_wizard.py) |
| native_member_interactions._event_followup_content_message | ported | application/business_flows/cockpit_events.py (cpm:ev-conduct/ev-att/ev-texts over event_series) |
| native_member_interactions._event_followup_edit_message | ported | event series text: /series /series_text /series_reset /followups (event_series.py) |
| native_member_interactions._event_followup_edit_result | ported | event series text: /series /series_text /series_reset /followups (event_series.py) |
| native_member_interactions._event_followup_reset_result | ported | event series text: /series /series_text /series_reset /followups (event_series.py) |
| native_member_interactions._event_settings_message | ported | event editing: /landing sections + /event_place + /setting (event_landing.py, event_wizard.py) |
| native_member_interactions._event_followups_action | ported | event_series /followups (followup_settings) |
| native_member_interactions._event_segment_action | ported | event_series /followups (followup_settings) |
| native_member_interactions._event_channel_action | obsolete | channel switch: only Telegram channel exists in port (same as event_followup_settings) |
| native_member_interactions._event_promotion_message | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._event_announcement_message | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._event_direction_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._event_new_entry_message | ported | event_wizard /new_event (6 steps, cpe:*) |
| native_member_interactions._event_new_direction_result | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._event_new_message | ported | event_wizard /new_event (6 steps, cpe:*) |
| native_member_interactions._event_create_result | ported | event_wizard /new_event (6 steps, cpe:*) |
| native_member_interactions._event_join_message | ported | /event_place (event_wizard.place_fact: online join URL) |
| native_member_interactions._event_join_result | ported | /event_place (event_wizard.place_fact: online join URL) |
| native_member_interactions._growth_more_message | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._growth_lifecycle_message | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._active_yandex_connection | ported | ads: /ads /ad_draft /ad_consent /ad_publish(blocked) /ad_stats /ad_report (ad_proposals.py, ad_analytics.py) |
| native_member_interactions._ad_channels_message | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._ad_channel_message | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._ai_visuals_message | ported | /visual (visual_creatives via YandexART executor effect) |
| native_member_interactions._ad_offers_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._ad_offer_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._acquisition_tool_rows | obsolete | acquisition tool catalog duplicated /ads+/partners+/landing in donor; superseded |
| native_member_interactions._acquisition_message | obsolete | acquisition tool catalog duplicated /ads+/partners+/landing in donor; superseded |
| native_member_interactions._creative_metric_from_code | obsolete | creative A/B trials need provider-reported metrics; no live Direct connector (publish gated) |
| native_member_interactions._creative_recommendation_text | obsolete | creative A/B trials need provider-reported metrics; no live Direct connector (publish gated) |
| native_member_interactions._creative_trial_reference | obsolete | creative A/B trials need provider-reported metrics; no live Direct connector (publish gated) |
| native_member_interactions._experiments_message | obsolete | creative A/B trials need provider-reported metrics; no live Direct connector (publish gated) |
| native_member_interactions._experiment_message | obsolete | creative A/B trials need provider-reported metrics; no live Direct connector (publish gated) |
| native_member_interactions._experiment_apply_message | obsolete | creative A/B trials need provider-reported metrics; no live Direct connector (publish gated) |
| native_member_interactions._directions_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_settings_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_subject_ids | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_results_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_goal_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_new_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_create_result | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_edit_message | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_edit_result | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_archive_confirm | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_archive_result | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._direction_restore_result | ported | catalog.py: /directions /direction /direction_add /direction_edit /direction_goal /direction_archive /direction_restore |
| native_member_interactions._manage_message | ported | application/business_flows/cockpit.py manage screen |
| native_member_interactions._business_profile_message | ported | catalog.py: /profile /profile_set |
| native_member_interactions._entrypoints_message | ported | bot/sources: /bot_status /connect_bot /landing /partners (bot_provisioning.py, event_landing.py, partners.py) |
| native_member_interactions._website_message | ported | bot/sources: /bot_status /connect_bot /landing /partners (bot_provisioning.py, event_landing.py, partners.py) |
| native_member_interactions._sources_message | ported | bot/sources: /bot_status /connect_bot /landing /partners (bot_provisioning.py, event_landing.py, partners.py) |
| native_member_interactions._integrations_message | ported | bot/sources: /bot_status /connect_bot /landing /partners (bot_provisioning.py, event_landing.py, partners.py) |
| native_member_interactions._manage_more_message | ported | nav: slash routes + /cockpit screens replace native button rows |
| native_member_interactions._team_message | ported | application/business_flows/cockpit.py team_screen (cpm:team/cpm:member over core.admin.roles_read_model) |
| native_member_interactions._today_full_message | ported | cockpit today screen |
| native_member_interactions._page_number | ported | application/business_flows/cockpit.py page_number |
| native_member_interactions._customer_message | ported | cockpit customers/customer screens |
| native_member_interactions._attention_message | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._publication_schedule_help | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_schedule_result | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_cancel_confirm | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_cancel_result | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._native_amount_minor | ported | money: /pay /payments /price (admin.py, cockpit_money.py) |
| native_member_interactions._native_amount_label | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._native_all_offerings | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._native_reference | ported | money: /pay /payments /price (admin.py, cockpit_money.py) |
| native_member_interactions._native_payment_summary_totals | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._publication_new_help | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_new_for_message | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_new_result | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_publish_result | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._payment_new_help | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._payment_new_result | ported | admin.record_payment 4th field links customer |
| native_member_interactions._payment_refund_confirm | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._payment_refund_result | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._price_set_help | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._price_set_result | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._invites_message | ported | invites.py via /invites, /invite_new |
| native_member_interactions._invite_new_result | ported | invites.py via /invites, /invite_new |
| native_member_interactions._automation_mutation_message | ported | admin: /audit /ops /cockpit /policy (admin.py, cockpit.py, automation_policy.py) |
| native_member_interactions._activity_edit_help | ported | catalog.py: /profile /profile_set |
| native_member_interactions._activity_edit_result | ported | catalog.py: /profile /profile_set |
| native_member_interactions._member_add_help | ported | core/policies/telegram/handlers/admin/roles_perms.py (/role_add|/role_del|/perm_add|/perm_del -> admin_set_role@v1) |
| native_member_interactions._member_add_role_message | ported | core/policies/telegram/handlers/admin/roles_perms.py (/role_add|/role_del|/perm_add|/perm_del -> admin_set_role@v1) |
| native_member_interactions._member_add_result | ported | core/policies/telegram/handlers/admin/roles_perms.py (/role_add|/role_del|/perm_add|/perm_del -> admin_set_role@v1) |
| native_member_interactions._member_role_result | ported | core/policies/telegram/handlers/admin/roles_perms.py (/role_add|/role_del|/perm_add|/perm_del -> admin_set_role@v1) |
| native_member_interactions._member_revoke_result | ported | core/policies/telegram/handlers/admin/roles_perms.py (/role_add|/role_del|/perm_add|/perm_del -> admin_set_role@v1) |
| native_member_interactions._growth_report_message | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._admin_report_message | ported | admin: /audit /ops /cockpit /policy (admin.py, cockpit.py, automation_policy.py) (programs section out of scope) |
| native_member_interactions._formats_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._format_toggle_result | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._tariff_message | obsolete | tariff/upgrade UI superseded by /pay paywall (same as admin_ops.get_subscription_state) |
| native_member_interactions._tariff_upgrade_message | obsolete | tariff/upgrade UI superseded by /pay paywall (same as admin_ops.get_subscription_state) |
| native_member_interactions._list_members | ported | application/business_flows/cockpit.py team_screen (cpm:team/cpm:member over core.admin.roles_read_model) |
| native_member_interactions._members_message | ported | application/business_flows/cockpit.py team_screen (cpm:team/cpm:member over core.admin.roles_read_model) |
| native_member_interactions._member_message | ported | application/business_flows/cockpit.py team_screen (cpm:team/cpm:member over core.admin.roles_read_model) |
| native_member_interactions._permissions_message | ported | application/business_flows/cockpit.py team_screen (cpm:team/cpm:member over core.admin.roles_read_model) |
| native_member_interactions._native_money_text | ported | application/business_flows/cockpit_money.py (cpm:payments/pay-refund/prices/growth-report) |
| native_member_interactions._native_journey_text | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._today_message | ported | application/business_flows/cockpit.py today screen (projection counts) |
| native_member_interactions._customers_message | ported | cockpit customers/customer screens |
| native_member_interactions._active_booking_offerings | ported | catalog.booking_offerings/resolve_slot_title: /add_slot #N binds offering, business tz |
| native_member_interactions._booking_offering_reference | ported | catalog.booking_offerings/resolve_slot_title: /add_slot #N binds offering, business tz |
| native_member_interactions._booking_open_message | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._booking_offering_exact | ported | catalog.booking_offerings/resolve_slot_title: /add_slot #N binds offering, business tz |
| native_member_interactions._booking_minimum_date | ported | catalog.booking_offerings/resolve_slot_title: /add_slot #N binds offering, business tz |
| native_member_interactions._booking_months_message | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._booking_dates_message | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._booking_times_message | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._booking_durations_message | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._booking_create_from_selection | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._booking_open_for_message | ported | booking: /book /slots /add_slot /my_bookings (bookings.py, cockpit_booking.py) |
| native_member_interactions._booking_open_failure_message | ported | booking: /book /slots /add_slot /my_bookings (bookings.py, cockpit_booking.py) |
| native_member_interactions._booking_open_create_message | ported | application/business_flows/cockpit_booking.py (bookings.parse_slot) |
| native_member_interactions._bookings_message | ported | application/business_flows/cockpit.py bookings screen (paged) |
| native_member_interactions._offering_new_help | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_capability | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_direction_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_input_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_new_for_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_new_result | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_retire_list_message | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_retire_confirm | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._offering_retire_result | ported | catalog.py: /offerings /offering_add /offering_retire /formats /format_on /format_off |
| native_member_interactions._publication_retire_list_message | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_retire_confirm | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._publication_retire_result | ported | application/business_flows/publications.py (/post_add|/post_schedule|/post_unschedule|/post_publish|/post_retire) |
| native_member_interactions._messengers_message | ported | application/business_flows/cockpit.py messengers screen (bot provisioning states) |
| native_member_interactions._setup_message | ported | owner_panels + business_catalog_ops._panels (/announce,/event_promo,/attention,/ad_channels,/ad_channel,/setup_channel,/journey, owner /me); texts follow donor; landing/venue rows and AI announcement not present (no landing pages, AI variant not ported); attention failed = due reminder unsent >15m |
| native_member_interactions._render | ported | cockpit.render |
| native_member_interactions.render_native_member_interaction | ported | business_flow_ops._cockpit |
| native_member_interactions.process_native_member_interaction | ported | business_flow_ops._cockpit via DecisionCore → executor send_message (reply_markup) |
| native_messenger_onboarding._public_base_url | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| native_messenger_onboarding._webhook_secret | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted; webhook secret derived HMAC(server_key, route_id) instead of random+stored, so retries reuse it and no secret is stored in facts; lease release = nm_active/nm_disabled fact or TTL expiry |
| native_messenger_onboarding._webhook_url | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| native_messenger_onboarding._existing_webhook_secret | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted; webhook secret derived HMAC(server_key, route_id) instead of random+stored, so retries reuse it and no secret is stored in facts; lease release = nm_active/nm_disabled fact or TTL expiry |
| native_messenger_onboarding._persist_native_connection | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| native_messenger_onboarding._acquire_provisioning_lease | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| native_messenger_onboarding._release_provisioning_lease | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted; webhook secret derived HMAC(server_key, route_id) instead of random+stored, so retries reuse it and no secret is stored in facts; lease release = nm_active/nm_disabled fact or TTL expiry |
| native_messenger_onboarding._release_provisioning_lease_if_owned | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted; webhook secret derived HMAC(server_key, route_id) instead of random+stored, so retries reuse it and no secret is stored in facts; lease release = nm_active/nm_disabled fact or TTL expiry |
| native_messenger_onboarding._disable_after_provider_failure | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| native_messenger_onboarding.provision_max_channel | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| native_messenger_onboarding.provision_vk_channel | ported | business_flows/native_channels.py (pure, business_admin@v1 nm_* facts; bodies compared) + runtime/integration/native_messenger_inbound (VK confirmation/secret, MAX secret header -> existing messaging_ingress vk/max adapters). Caveat: provider client injected (no live VK/MAX HTTP client in bai-port), HTTP route not mounted |
| owner_input.get_owner_input_session | obsolete | pending free-text сессия заменена командами с аргументами: /offering_add /direction_add /direction_edit /add_slot /schedule /landing /series_text /followups /warmup_days /event_place (online room) /price /pay /invite_new /post_add; program_* — вне скоупа |
| owner_input.begin_owner_input | obsolete | pending free-text сессия заменена командами с аргументами: /offering_add /direction_add /direction_edit /add_slot /schedule /landing /series_text /followups /warmup_days /event_place (online room) /price /pay /invite_new /post_add; program_* — вне скоупа |
| owner_input.clear_owner_input | obsolete | pending free-text сессия заменена командами с аргументами: /offering_add /direction_add /direction_edit /add_slot /schedule /landing /series_text /followups /warmup_days /event_place (online room) /price /pay /invite_new /post_add; program_* — вне скоупа |
| owner_input.resolve_owner_input | obsolete | pending free-text сессия заменена командами с аргументами: /offering_add /direction_add /direction_edit /add_slot /schedule /landing /series_text /followups /warmup_days /event_place (online room) /price /pay /invite_new /post_add; program_* — вне скоупа |
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
| partner_runtime.list_partner_campaigns | ported | partners.replay over partners@v1 facts |
| partner_runtime.partner_stats | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime.list_partner_candidates | ported | /partners |
| partner_runtime.get_partner_candidate_view | ported | /partner_pitch |
| partner_runtime.list_partner_send_connections | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime.authorize_partner_telegram_contact | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime.queue_partner_outreach | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime.approve_and_queue_partner_email_outreach | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime.set_partner_candidate_status | ported | partners.set_status |
| partner_runtime.record_partner_reply_if_expected | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime.list_partner_replies | ported | application/business_flows/partner_outreach.py: send_connections/authorize_telegram_contact/queue_outreach (owner-approval gate for public email)/record_reply_if_expected/replies/stats; facts only, outbox sends |
| partner_runtime._value | obsolete | DB row accessor; facts are dicts |
| partner_scoring.score_partner | ported | partners.rank |
| partner_scoring._audience_score | ported | partners.rank |
| partner_scoring._semantic_overlap | ported | partners.rank |
| partner_scoring._norm | ported | partners.rank |
| promotion_creatives._compact | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotion_creatives._business_kind | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotion_creatives._candidate | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotion_creatives._safe_fallback | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotion_creatives.generate_promotion_candidates | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotion_creatives._score_candidate | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotion_creatives.select_promotion_creative | ported | business_flows/promotions.py candidates/select/validate: same three variant sets per kind, same fallbacks and score |
| promotions._capture_verified_promotion_touch | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.promotion_start_payload | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.promotion_public_url | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.parse_promotion_start_payload | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.list_promotable_slots | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.create_slot_promotion | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.list_promotion_campaigns | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.promotion_stats | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions._open_channel_promotion_in_conn | ported | promotions.open_channel/open_channel_for_identity (tenant-replayed campaigns, active customer/identity required, one opened fact per customer) + native_messenger_inbound.promotion_touch for VK/MAX /start cpa_ |
| promotions.open_channel_promotion | ported | promotions.open_channel/open_channel_for_identity (tenant-replayed campaigns, active customer/identity required, one opened fact per customer) + native_messenger_inbound.promotion_touch for VK/MAX /start cpa_ |
| promotions.open_channel_promotion_for_identity | ported | promotions.open_channel/open_channel_for_identity (tenant-replayed campaigns, active customer/identity required, one opened fact per customer) + native_messenger_inbound.promotion_touch for VK/MAX /start cpa_ |
| promotions.open_promotion_link | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.book_promoted_slot | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| promotions.__post_init__ | ported | business_flows/promotions.py + catalog_ops._promotions: bodies compared; opened/booked facts in bookings@v1; Telegram /start cpa_ deep link; tenant-scoped via event store |
| retention._stamp | obsolete | tz-aware datetime stamp; port uses epoch ms |
| retention._next_action | ported | retention.py: /retention cohorts over bookings, /reactivate -> sales lead (no send) |
| retention._reactivation_cohort | ported | retention.py: /retention cohorts over bookings, /reactivate -> sales lead (no send) |
| retention._validate_existing_payment | obsolete | outcome-table cross-validation; repeat payment recorded via /lead N paid + /pay with idempotent payment refs |
| retention._validate_existing_reactivation | obsolete | outcome-table cross-validation; repeat payment recorded via /lead N paid + /pay with idempotent payment refs |
| retention.list_retention_candidates | ported | retention.py: /retention cohorts over bookings, /reactivate -> sales lead (no send) |
| retention.list_reactivation_opportunities | ported | retention.py: /retention cohorts over bookings, /reactivate -> sales lead (no send) |
| retention.prepare_reactivation_sales_lead | ported | retention.py: /retention cohorts over bookings, /reactivate -> sales lead (no send) |
| retention.record_reactivation_result | obsolete | outcome-table cross-validation; repeat payment recorded via /lead N paid + /pay with idempotent payment refs |
| sales_ai_orchestration._row_value | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration._owner_actor | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration.canonical_sales_ai_parameters | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration.claim_sales_ai_jobs | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration._prepare_analysis_egress | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration.sales_ai_analysis_egress_permit | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration._candidate_payload | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration.apply_sales_ai_analysis | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration.cancel_sales_ai_job | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration.retry_sales_ai_job | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration._prepare_draft_egress | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration.sales_ai_draft_egress_permit | ported | application/business_flows/sales_ai.py + /lead_ai (marketing_llm_complete, YandexGPT/GigaChat only) |
| sales_ai_orchestration.__init__ | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration._run | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration.__aenter__ | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_orchestration.__aexit__ | obsolete | DB job queue/lease/thread runner replaced by one synchronous executor LLM call per /lead_ai; no job rows exist |
| sales_ai_settings.business_sales_ai_consent_in_conn | ported | admin settings sales_ai / sales_ai_mode checked by sales_ai.egress_permit |
| sales_ai_settings.business_sales_ai_enabled_in_conn | ported | admin settings sales_ai / sales_ai_mode checked by sales_ai.egress_permit |
| sales_ai_settings.get_business_sales_ai_consent | ported | admin settings sales_ai / sales_ai_mode checked by sales_ai.egress_permit |
| sales_ai_settings.get_business_sales_ai_enabled | ported | admin settings sales_ai / sales_ai_mode checked by sales_ai.egress_permit |
| sales_ai_settings.set_business_sales_ai_enabled | ported | admin settings sales_ai / sales_ai_mode checked by sales_ai.egress_permit |
| sales_followups.schedule_sales_followup | ported | application.business_flows.sales.set_next (owner reminder) |
| sales_followups.get_active_sales_followup | ported | application.business_flows.sales.due_actions |
| sales_handoff.open_sales_handoff | ported | application.business_flows.sales.apply_event 'handoff' |
| sales_handoff.list_sales_handoffs | ported | application.business_flows.sales.render (нужен человек) |
| sales_handoff.resolve_sales_handoff | ported | application.business_flows.sales.apply_event 'resume' |
| sales_intelligence.extract_customer_message_text | ported | sales_inbound.py |
| sales_intelligence.normalize_customer_message_text | ported | sales_inbound.py |
| sales_intelligence._owner_actor | obsolete | owner actor lookup in business_members SQL; port facts are tenant-scoped, no actor resolution needed |
| sales_intelligence._printable | ported | sales_inbound.py |
| sales_metrics.get_sales_funnel_snapshot | ported | application.business_flows.sales.funnel |
| sales_operations.transition_sales_lead | ported | application.business_flows.sales.apply_event |
| sales_operations.set_sales_next_action | ported | application.business_flows.sales.set_next |
| sales_operations.add_sales_note | ported | application.business_flows.sales.add_note |
| sales_orchestration._bounded_score | ported | application/business_flows/sales_orchestration.py: orchestrate/evaluate_handoff/plan_action/select_candidate/approve_plan/authorize_outbound over sales_pipeline facts; no sends |
| sales_orchestration._row_value | obsolete | DB row accessor; equivalent is fact replay plans() in sales_orchestration.py |
| sales_orchestration._select_commercial_candidate | ported | application/business_flows/sales_orchestration.py: orchestrate/evaluate_handoff/plan_action/select_candidate/approve_plan/authorize_outbound over sales_pipeline facts; no sends |
| sales_orchestration.orchestrate_sales_signal_in_transaction | ported | application/business_flows/sales_orchestration.py: orchestrate/evaluate_handoff/plan_action/select_candidate/approve_plan/authorize_outbound over sales_pipeline facts; no sends |
| sales_orchestration.orchestrate_sales_signal | ported | application/business_flows/sales_orchestration.py: orchestrate/evaluate_handoff/plan_action/select_candidate/approve_plan/authorize_outbound over sales_pipeline facts; no sends |
| sales_orchestration.authorize_sales_outbound | ported | application/business_flows/sales_orchestration.py: orchestrate/evaluate_handoff/plan_action/select_candidate/approve_plan/authorize_outbound over sales_pipeline facts; no sends |
| sales_orchestration.approve_and_authorize_sales_outbound | ported | application/business_flows/sales_orchestration.py: orchestrate/evaluate_handoff/plan_action/select_candidate/approve_plan/authorize_outbound over sales_pipeline facts; no sends |
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
| ucr_attendance_observations._uint | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations._optional_unix_ms | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations._proto_bytes | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations._requested_external_user_id | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations.parse_ucr_participant_attendance | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations._provenance_ref | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations._observed_at | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations._duration_label | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations.ucr_attendance_to_observation | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations.read_ucr_attendance_observation | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations.invoke_universal_conference | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| ucr_attendance_observations.has_attendance | ported | interfaces/ucr/attendance.py (+ attendance_fact -> event_series) |
| visual_aesthetic_director._clean | ported | visual_creatives.invents_fact/sanitize_direction/_clean |
| visual_aesthetic_director.invents_fact | ported | visual_creatives.invents_fact/sanitize_direction/_clean |
| visual_aesthetic_director.sanitize_visual_direction | ported | visual_creatives.invents_fact/sanitize_direction/_clean |
| visual_creatives._brief_dict | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.visual_generation_ready | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.visual_video_generation_mode | obsolete | video: no Russian video provider on sovereign allowlist |
| visual_creatives.freeze_business_visual_payload | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.freeze_business_image_payload | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.freeze_business_video_payload | obsolete | video: no Russian video provider on sovereign allowlist |
| visual_creatives._load_frozen_business_visual_payload | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives._load_frozen_business_image_payload | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.frozen_business_visual_kind | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.frozen_business_visual_style | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.normalize_business_image_request | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.build_business_visual_brief | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.build_business_image_brief | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.create_business_visual_from_frozen_payload | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.create_business_image_from_frozen_payload | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.create_business_video_from_frozen_payload | obsolete | video: no Russian video provider on sovereign allowlist |
| visual_creatives.create_business_image | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.build_ad_visual_brief | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.create_ad_visual | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.materialize_ad_visual | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.poll_ad_visual | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_creatives.wait_ad_visual | ported | application/business_flows/visual_creatives.py + runtime yandex_art_generate/call_yandex_art (image.yandex_art.generate effect) |
| visual_scene_planning._truthy | ported | visual_scene.py: grounded planner + deterministic contract; injected RU chat client |
| visual_scene_planning._json_object | ported | visual_scene.py: grounded planner + deterministic contract; injected RU chat client |
| visual_scene_planning._grounded_items | ported | visual_scene.py: grounded planner + deterministic contract; injected RU chat client |
| visual_scene_planning._grounded_text | ported | visual_scene.py: grounded planner + deterministic contract; injected RU chat client |
| visual_scene_planning.grounded_scene_contract_from_mapping | ported | visual_scene.py: grounded planner + deterministic contract; injected RU chat client |
| visual_scene_planning.plan_visual_scene_contract | ported | visual_scene.py: grounded planner + deterministic contract; injected RU chat client |
| visual_style_preferences.load_visual_style_preference | ported | visual_creatives.save_style + replay styles |
| visual_style_preferences.save_visual_style_preference | ported | visual_creatives.save_style + replay styles |
| yandex_growth_analytics._percent | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics._unit_cost | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics._report_zone | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._current_period | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._event_window | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._value | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._load_tracked_ads | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._load_local_attribution | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._refresh_bundle | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._ad_id_batches | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics._provider_rows | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics.get_yandex_growth_snapshot | ported | yandex_growth.py: read-only snapshot over ad_publication_jobs ledger + Session refresh-once; injected provider; no cross-currency cost sums |
| yandex_growth_analytics.ctr_percent | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.cpc_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.cpl_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.booking_cost_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.cac_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.ctr_percent | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.cpc_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.cpl_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.booking_cost_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |
| yandex_growth_analytics.cac_micros | ported | ad_analytics: owner-entered Direct stats + local lead attribution |

Remaining by module (functions / lines):

visual_scene_variants 22/712, visual_brand_discovery 21/370, event_commercial_consent 9/296, visual_creatives 11/292, event_owner_flow 12/276, native_customer_interactions 14/270, creative_studio_publication 17/262, event_conference_join 12/240, event_delivery_targets 4/228, sales_intelligence 3/227, yandex_campaign_diagnostics 10/226, partner_growth 9/216, ad_spend 11/210, customer_timeline 10/210, owner_booking_journey 6/209, bot_gateway 10/208, ad_goal_autopilot 5/206, ad_spend_operations 7/206, native_member_interactions 6/201, event_growth 14/193, capability_parity 11/186, public_business_entry 5/185, cockpit_growth_analytics 11/180, growth_cockpit 11/180, event_public_surface 5/178, event_sessions 8/178, managed_bot_owner 8/175, creative_winner 7/174, creative_growth_optimizer 5/173, managed_bot_onboarding 11/173, messenger_switching 10/173, editable_advertising 10/166, creative_studio 8/154, event_analytics 9/145, promotion_attribution 4/143, ucr_attendance_pilot 4/136, event_followups 5/132, event_content_plans 7/131, event_content_assets 4/129, ad_spend_control 5/112, creative_generation 10/111, event_warmups 4/109, creative_growth_analytics 4/108, sales_ai_orchestration 5/105, activity_directions 9/104, ad_spend_consent 5/101, ai_commerce 4/101, cockpit_customers 5/101, connections 9/99, messenger_channels 5/98, customers 8/93, support_cases 8/93, event_customer_projection 2/91, email_connections 2/87, acquisition_destination 4/79, visual_scene_plan_receipts 5/79, owner_onboarding 5/73, sales_agent 4/73, ad_provider_session 5/69, platform_directory 5/68, revenue_attribution 3/65, sales_ai_drafts 5/62, tenancy 9/60, visual_aesthetic_director 3/60, event_reminder_channels 1/57, ad_publication_customization 3/55, creative_growth_optimization 2/52, event_announcements 1/51, sales_workspace 7/48, cockpit_events 2/42, partner_attribution 2/38, attribution 2/34, business_profile 5/34, sales_followups 3/34, sales_handoff 2/33, cockpit_calendar_management 2/31, cockpit_home 2/30, customer_role_guard 2/30, outcomes 1/28, partner_runtime 2/27, yandex_growth_analytics 2/24, activity 3/21, ad_oauth_sessions 1/20, cockpit_sales_management 2/20, existing_bot_onboarding 3/20, native_messenger_setup 3/18, sales_operations 3/18, cockpit_services 2/16, sales_ui 2/13, ad_connections 1/12, sales_ai_settings 2/12, control_callbacks 2/5, event_promotion 1/5, visual_style_preferences 1/3

