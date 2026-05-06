from __future__ import annotations


class CrmPipelineFieldPolicy:
    REQUIRED_FIELDS = ('name', 'stages')

    def validate_definition(self, payload: dict[str, object]) -> None:
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in payload:
                raise ValueError(f'Missing CRM pipeline field: {field_name}')
