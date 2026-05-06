# Ads Creative Autopilot (text-only)

This module generates and selects ad creatives for offers.

## Why
- Ads Autopilot without creatives is incomplete.
- This adds a SAFE creative generator with guardrails.

## Modes
1) Template-only (default): uses `interfaces.llm.TemplatedLLM`.
2) External LLM (optional): implement `LLMClient` via sealed effects.

## Guardrails
Conservative by default:
- no medical guarantees
- no shaming language
- no excessive punctuation / all-caps

## Events
- `ads_creative_generated` (selection record; wire it into your event_store)

## CLI
```bash
python tools/ads_creatives_generate.py \
  --offer-arm offer_std_cleaning \
  --business-type "Стоматология" \
  --offer-title "Чистка зубов со скидкой" \
  --offer-details "Запись онлайн. Подходит для первичного визита." \
  --n 3
```
