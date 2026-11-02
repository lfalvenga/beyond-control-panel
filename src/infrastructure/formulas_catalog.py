import formulas  # a pasta de fórmulas da equipe, na raiz do projeto

from src.domain.calculation import FormulaInfo, ParameterInfo
from src.domain.errors import CalculationError


class FormulasCatalog:
    """Adaptador: traduz o plugin formulas/ para o domínio."""

    def list(self) -> dict[str, FormulaInfo]:
        return {
            fid: FormulaInfo(
                id=f.id,
                name=f.nome,
                description=f.descricao,
                inputs=dict(f.entradas),
                parameters={
                    name: ParameterInfo(default, description)
                    for name, (default, description) in f.parametros.items()
                },
                unit=f.unidade,
                uses_time=f.usa_tempo,
                version=f.versao,
            )
            for fid, f in formulas.carregar_formulas().items()
        }

    def load_errors(self) -> dict[str, str]:
        return formulas.erros_de_carga()

    def run(self, formula_id, inputs, parameters, sample_rate_hz) -> float:
        formula = formulas.carregar_formulas().get(formula_id)
        if formula is None:
            raise CalculationError(f'A fórmula "{formula_id}" não está instalada.')
        try:
            return formulas.executar(formula, inputs, parameters, sample_rate_hz)
        except formulas.ErroDeFormula as error:
            raise CalculationError(str(error)) from error