# runtime/handlers/ads_autopilot

Role:
- strict route extraction
- payload normalization
- handoff into guarded runtime flow

Must NOT contain:
- business decision logic
- direct policy authority
- alternative execution paths bypassing RuntimeGuard
