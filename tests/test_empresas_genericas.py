import json
import pytest
import pymupdf
from kit_fechamento_rh.configuracao_empresas import carregar_cnpjs
from kit_fechamento_rh.processador_fechamento import processar_fechamento
from kit_fechamento_rh.leitor_pdf import analisar_pdf


def test_empresa_configuravel_fluxo_completo(tmp_path):
    config = tmp_path / "empresas.json"
    config.write_text(json.dumps({"Nova Empresa": {"cnpj": "00.000.000/0001-00"}}), encoding="utf-8")
    pdf = tmp_path / "recibo.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        texto = "100 FUNCIONARIO TESTE\nNOVA EMPRESA LTDA\n00.000.000/0001-00\nSetembro/2026\nMENSAL"
        page.insert_text((50, 50), texto)
        page.insert_text((50, 300), texto)
        doc.save(pdf)
    assert carregar_cnpjs(config) == {"NOVA EMPRESA": "00.000.000/0001-00"}
    assert analisar_pdf(pdf, "NOVA EMPRESA", "Setembro/2026", config)["aprovado"]
    assert not analisar_pdf(pdf, "OUTRA EMPRESA", "Setembro/2026", config)["aprovado"]
    resultado = processar_fechamento({"NOVA EMPRESA": pdf}, "Setembro/2026", tmp_path / "saida", config)
    assert resultado["NOVA EMPRESA"]["status"] == "SUCESSO"


def test_nome_de_empresa_nao_pode_ser_caminho(tmp_path):
    config = tmp_path / "empresas.json"
    config.write_text(json.dumps({"../fora": {"cnpj": "00.000.000/0001-00"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        carregar_cnpjs(config)
