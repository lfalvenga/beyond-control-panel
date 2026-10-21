import math

import formulas


def main() -> int:
    todas = formulas.carregar_formulas()
    problemas = 0

    for arquivo, motivo in formulas.erros_de_carga().items():
        print(f'ERRO    {arquivo}: {motivo}')
        problemas += 1

    for f in todas.values():
        ex = f.exemplo
        if ex is None:
            print(f'AVISO   {f.id}: sem `exemplo` (não dá para conferir o resultado)')
            continue

        try:
            obtido = formulas.executar(f, ex['entradas'], ex.get('parametros'), ex.get('taxa_hz'))
        except formulas.ErroDeFormula as erro:
            print(f'FALHOU  {f.id}: {erro}')
            problemas += 1
            continue
        if math.isclose(obtido, ex['esperado'], rel_tol=1e-6, abs_tol=1e-9):
            print(f'OK      {f.id}: {obtido:.6g}')
        else:
            print(f'FALHOU  {f.id}: obtido {obtido:.6g}, esperado {ex["esperado"]:.6g}')
            problemas += 1

        if f.usa_tempo:  # regra geral: sem taxa de amostragem, a fórmula tem que recusar
            try:
                formulas.executar(f, ex['entradas'], ex.get('parametros'), None)
            except formulas.ErroDeFormula:
                print(f'OK      {f.id}: recusa corretamente quando não há taxa')
            else:
                print(f'FALHOU  {f.id}: deveria recusar quando não há taxa')
                problemas += 1


if __name__ == '__main__':
    raise SystemExit(main())