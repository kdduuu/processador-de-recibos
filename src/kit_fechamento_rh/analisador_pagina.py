import re

from kit_fechamento_rh.configuracao_empresas import empresas_disponiveis


def padrao_empresa(empresas):
    nomes = "|".join(re.escape(n) for n in sorted(empresas, key=len, reverse=True))
    return re.compile(r"^\s*(" + nomes + r")(?=\s|$|[-.,]).*$", re.MULTILINE | re.IGNORECASE)

# Procura CNPJ no formato 00.000.000/0000-00.
PADRAO_CNPJ = re.compile(
    r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"
)

# Procura competências como Agosto/2026, Setembro/2026 etc.
PADRAO_COMPETENCIA = re.compile(
    r"\b(?:"
    r"Janeiro|Fevereiro|Março|Abril|Maio|Junho|"
    r"Julho|Agosto|Setembro|Outubro|Novembro|Dezembro"
    r")/\d{4}\b",
    re.IGNORECASE,
)

# Reconhece os tipos que podem aparecer nos recibos.
PADRAO_TIPO = re.compile(
    r"^\s*(MENSAL|ADTO)\s*$",
    re.MULTILINE,
)

# Procura linhas como:
# 223 NOME COMPLETO DO FUNCIONARIO
PADRAO_FUNCIONARIO = re.compile(
    r"^(\d+)\s+([A-ZÀ-Ú][A-ZÀ-Ú '\-]+)\s*$",
    re.MULTILINE,
)


def valores_unicos(encontrados):
    """Remove valores repetidos preservando a ordem."""
    return list(dict.fromkeys(encontrados))


def analisar_texto_pagina(texto, empresas=None):
    """Extrai os principais dados identificados em uma página."""

    empresas_encontradas = padrao_empresa(empresas if empresas is not None else empresas_disponiveis()).findall(texto)
    cnpjs_encontrados = PADRAO_CNPJ.findall(texto)
    competencias_encontradas = PADRAO_COMPETENCIA.findall(texto)
    tipos_encontrados = PADRAO_TIPO.findall(texto)
    funcionarios_encontrados = PADRAO_FUNCIONARIO.findall(texto)

    return {
        "empresas": [
            empresa.upper()
            for empresa in valores_unicos(empresas_encontradas)
        ],
        "cnpjs": valores_unicos(cnpjs_encontrados),
        "competencias": valores_unicos(competencias_encontradas),
        "tipos": valores_unicos(tipos_encontrados),
        "funcionarios": valores_unicos(funcionarios_encontrados),
        "qtd_ocorrencias_funcionario": len(funcionarios_encontrados),
    }