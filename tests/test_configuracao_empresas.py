import json

import pytest

from kit_fechamento_rh.configuracao_empresas import (
    carregar_cnpjs,
    obter_caminho_config_padrao,
    obter_cnpj_empresa,
)


def criar_configuracao_teste(caminho):
    configuracao = {
        "ALFA": {
            "cnpj": "00.000.000/0001-00",
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


def test_carregar_cnpjs(tmp_path):
    caminho = tmp_path / "empresas.json"

    criar_configuracao_teste(
        caminho
    )

    cnpjs = carregar_cnpjs(
        caminho
    )

    assert (
        cnpjs["ALFA"]
        == "00.000.000/0001-00"
    )

    assert (
        cnpjs["BETA"]
        == "11.111.111/0001-11"
    )

    assert (
        cnpjs["GAMA"]
        == "22.222.222/0001-22"
    )


def test_obter_cnpj_empresa(tmp_path):
    caminho = tmp_path / "empresas.json"

    criar_configuracao_teste(
        caminho
    )

    cnpj = obter_cnpj_empresa(
        "alfa",
        caminho,
    )

    assert (
        cnpj
        == "00.000.000/0001-00"
    )


def test_configuracao_inexistente_e_rejeitada(
    tmp_path,
):
    caminho = (
        tmp_path
        / "nao_existe.json"
    )

    with pytest.raises(
        FileNotFoundError
    ):
        carregar_cnpjs(
            caminho
        )


def test_cnpj_com_formato_invalido_e_rejeitado(
    tmp_path,
):
    caminho = tmp_path / "empresas.json"

    configuracao = {
        "ALFA": {
            "cnpj": "CNPJ INVALIDO",
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

    with pytest.raises(
        ValueError
    ):
        carregar_cnpjs(
            caminho
        )


def test_caminho_padrao_nao_depende_da_pasta_atual(
    tmp_path,
    monkeypatch,
):
    caminho_original = (
        obter_caminho_config_padrao()
    )

    monkeypatch.chdir(
        tmp_path
    )

    caminho_depois = (
        obter_caminho_config_padrao()
    )

    assert (
        caminho_depois
        == caminho_original
    )

    assert (
        caminho_depois.name
        == "empresas.local.json"
    )


def test_configuracao_principal_precisa_ser_objeto(
    tmp_path,
):
    caminho = tmp_path / "empresas.json"

    caminho.write_text(
        "[]",
        encoding="utf-8",
    )

    with pytest.raises(
        TypeError
    ):
        carregar_cnpjs(
            caminho
        )