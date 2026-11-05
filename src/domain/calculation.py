import uuid
from dataclasses import dataclass, field


@dataclass
class ParameterInfo:
    default: float
    description: str


@dataclass
class FormulaInfo:
    id: str
    name: str
    description: str
    inputs: dict[str, str]  # argumento -> descrição
    parameters: dict[str, ParameterInfo]
    unit: str
    uses_time: bool
    version: str


@dataclass
class Calculation:
    id: str
    name: str
    formula_id: str
    source_id: str
    inputs: dict[str, str] = field(default_factory=dict)  # argumento -> coluna original
    parameters: dict[str, float] = field(default_factory=dict)  # só os que o usuário mudou
    links: dict[str, str] = field(default_factory=dict)  # parâmetro -> id do cálculo de origem
    notes: str = ''
    # Registro do último cálculo: o pacote continua mostrando o resultado
    # mesmo em um computador sem a fórmula instalada.
    result: float | None = None
    unit: str = ''
    version: str = ''
    formula_name: str = ''
    formula_text: str = ''  # não é mais preenchido; mantido por compatibilidade

    @classmethod
    def new(cls, formula: FormulaInfo, source_id: str) -> 'Calculation':
        return cls(
            id=uuid.uuid4().hex[:8],
            name=formula.name,
            formula_id=formula.id,
            source_id=source_id,
            unit=formula.unit,
            version=formula.version,
            formula_name=formula.name,
        )


@dataclass
class Evaluation:
    value: float | None = None
    error: str = ''
    installed: bool = True