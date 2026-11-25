from kit_fechamento_rh.validador_lote import (
    validar_lote,
)

CNPJ_TESTE = "12.345.678/0001-90"


def criar_pagina(
    codigo="100",
    nome="FUNCIONARIO TESTE",
    empresa="ALFA",
    cnpj=CNPJ_TESTE,
    competencia="Agosto/2026",
    tipo="MENSAL",
):
    return {
        "empresas": [
            empresa,
        ],
        "cnpjs": [
            cnpj,
        ],
        "competencias": [
            competencia,
        ],
        "tipos": [
            tipo,
        ],
        "funcionarios": [
            (
                codigo,
                nome,
            ),
        ],
    }


def test_lote_consistente_e_aprovado():
    paginas = [
        criar_pagina(
            codigo="100",
            nome="FUNCIONARIO UM",
        ),
        criar_pagina(
            codigo="101",
            nome="FUNCIONARIO DOIS",
        ),
    ]

    problemas = validar_lote(
        paginas,
        "ALFA",
        "Agosto/2026",
    )

    assert problemas == []


def test_lote_rejeita_empresa_diferente_da_esperada():
    paginas = [
        criar_pagina(),
    ]

    problemas = validar_lote(
        paginas,
        "BETA",
        "Agosto/2026",
    )

    assert any(
        "empresa diferente da esperada"
        in problema
        for problema in problemas
    )


def test_lote_rejeita_competencia_diferente():
    paginas = [
        criar_pagina(),
    ]

    problemas = validar_lote(
        paginas,
        "ALFA",
        "Setembro/2026",
    )

    assert any(
        "competência diferente da esperada"
        in problema
        for problema in problemas
    )


def test_lote_rejeita_funcionario_repetido():
    paginas = [
        criar_pagina(),
        criar_pagina(),
    ]

    problemas = validar_lote(
        paginas,
        "ALFA",
        "Agosto/2026",
    )

    assert any(
        "funcionário repetido"
        in problema
        for problema in problemas
    )


def test_lote_aprova_cnpj_esperado():
    paginas = [
        criar_pagina(),
    ]

    problemas = validar_lote(
        paginas,
        "ALFA",
        "Agosto/2026",
        CNPJ_TESTE,
    )

    assert problemas == []


def test_lote_rejeita_cnpj_diferente_do_esperado():
    paginas = [
        criar_pagina(),
    ]

    problemas = validar_lote(
        paginas,
        "ALFA",
        "Agosto/2026",
        "98.765.432/0001-10",
    )

    assert any(
        "CNPJ diferente do esperado"
        in problema
        for problema in problemas
    )