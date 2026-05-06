from contracts.executable_action import ExecutableAction


class ActionValidator:
    def validate(self, action: ExecutableAction) -> tuple[bool, list[str]]:
        if not isinstance(action, ExecutableAction):
            return False, ['invalid:contract_type']
        errors = action.validate_contract()
        return not errors, errors
