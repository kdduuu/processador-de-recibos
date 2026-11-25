"""Testes da publicação controlada, sem documentos confidenciais."""

from pathlib import Path

import kit_fechamento_rh.processador_fechamento as fechamento


def criar_analise(aprovado=True, problema=None):
    return {
        "aprovado": aprovado,
        "erro_arquivo": None,
        "erro_configuracao": None,
        "pendencias": [],
        "problemas_lote": [] if problema is None else [problema],
    }


def preparar_simulacao(monkeypatch, status_por_empresa=None, falha_publicacao=False):
    """Substitui PDFs por documentos fictícios criados na pasta temporária."""
    status_por_empresa = status_por_empresa or {}
    chamadas = []

    def analisar_pdf(caminho_pdf, empresa, competencia, caminho_config):
        return criar_analise()

    def processar_kit(
        caminho_pdf, empresa, competencia, pasta_saida, caminho_config,
        pasta_relatorio=None, analise_prevalidada=None,
    ):
        chamadas.append(empresa)
        status = status_por_empresa.get(empresa, "SUCESSO")
        pasta = Path(pasta_saida) / empresa / "2026-08"
        pasta.mkdir(parents=True, exist_ok=True)
        pdf = pasta / f"RECIBO DE PAGAMENTO - FICTICIO - 08-2026 - {empresa}.pdf"
        pdf.write_bytes(b"PDF SINTETICO")
        relatorio = pasta / f"RELATORIO PROCESSAMENTO - {empresa} - 2026-08.txt"
        relatorio.write_text(f"Pasta de saída: {pasta_relatorio}", encoding="utf-8")
        return {
            "status": status,
            "processamento_concluido": status != "FALHA",
            "geracao": {
                "pasta_saida": pasta,
                "arquivos": [pdf],
                "plano": [{"pagina": 1, "destino": pdf}],
            },
            "relatorio": relatorio,
        }

    monkeypatch.setattr(fechamento, "analisar_pdf", analisar_pdf)
    monkeypatch.setattr(fechamento, "processar_kit", processar_kit)

    if falha_publicacao:
        original = Path.rename

        def rename_controlado(self, destino):
            destino = Path(destino)
            # Simula erro ao publicar a segunda empresa (a primeira já foi publicada).
            if destino.name == "BETA":
                raise OSError("falha simulada de publicação")
            return original(self, destino)

        monkeypatch.setattr(Path, "rename", rename_controlado)

    return chamadas


def pastas_provisorias(destino):
    return list(destino.rglob(".kit_*"))


def test_uma_empresa_e_parcial_e_publica_em_pasta_final(tmp_path, monkeypatch, capsys):
    chamadas = preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    resultado = fechamento.processar_fechamento(
        {"ALFA": "alfa.pdf"}, "Agosto/2026", destino
    )
    pasta = destino / "ALFA"
    assert chamadas == ["ALFA"]
    assert resultado["ALFA"]["status"] == "SUCESSO"
    assert len(resultado["ALFA"]["geracao"]["arquivos"]) == 1
    assert resultado["ALFA"]["geracao"]["arquivos"][0].exists()
    assert resultado["ALFA"]["relatorio"].exists()
    assert str(pasta) in resultado["ALFA"]["relatorio"].read_text(encoding="utf-8")
    assert not pastas_provisorias(destino)
    assert "Escopo: PROCESSAMENTO PARCIAL" in capsys.readouterr().out


def test_tres_empresas_formam_fechamento_completo(tmp_path, monkeypatch, capsys):
    chamadas = preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf", "GAMA": "z.pdf"},
        "Agosto/2026", destino,
    )
    assert chamadas == ["ALFA", "BETA", "GAMA"]
    assert all(r["status"] == "SUCESSO" for r in resultado.values())
    assert all((destino / empresa).is_dir() for empresa in resultado)
    assert not pastas_provisorias(destino)
    saida = capsys.readouterr().out
    assert "Escopo: FECHAMENTO COMPLETO" in saida
    assert "Empresas concluídas: 3/3" in saida


def test_prevalidacao_reprovada_impede_toda_geracao(tmp_path, monkeypatch, capsys):
    chamadas = []

    def analisar_pdf(caminho_pdf, empresa, competencia, caminho_config):
        return criar_analise(empresa != "BETA", "empresa divergente" if empresa == "BETA" else None)

    def processar_kit(*args, **kwargs):
        chamadas.append("chamado")
        raise AssertionError("não deveria processar")

    monkeypatch.setattr(fechamento, "analisar_pdf", analisar_pdf)
    monkeypatch.setattr(fechamento, "processar_kit", processar_kit)
    destino = tmp_path / "saidas"
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert chamadas == []
    assert resultado["ALFA"]["aprovado"]
    assert not resultado["BETA"]["aprovado"]
    assert not destino.exists()
    assert "BETA: REPROVADA" in capsys.readouterr().out


def test_empresa_nao_suportada_bloqueada(tmp_path, monkeypatch):
    def erro(*args, **kwargs):
        raise AssertionError("não deveria validar")

    monkeypatch.setattr(fechamento, "analisar_pdf", erro)
    assert fechamento.processar_fechamento(
        {"EMPRESA_X": "x.pdf"}, "Agosto/2026", tmp_path
    ) == {}


def test_nenhuma_empresa_nao_inicia(tmp_path):
    assert fechamento.processar_fechamento({}, "Agosto/2026", tmp_path) == {}


def test_erro_na_segunda_empresa_descarta_preparacao(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch, {"BETA": "FALHA"})
    destino = tmp_path / "saidas"
    resultados = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "FALHA" for r in resultados.values())
    assert all("geracao" not in r for r in resultados.values())
    assert not list(destino.rglob("*.pdf"))
    assert not pastas_provisorias(destino)
    assert not (destino / "ALFA").exists()


def test_ressalva_em_relatorio_nao_publica_pdfs(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch, {"BETA": "SUCESSO_COM_RESSALVA"})
    destino = tmp_path / "saidas"
    resultados = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "FALHA" for r in resultados.values())
    assert not list(destino.rglob("*.pdf"))
    assert not pastas_provisorias(destino)


def test_destino_preexistente_e_preservado_e_cria_revisao(tmp_path, monkeypatch):
    chamadas = preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    pasta_existente = destino / "BETA" / "2026-08"
    pasta_existente.mkdir(parents=True)
    arquivo_antigo = pasta_existente / "documento-anterior.pdf"
    arquivo_antigo.write_bytes(b"ORIGINAL INALTERADO")

    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert chamadas == ["ALFA", "BETA"]
    assert all(r["status"] == "SUCESSO" for r in resultado.values())
    assert arquivo_antigo.read_bytes() == b"ORIGINAL INALTERADO"
    assert not list((destino / "ALFA").glob("*.pdf"))
    for empresa in ("ALFA", "BETA"):
        revisao = destino / empresa / "REVISAO 01"
        assert revisao.is_dir()
        assert resultado[empresa]["geracao"]["pasta_saida"] == revisao
        assert resultado[empresa]["geracao"]["arquivos"][0].is_file()
        assert str(revisao) in resultado[empresa]["relatorio"].read_text(encoding="utf-8")


def test_reprocessamentos_geram_revisoes_sequenciais(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    arquivos = {"ALFA": "g.pdf"}
    primeira = fechamento.processar_fechamento(arquivos, "Agosto/2026", destino)
    segunda = fechamento.processar_fechamento(arquivos, "Agosto/2026", destino)
    terceira = fechamento.processar_fechamento(arquivos, "Agosto/2026", destino)
    nomes = [
        execucao["ALFA"]["geracao"]["pasta_saida"].name
        for execucao in (primeira, segunda, terceira)
    ]
    assert nomes == ["ALFA", "REVISAO 01", "REVISAO 02"]
    assert all(r["ALFA"]["status"] == "SUCESSO" for r in (primeira, segunda, terceira))
    assert len(list((destino / "ALFA").rglob("*.pdf"))) == 3
    assert not pastas_provisorias(destino)


def test_revisao_comum_ignora_versoes_reservadas(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    (destino / "ALFA").mkdir(parents=True)
    (destino / "BETA" / "REVISAO 01").mkdir(parents=True)
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "SUCESSO" for r in resultado.values())
    assert all(
        r["geracao"]["pasta_saida"].name == "REVISAO 02"
        for r in resultado.values()
    )
    assert (destino / "ALFA").is_dir()
    assert (destino / "BETA" / "REVISAO 01").is_dir()


def test_numeracao_nao_reutiliza_revisoes_com_lacuna(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    (destino / "ALFA" / "REVISAO 03").mkdir(parents=True)
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf"}, "Agosto/2026", destino
    )
    assert resultado["ALFA"]["status"] == "SUCESSO"
    assert resultado["ALFA"]["geracao"]["pasta_saida"].name == "REVISAO 04"


def test_falha_em_revisao_preserva_entrega_antiga(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch, {"BETA": "FALHA"})
    destino = tmp_path / "saidas"
    antigo = destino / "ALFA" / "antigo.pdf"
    antigo.parent.mkdir(parents=True)
    antigo.write_bytes(b"ANTIGO")
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "FALHA" for r in resultado.values())
    assert antigo.read_bytes() == b"ANTIGO"
    assert not (destino / "ALFA" / "REVISAO 01").exists()
    assert not (destino / "BETA" / "REVISAO 01").exists()
    assert not pastas_provisorias(destino)


def test_falha_ao_publicar_segunda_empresa_reverte_primeira(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch, falha_publicacao=True)
    destino = tmp_path / "saidas"
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "FALHA" for r in resultado.values())
    assert not (destino / "ALFA").exists()
    assert not (destino / "BETA" / "2026-08").exists()
    assert not list(destino.rglob("*.pdf"))
    assert not pastas_provisorias(destino)


def test_preparacao_usa_mkdir_normal_sem_acl_privada(tmp_path, monkeypatch):
    """Regressão: não solicitar o modo 0o700 do TemporaryDirectory."""
    preparar_simulacao(monkeypatch)
    criacoes = []
    mkdir_original = Path.mkdir

    def registrar_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        if self.name.startswith(".kit_"):
            criacoes.append((self.parent, mode, exist_ok))
        return mkdir_original(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", registrar_mkdir)
    destino = tmp_path / "saidas"
    resultado = fechamento.processar_fechamento(
        {"BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert resultado["BETA"]["status"] == "SUCESSO"
    assert criacoes == [(destino.resolve(), 0o777, False)]
    assert not list(destino.rglob(".kit_*"))


def test_revisao_prepara_no_pai_da_entrega(tmp_path, monkeypatch):
    """Cada revisão recebe a política da pasta da própria empresa."""
    preparar_simulacao(monkeypatch)
    destino = tmp_path / "saidas"
    (destino / "ALFA").mkdir(parents=True)
    criacoes = []
    mkdir_original = Path.mkdir

    def registrar_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        if self.name.startswith(".kit_"):
            criacoes.append((self.parent, mode, exist_ok))
        return mkdir_original(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", registrar_mkdir)
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "SUCESSO" for r in resultado.values())
    assert criacoes == [
        (destino.resolve() / "ALFA", 0o777, False),
        (destino.resolve() / "BETA", 0o777, False),
    ]
    assert all(r["geracao"]["pasta_saida"].name == "REVISAO 01" for r in resultado.values())
    assert not list(destino.rglob(".kit_*"))


def test_falha_em_revisao_limpa_preparacoes_de_todos_os_pais(tmp_path, monkeypatch):
    preparar_simulacao(monkeypatch, {"BETA": "FALHA"})
    destino = tmp_path / "saidas"
    (destino / "ALFA").mkdir(parents=True)
    anterior = destino / "ALFA" / "anterior.pdf"
    anterior.write_bytes(b"PRESERVAR")
    resultado = fechamento.processar_fechamento(
        {"ALFA": "g.pdf", "BETA": "t.pdf"}, "Agosto/2026", destino
    )
    assert all(r["status"] == "FALHA" for r in resultado.values())
    assert anterior.read_bytes() == b"PRESERVAR"
    assert not (destino / "BETA").exists()
    assert not list(destino.rglob(".kit_*"))
    assert not list(destino.rglob("REVISAO *"))


def test_colisao_de_preparacao_nao_apaga_pasta_alheia(tmp_path, monkeypatch):
    import pytest
    from uuid import UUID

    identificador = UUID(int=1)
    monkeypatch.setattr(fechamento, "uuid4", lambda: identificador)
    existente = tmp_path / f".kit_{identificador.hex[:12]}"
    existente.mkdir()
    arquivo = existente / "anterior.txt"
    arquivo.write_text("preservar", encoding="utf-8")
    with pytest.raises(FileExistsError):
        with fechamento._pasta_preparacao(tmp_path):
            raise AssertionError("A pasta existente não pode ser reutilizada")
    assert arquivo.read_text(encoding="utf-8") == "preservar"


def test_nome_curto_da_preparacao_para_windows(tmp_path):
    """Evita que o identificador temporário estoure o caminho de revisões."""
    from pathlib import PureWindowsPath

    # Comprimento equivalente ao caminho Windows que revelou o problema,
    # sem reproduzir dados ou nomes reais de usuários.
    pai_windows = PureWindowsPath("C:/") / ("x" * 115) / "ALFA"
    with fechamento._pasta_preparacao(tmp_path) as pasta:
        assert pasta.name.startswith(".kit_")
        assert len(pasta.name) <= 17
        caminho = pai_windows / pasta.name / "ALFA" / "2026-08" / (
            "RECIBO DE PAGAMENTO - FUNCIONARIO FICTICIO - 08-2026 - ALFA.pdf"
        )
        assert len(str(caminho)) < 260
        assert pasta.is_dir()
    assert not pasta.exists()
