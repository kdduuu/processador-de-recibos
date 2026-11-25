from kit_fechamento_rh.analisador_pagina import analisar_texto_pagina
from kit_fechamento_rh.leitor_pdf import validar_pagina

TEXTO_RECIBO_MENSAL = """
100 FUNCIONARIO TESTE
12.345.678/0001-90
ALFA TRANSPORTES LTDA
Agosto/2026
MENSAL

100 FUNCIONARIO TESTE
12.345.678/0001-90
ALFA TRANSPORTES LTDA
Agosto/2026
MENSAL
"""


def test_analisador_identifica_dados_da_pagina():
    dados = analisar_texto_pagina(TEXTO_RECIBO_MENSAL)

    assert dados["empresas"] == ["ALFA"]
    assert dados["cnpjs"] == ["12.345.678/0001-90"]
    assert dados["competencias"] == ["Agosto/2026"]
    assert dados["tipos"] == ["MENSAL"]
    assert dados["funcionarios"] == [
        ("100", "FUNCIONARIO TESTE")
    ]
    assert dados["qtd_ocorrencias_funcionario"] == 2


def test_pagina_mensal_valida_nao_possui_problemas():
    dados = analisar_texto_pagina(TEXTO_RECIBO_MENSAL)

    problemas = validar_pagina(dados)

    assert problemas == []


def test_pagina_adto_e_reprovada():
    texto_adto = TEXTO_RECIBO_MENSAL.replace(
        "MENSAL",
        "ADTO",
    )

    dados = analisar_texto_pagina(texto_adto)

    problemas = validar_pagina(dados)

    assert "tipo de recibo inválido: ADTO" in problemas