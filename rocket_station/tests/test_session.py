from src.ui.state.session import SessionState


def test_activate_notifies_only_on_change():
    session, calls = SessionState(), []
    session.on_active_change(lambda: calls.append(session.active_code))
    session.activate('A1')
    session.activate('A1')
    session.activate('A1', force=True)
    session.activate(None)
    assert calls == ['A1', 'A1', None]


def test_request_edit_goes_through_the_guard():
    session, asked = SessionState(), []
    session.edit_guard = asked.append
    session.request_edit('A1')
    assert asked == ['A1'] and session.editing_code is None


def test_request_edit_without_guard_edits_right_away():
    session = SessionState()
    session.request_edit('A1')
    assert session.editing_code == 'A1'


def test_list_and_data_listeners():
    session, calls = SessionState(), []
    session.on_list_change(lambda: calls.append('list'))
    session.on_data_change(lambda: calls.append('data'))
    session.list_changed()
    session.data_changed()
    assert calls == ['list', 'data']