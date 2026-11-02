import math

import pytest

import formulas

ALL = formulas.carregar_formulas()


def test_all_formula_files_load():
    assert formulas.erros_de_carga() == {}


@pytest.mark.parametrize('formula_id', sorted(ALL))
def test_formula_example(formula_id):
    formula = ALL[formula_id]
    if formula.exemplo is None:
        pytest.skip('sem exemplo')
    example = formula.exemplo
    value = formulas.executar(
        formula, example['entradas'], example.get('parametros'), example.get('taxa_hz')
    )
    assert math.isclose(value, example['esperado'], rel_tol=1e-6, abs_tol=1e-9)


@pytest.mark.parametrize('formula_id', [i for i, f in ALL.items() if f.usa_tempo and f.exemplo])
def test_time_formulas_refuse_without_sample_rate(formula_id):
    formula = ALL[formula_id]
    with pytest.raises(formulas.ErroDeFormula):
        formulas.executar(formula, formula.exemplo['entradas'], formula.exemplo.get('parametros'), None)