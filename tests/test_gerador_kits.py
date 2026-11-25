import pytest

from kit_fechamento_rh.gerador_kits import (
    formatar_competencia,
    limpar_nome_arquivo,
    remover_arquivos_gerados,
)


def test_formatar_competencia():
    resultado = formatar_competencia(
        "Agosto/2026"
    )

    assert resultado == {
        "arquivo": "08-2026",
        "pasta": "2026-08",
    }


def test_formatar_competencia_ignora_maiusculas_minusculas():
    resultado = formatar_competencia(
        "AGOSTO/2026"
    )

    assert resultado == {
        "arquivo": "08-2026",
        "pasta": "2026-08",
    }


def test_formatar_competencia_rejeita_mes_invalido():
    with pytest.raises(
        ValueError
    ):
        formatar_competencia(
            "MesInvalido/2026"
        )


def test_limpar_nome_arquivo():
    resultado = limpar_nome_arquivo(
        "FUNCIONARIO: TESTE / RH"
    )

    assert (
        resultado
        == "FUNCIONARIO TESTE RH"
    )


def test_limpar_nome_remove_espacos_duplicados():
    resultado = limpar_nome_arquivo(
        "FUNCIONARIO     TESTE"
    )

    assert (
        resultado
        == "FUNCIONARIO TESTE"
    )


def test_limpeza_remove_todos_os_destinos_planejados(
    tmp_path,
):
    arquivo_concluido = (
        tmp_path
        / "concluido.pdf"
    )

    arquivo_parcial = (
        tmp_path
        / "parcial.pdf"
    )

    arquivo_concluido.write_bytes(
        b"arquivo concluido"
    )

    arquivo_parcial.write_bytes(
        b"arquivo parcial"
    )

    geracao = {
        "arquivos": [
            arquivo_concluido,
        ],
        "plano": [
            {
                "destino": arquivo_concluido,
            },
            {
                "destino": arquivo_parcial,
            },
        ],
    }

    remover_arquivos_gerados(
        geracao
    )

    assert not arquivo_concluido.exists()
    assert not arquivo_parcial.exists()