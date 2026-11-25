"""Integração do fechamento em duas empresas usando somente PDFs sintéticos."""

import json

import pymupdf

from kit_fechamento_rh.processador_fechamento import processar_fechamento


def criar_pdf(caminho, empresa, cnpj, codigo):
    texto = (
        f"{codigo} FUNCIONARIO FICTICIO\n"
        f"{cnpj}\n{empresa} TRANSPORTES LTDA\nAgosto/2026\nMENSAL\n\n"
        f"{codigo} FUNCIONARIO FICTICIO\n"
        f"{cnpj}\n{empresa} TRANSPORTES LTDA\nAgosto/2026\nMENSAL"
    )
    with pymupdf.open() as documento:
        pagina = documento.new_page()
        pagina.insert_textbox(pymupdf.Rect(50, 50, 550, 750), texto, fontsize=10)
        documento.save(caminho)


def criar_entradas(tmp_path):
    cnpjs = {
        "ALFA": "12.345.678/0001-90",
        "BETA": "11.111.111/0001-11",
        "GAMA": "22.222.222/0001-22",
    }
    config = tmp_path / "empresas.json"
    config.write_text(
        json.dumps({empresa: {"cnpj": cnpj} for empresa, cnpj in cnpjs.items()}),
        encoding="utf-8",
    )
    arquivos = {}
    for i, empresa in enumerate(("ALFA", "BETA"), start=100):
        origem = tmp_path / f"{empresa}.pdf"
        criar_pdf(origem, empresa, cnpjs[empresa], str(i))
        arquivos[empresa] = origem
    return config, arquivos


def test_fechamento_real_sintetico_publica_duas_empresas(tmp_path):
    config, arquivos = criar_entradas(tmp_path)
    destino = tmp_path / "entrega"
    resultado = processar_fechamento(arquivos, "Agosto/2026", destino, config)
    assert all(dados["status"] == "SUCESSO" for dados in resultado.values())
    for empresa, dados in resultado.items():
        pasta = destino / empresa
        assert dados["geracao"]["pasta_saida"] == pasta
        assert len(dados["geracao"]["arquivos"]) == 1
        assert dados["geracao"]["arquivos"][0].is_file()
        assert dados["relatorio"].is_file()
        assert str(pasta) in dados["relatorio"].read_text(encoding="utf-8")
        assert dados["auditoria"]["arquivos_aprovados"] == 1
    assert not list(destino.rglob(".kit_*"))


def test_falha_real_do_relatorio_da_BETA_descarta_tudo(tmp_path, monkeypatch):
    import kit_fechamento_rh.processador as processador

    config, arquivos = criar_entradas(tmp_path)
    destino = tmp_path / "entrega"
    relatorio_original = processador.gerar_relatorio_processamento

    def falhar_para_BETA(resultado, pasta_exibida=None):
        if resultado["empresa_encontrada"] == "BETA":
            raise OSError("teste sintético: falha no relatório")
        return relatorio_original(resultado, pasta_exibida=pasta_exibida)

    monkeypatch.setattr(processador, "gerar_relatorio_processamento", falhar_para_BETA)
    resultado = processar_fechamento(arquivos, "Agosto/2026", destino, config)
    assert all(dados["status"] == "FALHA" for dados in resultado.values())
    assert not list(destino.rglob("*.pdf"))
    assert not list(destino.rglob("*.txt"))
    assert not list(destino.rglob(".kit_*"))


def test_reprocessamento_real_sintetico_cria_revisao(tmp_path):
    """PDFs sintéticos: dois processamentos sem substituir a primeira entrega."""
    config, arquivos = criar_entradas(tmp_path)
    destino = tmp_path / "entrega"
    primeira = processar_fechamento(arquivos, "Agosto/2026", destino, config)
    segunda = processar_fechamento(arquivos, "Agosto/2026", destino, config)

    assert all(r["status"] == "SUCESSO" for r in primeira.values())
    assert all(r["status"] == "SUCESSO" for r in segunda.values())
    for empresa in arquivos:
        anterior = destino / empresa
        revisao = destino / empresa / "REVISAO 01"
        assert anterior.is_dir() and revisao.is_dir()
        assert len(list(anterior.glob("*.pdf"))) == 1
        assert len(list(revisao.glob("*.pdf"))) == 1
        assert primeira[empresa]["geracao"]["arquivos"][0].is_file()
        assert segunda[empresa]["geracao"]["arquivos"][0].is_file()
        assert str(revisao) in segunda[empresa]["relatorio"].read_text(encoding="utf-8")
        assert segunda[empresa]["auditoria"]["arquivos_aprovados"] == 1
    assert not list(destino.rglob(".kit_*"))
