
from src.application.report_service import ChartData
from src.domain.enums import Axis
from src.ui.theme import is_dark


_LIGHT = {
    'text': '#334155',
    'axis': '#94a3b8',
    'grid': '#e2e8f0',
    'title': '#0f172a',
}

_DARK = {
    'text': '#CBD5E1',
    'axis': '#64748B',
    'grid': '#1E2F3C',
    'title': '#F1F5F9',
}


def chart_colors() -> dict:
    return _DARK if is_dark() else _LIGHT


def y_axis(name: str, position: str, with_grid: bool) -> dict:
    c = chart_colors()

    return {
        'type': 'value',
        'name': name,
        'position': position,
        'scale': True,
        'nameTextStyle': {'color': c['text']},
        'axisLabel': {'color': c['text']},
        'axisLine': {'show': True, 'lineStyle': {'color': c['axis']}},
        'splitLine': {
            'show': with_grid,
            'lineStyle': {'color': c['grid']},
        },
    }


def chart_options(title: str, data: ChartData) -> dict:
    c = chart_colors()

    names_by_axis = {Axis.LEFT: [], Axis.RIGHT: []}

    for s in data.series:
        names_by_axis[s.axis].append(s.name)

    axes = [
        a for a in (Axis.LEFT, Axis.RIGHT)
        if names_by_axis[a]
    ]

    index = {a: i for i, a in enumerate(axes)}
    series = []

    for s in data.series:
        item = {
            'name': s.name,
            'type': 'line',
            'yAxisIndex': index[s.axis],
            'showSymbol': False,
            'lineStyle': {'color': s.color, 'width': 2},
            'itemStyle': {'color': s.color},
            'data': s.points,
        }

        if data.ordered:
            item['sampling'] = 'lttb'

        series.append(item)

    return {
        'title': {
            'text': title,
            'left': 'center',
            'textStyle': {'color': c['title']},
        },
        'tooltip': {'trigger': 'axis'},
        'legend': {
            'top': 30,
            'textStyle': {'color': c['text']},
        },
        'toolbox': {
            'right': 10,
            'feature': {'restore': {'title': 'Restaurar zoom'}},
            'iconStyle': {'borderColor': c['text']},
        },
        'grid': {
            'left': 70,
            'right': 70 if len(axes) == 2 else 30,
            'top': 80,
            'bottom': 95,
        },
        'dataZoom': [
            {'type': 'inside', 'xAxisIndex': 0},
            {
                'type': 'slider',
                'xAxisIndex': 0,
                'textStyle': {'color': c['text']},
            },
        ],
        'xAxis': {
            'type': 'value',
            'name': data.x_label,
            'nameLocation': 'middle',
            'nameGap': 30,
            'scale': True,
            'nameTextStyle': {'color': c['text']},
            'axisLabel': {'color': c['text']},
            'axisLine': {'lineStyle': {'color': c['axis']}},
            'splitLine': {'show': False},
        },
        'yAxis': [
            y_axis(
                ' / '.join(names_by_axis[a]),
                'left' if a is Axis.LEFT else 'right',
                a is axes[0],
            )
            for a in axes
        ],
        'series': series,
    }
