import re
from dataclasses import dataclass, field

from rocket_station.domain.enums import OperationKind, Review
from rocket_station.domain.errors import ValidationError

CODE_PATTERN = re.compile(r'[A-Za-z0-9_-]+')

DEFAULT_PARAMETERS = [
    ('Pressão Atmosférica', 'Pa'),
    ('Latitude', '°'),
    ('Longitude', '°'),
    ('Altitude', 'm'),
    ('Inclinação', '°'),
    ('Azimute', '°'),
]


@dataclass
class Parameter:
    name: str
    unit: str = ''
    value: float | None = None
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
    classification: str = ''
    notes: str = ''
    parameters: list[Parameter] = field(default_factory=list)

    @classmethod
    def blank(cls) -> 'Operation':
        return cls(parameters=[Parameter(name=n, unit=u) for n, u in DEFAULT_PARAMETERS])

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