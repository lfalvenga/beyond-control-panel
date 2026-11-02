from src.application.report_service import ChartData
from src.domain.enums import Axis

TEXT = '#334155'
AXIS = '#94a3b8'
GRID = '#e2e8f0'
TITLE = '#0f172a'


def y_axis(name: str, position: str, with_grid: bool) -> dict:
    return {
        'type': 'value',
        'name': name,
        'position': position,
        'scale': True,  # não força o zero: dá para ver variações pequenas
        'nameTextStyle': {'color': TEXT},
        'axisLabel': {'color': TEXT},
        'axisLine': {'show': True, 'lineStyle': {'color': AXIS}},
        'splitLine': {'show': with_grid, 'lineStyle': {'color': GRID}},
    }


def chart_options(title: str, data: ChartData) -> dict:
    names_by_axis = {Axis.LEFT: [], Axis.RIGHT: []}
    for s in data.series:
        names_by_axis[s.axis].append(s.name)
    axes = [a for a in (Axis.LEFT, Axis.RIGHT) if names_by_axis[a]]  # só o eixo que alguém usa
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
            item['sampling'] = 'lttb'  # reduz a densidade só na exibição
        series.append(item)
    return {
        'title': {'text': title, 'left': 'center', 'textStyle': {'color': TITLE}},
        'tooltip': {'trigger': 'axis'},
        'legend': {'top': 30, 'textStyle': {'color': TEXT}},
        'toolbox': {
            'right': 10,
            'feature': {'restore': {'title': 'Restaurar zoom'}},
            'iconStyle': {'borderColor': TEXT},
        },
        'grid': {'left': 70, 'right': 70 if len(axes) == 2 else 30, 'top': 80, 'bottom': 95},
        'dataZoom': [
            {'type': 'inside', 'xAxisIndex': 0},
            {'type': 'slider', 'xAxisIndex': 0, 'textStyle': {'color': TEXT}},
        ],
        'xAxis': {
            'type': 'value',
            'name': data.x_label,
            'nameLocation': 'middle',
            'nameGap': 30,
            'scale': True,
            'nameTextStyle': {'color': TEXT},
            'axisLabel': {'color': TEXT},
            'axisLine': {'lineStyle': {'color': AXIS}},
            'splitLine': {'show': False},
        },
        'yAxis': [
            y_axis(' / '.join(names_by_axis[a]), 'left' if a is Axis.LEFT else 'right', a is axes[0])
            for a in axes
        ],
        'series': series,
    }