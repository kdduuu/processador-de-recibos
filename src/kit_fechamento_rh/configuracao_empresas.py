import json
import re
import sys
from pathlib import Path

EMPRESAS_EXEMPLO = {
    "ALFA",
    "BETA",
    "GAMA",
}

PADRAO_CNPJ = re.compile(
    r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
)


def obter_diretorio_aplicacao():
    """Retorna a pasta-base da aplicação."""

    # Quando futuramente o programa estiver empacotado como .exe,
    # usamos a própria pasta do executável.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    # Durante o desenvolvimento:
    #
    # projeto/
    # ├── config/
    # └── src/
    #     └── kit_fechamento_rh/
    #         └── configuracao_empresas.py
    #
    # parents[2] representa a raiz do projeto.
    return Path(__file__).resolve().parents[2]


def obter_caminho_config_padrao():
    """Retorna o caminho da configuração local das empresas."""

    return (
        obter_diretorio_aplicacao()
        / "config"
        / "empresas.local.json"
    )


def carregar_cnpjs(
    caminho_config=None,
):
    """Carrega e valida os CNPJs configurados localmente."""

    if caminho_config is None:
        caminho = obter_caminho_config_padrao()
    else:
        caminho = Path(caminho_config)

    if not caminho.exists():
        raise FileNotFoundError(
            f"arquivo de configuração não encontrado: {caminho}"
        )

    try:
        conteudo = caminho.read_text(
            encoding="utf-8"
        )

        configuracao = json.loads(
            conteudo
        )

    except json.JSONDecodeError as erro:
        raise ValueError(
            "o arquivo de configuração possui JSON inválido"
        ) from erro

    if not isinstance(configuracao, dict):
        raise TypeError(
            "a configuração principal deve ser um objeto JSON"
        )

    cnpjs = {}

    if not configuracao:
        raise ValueError("configure pelo menos uma empresa")

    for nome, dados_empresa in configuracao.items():
        empresa = nome.strip().upper()
        if (not re.fullmatch(r"[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9 ._-]*", empresa)
                or empresa.endswith(".") or empresa in cnpjs
                or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", empresa)):
            raise ValueError(f"nome de empresa inválido ou duplicado: {nome}")

        if not isinstance(dados_empresa, dict):
            raise TypeError(
                f"configuração inválida para a empresa {empresa}"
            )

        cnpj = dados_empresa.get(
            "cnpj"
        )

        if not isinstance(cnpj, str):
            raise TypeError(
                f"CNPJ deve ser texto para a empresa {empresa}"
            )

        cnpj = cnpj.strip()

        if not PADRAO_CNPJ.fullmatch(
            cnpj
        ):
            raise ValueError(
                f"CNPJ inválido na configuração da empresa {empresa}"
            )

        cnpjs[empresa] = cnpj

    return cnpjs


def obter_cnpj_empresa(
    empresa,
    caminho_config=None,
):
    """Retorna o CNPJ esperado para uma empresa."""

    empresa = empresa.strip().upper()

    cnpjs = carregar_cnpjs(
        caminho_config
    )

    if empresa not in cnpjs:
        raise ValueError(f"empresa não suportada: {empresa}")
    return cnpjs[empresa]

def empresas_disponiveis(caminho_config=None):
    """Lista empresas locais; sem configuração, exibe apenas os exemplos."""
    try:
        return tuple(carregar_cnpjs(caminho_config))
    except FileNotFoundError:
        if caminho_config is not None:
            raise
        return tuple(sorted(EMPRESAS_EXEMPLO))
