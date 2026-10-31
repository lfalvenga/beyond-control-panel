GRAY, GREEN, YELLOW, RED = 'text-gray-400', 'text-green-400', 'text-yellow-400', 'text-red-400'


def higher_is_better(value: float | None, green: float, yellow: float) -> str:
    if value is None:
        return GRAY
    return GREEN if value >= green else YELLOW if value >= yellow else RED


def lower_is_better(value: float | None, green: float, yellow: float) -> str:
    if value is None:
        return GRAY
    return GREEN if value <= green else YELLOW if value <= yellow else RED