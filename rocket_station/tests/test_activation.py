import pytest

from rocket_station.domain.activation import (
    ACK_TIMEOUT_S,
    COUNTDOWN_S,
    Activation,
    LinkSnapshot,
    StageState,
    TickAction,
)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def snap(**changes):
    values = dict(connected=True, acks={1: 1, 2: 1, 3: 1}, recording=True, silence_s=0.1)
    values.update(changes)
    return LinkSnapshot(**values)


@pytest.fixture
def env():
    clock = Clock()
    return Activation(clock), clock


def test_stage_states(env):
    activation, clock = env
    assert activation.stage_state(1, snap(acks={})) is StageState.UNKNOWN
    assert activation.stage_state(1, snap(acks={1: 0})) is StageState.OFF
    activation.mark_sent(1)
    assert activation.stage_state(1, snap(acks={1: 0})) is StageState.SENT
    clock.now += ACK_TIMEOUT_S + 1
    assert activation.stage_state(1, snap(acks={1: 0})) is StageState.NO_CONFIRMATION
    assert activation.stage_state(1, snap(acks={1: 1})) is StageState.CONFIRMED


def test_stages_must_be_armed_in_order(env):
    activation, _ = env
    assert activation.arm_blocker(2, snap(acks={1: 0})) != ''
    assert activation.arm_blocker(1, snap(acks={1: 0})) == ''
    assert activation.arm_blocker(2, snap(acks={1: 1, 2: 0})) == ''


@pytest.mark.parametrize(
    'changes',
    [
        {'connected': False},
        {'acks': {1: 1, 2: 1, 3: 0}},
        {'acks': {1: 1, 2: 1}},
        {'recording': False},
        {'silence_s': 5.0},
        {'silence_s': None},
    ],
)
def test_ignition_is_blocked(env, changes):
    activation, _ = env
    assert activation.ignition_blocker(snap(**changes)) != ''


def test_ignition_is_released_when_everything_is_fine(env):
    assert env[0].ignition_blocker(snap()) == ''


def test_countdown_fires_only_after_the_time(env):
    activation, clock = env
    activation.start_countdown('A1')
    clock.now += COUNTDOWN_S - 0.1
    assert activation.tick(snap()).action is TickAction.NONE
    clock.now += 0.2
    assert activation.tick(snap()).action is TickAction.FIRE
    assert not activation.counting


@pytest.mark.parametrize(
    'changes',
    [
        {'silence_s': 4.0},
        {'acks': {1: 1, 2: 1, 3: 0}},
        {'recording': False},
        {'panel_visible': False},
        {'connected': False},
    ],
)
def test_countdown_aborts_when_a_condition_fails(env, changes):
    activation, clock = env
    activation.start_countdown('A1')
    clock.now += 1
    result = activation.tick(snap(**changes))
    assert result.action is TickAction.ABORT and result.reason and not activation.counting


def test_ignition_can_only_be_sent_once_until_disarmed(env):
    activation, _ = env
    activation.mark_ignition_sent()
    assert 'já foi enviada' in activation.ignition_blocker(snap())
    activation.disarm()
    assert activation.ignition_blocker(snap()) == ''


def test_disarm_cancels_the_countdown(env):
    activation, _ = env
    activation.start_countdown('A1')
    assert activation.disarm() is True and not activation.counting