import re
from dataclasses import dataclass, field

from src.domain.enums import OperationKind, Review
from src.domain.errors import ValidationError

CODE_PATTERN = re.compile(r'[A-Za-z0-9_-]+')

def _single(name: str, unit: str) -> tuple:
    return (name, [(name, unit)])

DEFAULT_PARAMETERS = [
    _single('Pressão Atmosférica', 'Pa'),
    _single('Latitude', '°'),
    _single('Longitude', '°'),
    _single('Altitude', 'm'),
    _single('Inclinação', '°'),
    _single('Azimute', '°'),
    ('Motor', [
        ('Massa da Tubeira', 'g'),
        ('Massa da Tampa', 'g'),
        ('Massa da Câmara', 'g'),
        ('Massa do Motor Vazio', 'g'),
    ]),
    *[
        (f'{n}° Grão', [('Massa do Grão', 'g'), ('Comprimento do Grão', 'mm')])
        for n in range(1, 8)
    ],
    ('Motor Carregado', [('Massa do Motor', 'g'), ('Ajuste de Massa (Inibidor)', 'g')]),
    _single('Umidade do Ar', '%'),
    _single('Temperatura do Ar', '°C'),
    _single('Velocidade do Vento', 'm/s'),
    ('Termopares', [(f'Posição Termopar {n} (Tampa)', 'mm') for n in (1, 2, 3)]),
]


@dataclass
class Measure:
    name: str
    unit: str = ''
    value: float | None = None


@dataclass
class Parameter:
    name: str
    measures: list[Measure] = field(default_factory=list)
    responsible: str = ''
    time: str = ''
    review: Review = Review.PENDING


@dataclass
class Operation:
    id: str = ''
    code: str = ''
    kind: OperationKind = OperationKind.STATIC_TEST
    uses_activation: bool = True
    project: str = ''
    date: str = ''
    location: str = ''
    team: str = ''
    created_by: str = ''
    created_at: str = ''
    updated_at: str = ''
    deleted_at: str = ''
    classification: str = ''
    notes: str = ''
    parameters: list[Parameter] = field(default_factory=list)

    @classmethod
    def blank(cls) -> 'Operation':
        return cls(parameters=[
            Parameter(name=n, measures=[Measure(m, u) for m, u in ms])
            for n, ms in DEFAULT_PARAMETERS
        ])

    def normalize_and_validate(self) -> None:
        self.code = self.code.strip()
        if not self.code:
            raise ValidationError('Informe o Código do Teste.')
        if not CODE_PATTERN.fullmatch(self.code):
            raise ValidationError('O código só pode ter letras, números, - e _.')
        self.created_by = self.created_by.strip()
        if not self.created_by:
            raise ValidationError('Informe quem está criando o teste.')
        if self.kind == OperationKind.STATIC_TEST:
            self.uses_activation = True  # teste estático sempre usa o circuito

    def review_counts(self) -> dict[Review, int]:
        counts = {review: 0 for review in Review}
        for parameter in self.parameters:
            counts[parameter.review] += 1
        return counts