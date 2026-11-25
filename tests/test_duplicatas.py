"""Regressões com recibos inteiramente fictícios e sem dados do RH."""

import json

import pymupdf

from kit_fechamento_rh.leitor_pdf import analisar_pdf
from kit_fechamento_rh.processador_fechamento import processar_fechamento


CNPJ_FICTICIO = "12.345.678/0001-90"


def criar_entrada(tmp_path, com_diferenca=False):
    caminho = tmp_path / "recibos_ficticios.pdf"
    texto_base = (
        "ALFA TRANSPORTES LTDA\n"
        f"{CNPJ_FICTICIO}\nAgosto/2026\nMENSAL\n"
        "123 FUNCIONARIO FICTICIO\nVALOR DE TESTE 100\n"
        "123 FUNCIONARIO FICTICIO\n"
    )
    with pymupdf.open() as doc:
        for indice in range(2):
            pagina = doc.new_page()
            texto = texto_base
            if com_diferenca and indice == 1:
                texto = texto.replace("VALOR DE TESTE 100", "VALOR DE TESTE 200")
            pagina.insert_textbox(pymupdf.Rect(30, 30, 540, 720), texto, fontsize=11)
        doc.save(caminho)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"ALFA": {"cnpj": CNPJ_FICTICIO}, "BETA": {"cnpj": "11.111.111/0001-11"}, "GAMA": {"cnpj": "22.222.222/0001-22"}}), encoding="utf8")
    return caminho, config


def test_copia_identica_e_ignorada_com_rastreabilidade(tmp_path):
    caminho, config = criar_entrada(tmp_path)
    analise = analisar_pdf(caminho, "ALFA", "Agosto/2026", config)
    assert analise["aprovado"]
    assert analise["total_paginas"] == 2
    assert analise["total_recibos"] == 1
    assert analise["paginas_ignoradas"] == [{"pagina": 2, "igual_a": 1}]

    saida = tmp_path / "saida_agosto"
    resultado = processar_fechamento(
        {"ALFA": caminho}, "Agosto/2026", saida, config
    )["ALFA"]
    assert resultado["status"] == "SUCESSO"
    assert len(resultado["geracao"]["arquivos"]) == 1
    assert resultado["geracao"]["arquivos"][0].parent == saida / "ALFA"
    assert resultado["auditoria"]["arquivos_aprovados"] == 1
    relatorio = resultado["relatorio"].read_text(encoding="utf8")
    assert "Cópias idênticas ignoradas: 1" in relatorio
    assert "Página 2 igual à página 1" in relatorio


def test_copia_com_valor_divergente_continua_bloqueada(tmp_path):
    caminho, config = criar_entrada(tmp_path, com_diferenca=True)
    analise = analisar_pdf(caminho, "ALFA", "Agosto/2026", config)
    assert not analise["aprovado"]
    assert analise["total_recibos"] == 2
    assert analise["paginas_ignoradas"] == []
    assert any("funcionário repetido" in problema for problema in analise["problemas_lote"])
    destino = tmp_path / "saida_agosto"
    resultado = processar_fechamento({"ALFA": caminho}, "Agosto/2026", destino, config)
    assert not resultado["ALFA"]["aprovado"]
    assert not destino.exists()
