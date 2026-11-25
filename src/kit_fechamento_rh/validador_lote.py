from collections import Counter

from kit_fechamento_rh.configuracao_empresas import (
    empresas_disponiveis,
)


def validar_lote(
    paginas,
    empresa_esperada,
    competencia_esperada,
    cnpj_esperado=None,
    empresas=None,
):
    """Valida se todas as páginas pertencem ao mesmo lote esperado."""

    problemas = []

    if not paginas:
        problemas.append(
            "o lote não possui páginas para validação"
        )
        return problemas

    empresa_esperada = (
        empresa_esperada.strip().upper()
    )

    competencia_esperada = (
        competencia_esperada.strip()
    )

    if empresa_esperada not in (empresas if empresas is not None else empresas_disponiveis()):
        problemas.append(
            f"empresa não suportada: {empresa_esperada}"
        )

    empresas = []
    cnpjs = []
    competencias = []
    tipos = []
    funcionarios = []

    for pagina in paginas:
        empresas.extend(
            pagina["empresas"]
        )

        cnpjs.extend(
            pagina["cnpjs"]
        )

        competencias.extend(
            pagina["competencias"]
        )

        tipos.extend(
            pagina["tipos"]
        )

        funcionarios.extend(
            pagina["funcionarios"]
        )

    empresas_unicas = set(
        empresas
    )

    cnpjs_unicos = set(
        cnpjs
    )

    competencias_unicas = set(
        competencias
    )

    tipos_unicos = set(
        tipos
    )

    if len(empresas_unicas) != 1:
        problemas.append(
            "o lote deve possuir exatamente uma empresa"
        )

    if len(cnpjs_unicos) != 1:
        problemas.append(
            "o lote deve possuir exatamente um CNPJ"
        )

    if len(competencias_unicas) != 1:
        problemas.append(
            "o lote deve possuir exatamente uma competência"
        )

    if tipos_unicos != {"MENSAL"}:
        problemas.append(
            "o lote deve conter somente recibos MENSAL"
        )

    contagem_funcionarios = Counter(
        funcionarios
    )

    funcionarios_repetidos = [
        funcionario
        for funcionario, quantidade
        in contagem_funcionarios.items()
        if quantidade > 1
    ]

    for codigo, nome in funcionarios_repetidos:
        problemas.append(
            "funcionário repetido no lote: "
            f"{codigo} - {nome}"
        )

    if len(empresas_unicas) == 1:
        empresa_encontrada = next(
            iter(empresas_unicas)
        )

        if empresa_encontrada != empresa_esperada:
            problemas.append(
                "empresa diferente da esperada: "
                f"esperado {empresa_esperada}, "
                f"encontrado {empresa_encontrada}"
            )

    if len(competencias_unicas) == 1:
        competencia_encontrada = next(
            iter(competencias_unicas)
        )

        if (
            competencia_encontrada.casefold()
            != competencia_esperada.casefold()
        ):
            problemas.append(
                "competência diferente da esperada: "
                f"esperado {competencia_esperada}, "
                f"encontrado {competencia_encontrada}"
            )

    if (
        cnpj_esperado is not None
        and len(cnpjs_unicos) == 1
    ):
        cnpj_esperado = (
            cnpj_esperado.strip()
        )

        cnpj_encontrado = next(
            iter(cnpjs_unicos)
        )

        if cnpj_encontrado != cnpj_esperado:
            problemas.append(
                "CNPJ diferente do esperado para a empresa"
            )

    return problemas