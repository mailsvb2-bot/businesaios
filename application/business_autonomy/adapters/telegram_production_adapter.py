from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import (
    ChannelCapabilityDescriptor,
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, ExecutionVerdict

CANON_TELEGRAM_PRODUCTION_ADAPTER = True


@dataclass(frozen=True)
class TelegramBotCredentials:
    bot_token: str

    def validate(self) -> None:
        if ':' not in str(self.bot_token or ''):
            raise ValueError('telegram bot token must look like BOT_ID:TOKEN')


class TelegramProductionAdapter(BaseStaticChannelAdapter):
    channel_kind = ChannelKind.CHATBOT
    adapter_key = 'chatbot.telegram'
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor('telegram.send', ('message_send', 'message_edit'), write_enabled=True, human_verification_required=False),
            ChannelCapabilityDescriptor('telegram.read', ('message_read', 'user_profile_read'), write_enabled=False, human_verification_required=False),
        ),
    )

    def discover_capabilities(self, *, identity: ChannelIdentity) -> Sequence[ChannelCapabilityDescriptor]:
        capabilities = super().discover_capabilities(identity=identity)
        return tuple(capabilities)

    async def execute(self, *, envelope: ChannelExecutionEnvelope, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        result = await super().execute(envelope=envelope, request=request)
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.SIMULATED if request.envelope.simulation else ExecutionVerdict.COMPLETED,
            business_id=result.business_id,
            goal_id=result.goal_id,
            execution_id=result.execution_id,
            message='telegram production adapter accepted execution envelope',
            metrics={**dict(result.metrics or {}), 'transport': 'telegram_bot_api'},
            evidence=result.evidence,
            delegated_to_domain_engine=True,
            adapter_name=self.adapter_key,
            metadata={**dict(result.metadata or {}), 'provider': 'telegram'},
        )

    def credential_contract(self) -> dict[str, str]:
        return {'bot_token': 'telegram bot token from BotFather'}
