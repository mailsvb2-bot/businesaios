from crm.actions.crm_append_note_action import CrmAppendNoteAction


def test_action_has_stable_type():
    assert CrmAppendNoteAction().action_type == 'crm.append_note'
