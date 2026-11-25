"""Testes do resumo da interface, sem abrir janela e sem dados reais."""

from kit_fechamento_rh.interface import resumir_execucao


def test_resumo_sucesso_de_duas_empresas():
    resultados = {
        "ALFA": {"status": "SUCESSO", "geracao": {"arquivos": ["1.pdf", "2.pdf"]}},
        "BETA": {"status": "SUCESSO", "geracao": {"arquivos": ["3.pdf"]}},
    }
    situacao, texto, quantidade = resumir_execucao(resultados, "destino_teste")

    assert situacao == "sucesso"
    assert quantidade == 3
    assert "ALFA: SUCESSO" in texto
    assert "BETA: SUCESSO" in texto
    assert "Total de recibos gerados: 3" in texto


def test_resumo_prevalidacao_reprovada_nao_acusa_geracao():
    resultados = {
        "ALFA": {"aprovado": True, "problemas_lote": []},
        "BETA": {
            "aprovado": False,
            "problemas_lote": ["empresa diferente da esperada"],
        },
    }
    situacao, texto, quantidade = resumir_execucao(resultados, "destino_teste")

    assert situacao == "falha"
    assert quantidade == 0
    assert "ALFA: VALIDADA" in texto
    assert "BETA: REPROVADA" in texto
    assert "empresa diferente da esperada" in texto
    assert "Falha na geração" not in texto


def test_resumo_geracao_interrompida_orienta_verificar_destino():
    resultados = {"ALFA": {"status": "FALHA", "aprovado": True}}
    situacao, texto, quantidade = resumir_execucao(resultados, "destino_teste")

    assert situacao == "falha"
    assert quantidade == 0
    assert "Verifique se já existem recibos" in texto


def test_resumo_ressalva_no_relatorio():
    resultados = {
        "GAMA": {
            "status": "SUCESSO_COM_RESSALVA",
            "geracao": {"arquivos": ["a.pdf", "b.pdf"]},
        }
    }
    situacao, texto, quantidade = resumir_execucao(resultados, "destino_teste")

    assert situacao == "ressalva"
    assert quantidade == 2
    assert "COM RESSALVA" in texto
    assert "falha no relatório" in texto


def test_resumo_execucao_descartada_nao_exibe_pdfs_temporarios():
    resultados = {
        "ALFA": {
            "status": "FALHA",
            "erro_lote": "BETA falhou. Nenhum arquivo foi publicado.",
        },
        "BETA": {
            "status": "FALHA",
            "erro_lote": "BETA falhou. Nenhum arquivo foi publicado.",
        },
    }
    situacao, texto, quantidade = resumir_execucao(resultados, "destino_teste")
    assert situacao == "falha"
    assert quantidade == 0
    assert "Nenhum arquivo foi publicado" in texto
    assert "Total de recibos gerados: 0" in texto


def test_resumo_mostra_destino_exato_da_revisao(tmp_path):
    from kit_fechamento_rh.interface import resumir_execucao

    pasta_revisao = tmp_path / "ALFA" / "REVISAO 01"
    resultados = {
        "ALFA": {
            "status": "SUCESSO",
            "geracao": {
                "arquivos": [pasta_revisao / "recibo.pdf"],
                "pasta_saida": pasta_revisao,
            },
        },
    }
    situacao, texto, quantidade = resumir_execucao(resultados, str(tmp_path))
    assert situacao == "sucesso"
    assert quantidade == 1
    assert str(pasta_revisao) in texto
