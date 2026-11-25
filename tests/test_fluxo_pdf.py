import json

import pymupdf

from kit_fechamento_rh.processador import (
    processar_kit,
)

CNPJ_TESTE = "12.345.678/0001-90"


def criar_configuracao_teste(
    caminho,
    cnpj_alfa=CNPJ_TESTE,
):
    configuracao = {
        "ALFA": {
            "cnpj": cnpj_alfa,
        },
        "BETA": {
            "cnpj": "11.111.111/0001-11",
        },
        "GAMA": {
            "cnpj": "22.222.222/0001-22",
        },
    }

    caminho.write_text(
        json.dumps(configuracao),
        encoding="utf-8",
    )


def criar_pdf_sintetico(caminho):
    """Cria um PDF fictício com dois funcionários para testes."""

    funcionarios = [
        (
            "100",
            "FUNCIONARIO TESTE UM",
        ),
        (
            "101",
            "FUNCIONARIO TESTE DOIS",
        ),
    ]

    documento = pymupdf.open()

    try:
        for codigo, nome in funcionarios:
            pagina = documento.new_page()

            texto = f"""
{codigo} {nome}
{CNPJ_TESTE}
ALFA TRANSPORTES LTDA
Agosto/2026
MENSAL

{codigo} {nome}
{CNPJ_TESTE}
ALFA TRANSPORTES LTDA
Agosto/2026
MENSAL
"""

            pagina.insert_textbox(
                pymupdf.Rect(
                    50,
                    50,
                    550,
                    750,
                ),
                texto,
                fontsize=10,
            )

        documento.save(
            caminho
        )

    finally:
        documento.close()


def test_fluxo_completo_com_pdf_sintetico(
    tmp_path,
):
    pdf_origem = (
        tmp_path
        / "recibos_teste.pdf"
    )

    pasta_saida = (
        tmp_path
        / "saidas"
    )

    caminho_config = (
        tmp_path
        / "empresas.json"
    )

    criar_pdf_sintetico(
        pdf_origem
    )

    criar_configuracao_teste(
        caminho_config
    )

    resultado = processar_kit(
        pdf_origem,
        "ALFA",
        "Agosto/2026",
        pasta_saida,
        caminho_config,
    )

    assert resultado["status"] == "SUCESSO"

    assert (
        resultado["processamento_concluido"]
        is True
    )

    assert resultado["total_paginas"] == 2

    assert (
        len(
            resultado["geracao"]["arquivos"]
        )
        == 2
    )

    assert (
        resultado["auditoria"]["aprovado"]
        is True
    )

    assert (
        resultado["auditoria"][
            "arquivos_aprovados"
        ]
        == 2
    )

    assert resultado["relatorio"].exists()

    for arquivo in resultado["geracao"]["arquivos"]:
        assert arquivo.exists()
        assert arquivo.name.startswith("RECIBO DE PAGAMENTO - ")
        assert arquivo.name.endswith(" - 08-2026 - ALFA.pdf")
        assert "KIT FECHAMENTO" not in arquivo.name


def test_fluxo_rejeita_empresa_incorreta(
    tmp_path,
):
    pdf_origem = (
        tmp_path
        / "recibos_teste.pdf"
    )

    pasta_saida = (
        tmp_path
        / "saidas"
    )

    caminho_config = (
        tmp_path
        / "empresas.json"
    )

    criar_pdf_sintetico(
        pdf_origem
    )

    criar_configuracao_teste(
        caminho_config
    )

    resultado = processar_kit(
        pdf_origem,
        "BETA",
        "Agosto/2026",
        pasta_saida,
        caminho_config,
    )

    assert resultado["status"] == "FALHA"

    assert (
        resultado["processamento_concluido"]
        is False
    )

    assert resultado["aprovado"] is False

    assert not pasta_saida.exists()


def test_fluxo_rejeita_cnpj_incorreto(
    tmp_path,
):
    pdf_origem = (
        tmp_path
        / "recibos_teste.pdf"
    )

    pasta_saida = (
        tmp_path
        / "saidas"
    )

    caminho_config = (
        tmp_path
        / "empresas.json"
    )

    criar_pdf_sintetico(
        pdf_origem
    )

    criar_configuracao_teste(
        caminho_config,
        "98.765.432/0001-10",
    )

    resultado = processar_kit(
        pdf_origem,
        "ALFA",
        "Agosto/2026",
        pasta_saida,
        caminho_config,
    )

    assert resultado["status"] == "FALHA"
    assert resultado["aprovado"] is False

    assert any(
        "CNPJ diferente do esperado"
        in problema
        for problema
        in resultado["problemas_lote"]
    )

    assert not pasta_saida.exists()


def test_fluxo_com_ressalva_se_relatorio_falhar(
    tmp_path,
    monkeypatch,
):
    pdf_origem = (
        tmp_path
        / "recibos_teste.pdf"
    )

    pasta_saida = (
        tmp_path
        / "saidas"
    )

    caminho_config = (
        tmp_path
        / "empresas.json"
    )

    criar_pdf_sintetico(
        pdf_origem
    )

    criar_configuracao_teste(
        caminho_config
    )

    def falhar_relatorio(_resultado):
        raise OSError(
            "falha simulada no relatório"
        )

    monkeypatch.setattr(
        "kit_fechamento_rh.processador."
        "gerar_relatorio_processamento",
        falhar_relatorio,
    )

    resultado = processar_kit(
        pdf_origem,
        "ALFA",
        "Agosto/2026",
        pasta_saida,
        caminho_config,
    )

    assert (
        resultado["processamento_concluido"]
        is True
    )

    assert (
        resultado["auditoria"]["aprovado"]
        is True
    )

    assert (
        resultado["status"]
        == "SUCESSO_COM_RESSALVA"
    )

    assert "erro_relatorio" in resultado
    assert "relatorio" not in resultado

    assert (
        len(
            resultado["geracao"]["arquivos"]
        )
        == 2
    )

    for arquivo in resultado[
        "geracao"
    ]["arquivos"]:
        assert arquivo.exists()