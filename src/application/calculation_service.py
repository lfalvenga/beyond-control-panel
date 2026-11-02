from src.application.ports import FormulaCatalog
from src.application.source_service import SourceService
from src.domain.calculation import Calculation, Evaluation, FormulaInfo
from src.domain.errors import CalculationError, ValidationError


class CalculationService:
    def __init__(self, catalog: FormulaCatalog, sources: SourceService) -> None:
        self._catalog = catalog
        self._sources = sources

    def formulas(self) -> dict[str, FormulaInfo]:
        return self._catalog.list()

    def load_errors(self) -> dict[str, str]:
        return self._catalog.load_errors()

    def new(self, code: str) -> Calculation:
        formulas = self._catalog.list()
        if not formulas:
            raise ValidationError('Não há fórmulas instaladas. Veja formulas/_modelo.py.')
        sources = self._sources.list_all(code)
        if not sources:
            raise ValidationError('Importe um CSV na tela Log para montar cálculos.')
        return Calculation.new(next(iter(formulas.values())), sources[-1].id)

    def evaluate(self, code: str, calculation: Calculation) -> Evaluation:
        """Recalcula e atualiza o registro do cálculo (que só vai ao pacote ao salvar)."""
        formula = self._catalog.list().get(calculation.formula_id)
        if formula is None:
            return Evaluation(installed=False)  # mantém o último resultado salvo
        calculation.result = None
        source = next(
            (s for s in self._sources.list_all(code) if s.id == calculation.source_id), None
        )
        if source is None:
            return Evaluation(error='A fonte deste cálculo não existe mais. Escolha outra.')
        try:
            numeric = self._sources.numeric_columns(code, source)
        except (OSError, ValueError):
            numeric = {}
        inputs = {}
        for argument, description in formula.inputs.items():
            column = calculation.inputs.get(argument)
            if not column or column not in numeric:
                return Evaluation(error=f'Escolha a variável de "{description}".')
            inputs[argument] = numeric[column]
        parameters = {
            name: info.default if calculation.parameters.get(name) is None else calculation.parameters[name]
            for name, info in formula.parameters.items()
        }
        try:
            value = self._catalog.run(formula.id, inputs, parameters, source.sample_rate_hz)
        except CalculationError as error:
            return Evaluation(error=str(error))
        calculation.result = value
        calculation.unit = formula.unit
        calculation.formula_name = formula.name
        calculation.version = formula.version
        return Evaluation(value=value)