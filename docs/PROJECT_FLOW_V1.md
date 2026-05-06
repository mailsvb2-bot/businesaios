# PROJECT_FLOW_V1

```mermaid
flowchart TD
    U[User / Operator] --> I1[interfaces/api]
    U --> I2[interfaces/telegram]

    I1 --> APP[runtime/application service]
    I2 --> APP

    APP --> DEC[Canonical decision/recommendation path]
    DEC --> RT[runtime registry + executor]

    RT --> FX[runtime effects boundary]
    FX --> EXT[External providers/connectors]

    DEC --> BH[core/behavior engine]
    BH --> BR[behavior integration bridges]
    BR --> RT

    RT --> GOV[infra governance + control plane]
    GOV --> AP[approvals / policy versioning]
    GOV --> RB[release promotion / rollback]
    GOV --> EV[evidence + audit trail]

    RT --> OBS[observability metrics/traces/events]
    GOV --> OBS
    BH --> OBS

    OBS --> OP[Ops / Monitoring]
    EV --> OP
```

## Notes

- Interfaces stay thin and call application contracts only.
- Decision intent is generated in canonical path; execution is isolated in runtime effects.
- Governance and compliance can gate, approve, rollback, and record evidence.
- Behavior engine enriches constraints/observables without creating a second brain.
