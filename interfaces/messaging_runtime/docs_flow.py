CANONICAL_DATA_FLOW = (
    "inbound raw -> parse -> MessageEnvelope -> route -> worldstate -> view -> "
    "OutboundEnvelope -> queue -> dispatcher -> ack reconciliation -> telemetry/audit"
)
