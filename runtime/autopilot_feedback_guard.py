from __future__ import annotations


class AutopilotFeedbackGuardViolation(Exception):
    """Raised when action generation and evaluation are improperly coupled."""


class AutopilotFeedbackGuard:
    """
    Protects against 'same brain both acts and judges' architecture.

    Example of forbidden chain:
        same_component -> action generation
        same_component -> evaluation
        same_component -> retraining decision
    """

    def validate_action_vs_evaluation(
        self,
        action_origin: str,
        evaluation_origin: str,
    ) -> None:
        if not action_origin or not evaluation_origin:
            raise AutopilotFeedbackGuardViolation(
                "Both action_origin and evaluation_origin are required."
            )

        if action_origin == evaluation_origin:
            raise AutopilotFeedbackGuardViolation(
                "Action generator and evaluator must be different components."
            )

    def validate_evaluation_vs_retraining(
        self,
        evaluation_origin: str,
        retraining_origin: str,
    ) -> None:
        if not evaluation_origin or not retraining_origin:
            raise AutopilotFeedbackGuardViolation(
                "Both evaluation_origin and retraining_origin are required."
            )

        if evaluation_origin == retraining_origin:
            raise AutopilotFeedbackGuardViolation(
                "Evaluator and retraining trigger must be different components."
            )

    def validate_full_chain(
        self,
        action_origin: str,
        evaluation_origin: str,
        retraining_origin: str,
    ) -> None:
        self.validate_action_vs_evaluation(action_origin, evaluation_origin)
        self.validate_evaluation_vs_retraining(evaluation_origin, retraining_origin)

        if action_origin == retraining_origin:
            raise AutopilotFeedbackGuardViolation(
                "Action generator and retraining trigger must be different components."
            )


# Compatibility alias for older code paths.
AutopilotFeedbackFirewall = AutopilotFeedbackGuard
