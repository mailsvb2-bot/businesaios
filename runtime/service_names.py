from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeServiceName:
    OBSERVABILITY: str = "observability"
    ARCHITECTURE_WATCH: str = "architecture_watch"
    STRUCTURE_WATCH: str = "structure_watch"
    FLOW_WATCH: str = "flow_watch"
    DIFFUSION_WATCH: str = "diffusion_watch"
    MARKET_WATCH: str = "market_watch"
    MANAGED_RUNTIME_PLANE: str = "managed_runtime_plane"
    MARKET_INTELLIGENCE_RUNTIME: str = "market_intelligence_runtime"
    CREATIVE_INTELLIGENCE: str = "creative_intelligence"
    AUTONOMY_ADVISOR: str = "autonomy_advisor"
    WORLD_STATE_INTEGRATION: str = "world_state_integration"
    DECISION_INPUT_SERVICE: str = "decision_input_service"
    DECISION_GATEWAY: str = "decision_gateway"
    RUNTIME_STATE_ENRICHMENT: str = "runtime_state_enrichment"
    RUNTIME_PACKET_PROVIDER: str = "runtime_packet_provider"
    RISK_ENGINE: str = "risk_engine"
    REWARD_GUARD: str = "reward_guard"
    SIMULATION_GATE: str = "simulation_gate"
    KILL_SWITCH: str = "kill_switch"
    ACTION_BUDGET: str = "action_budget"
    GOVERNANCE_CHAIN: str = "governance_chain"
    ACTION_EXECUTOR: str = "action_executor"
    DECISION_CORE: str = "decision_core"
