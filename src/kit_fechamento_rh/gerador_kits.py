import re
from pathlib import Path

import pymupdf

MESES = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


def formatar_competencia(competencia):
    """Transforma Agosto/2026 em dados seguros para nomes de arquivos."""

    mes, ano = competencia.split("/", 1)

    numero_mes = MESES.get(mes.casefold())

    if not numero_mes:
        raise ValueError(
            f"competência inválida: {competencia}"
        )

    return {
        "arquivo": f"{numero_mes}-{ano}",
        "pasta": f"{ano}-{numero_mes}",
    }


def limpar_nome_arquivo(texto):
    """Remove caracteres que o Windows não permite em nomes de arquivos."""

    texto_limpo = re.sub(
        r'[<>:"/\\|?*]',
        "",
        texto,
    )

    return " ".join(texto_limpo.split())


def remover_destinos_planejados(plano_geracao):
    """Remove arquivos existentes previstos no plano de geração."""

    for item in plano_geracao:
        destino = item["destino"]

        if destino.exists():
            try:
                destino.unlink()
            except OSError:
                pass


def remover_arquivos_gerados(geracao):
    """Remove todos os destinos previstos para uma geração."""

    remover_destinos_planejados(
        geracao["plano"]
    )


def gerar_kits(
    resultado,
    pasta_saida="saidas",
):
    """Gera um PDF individual para cada página de um lote aprovado."""

    if not resultado["aprovado"]:
        raise ValueError(
            "o lote não foi aprovado e não pode gerar arquivos"
        )

    empresa = resultado["empresa_encontrada"]
    competencia = resultado["competencia_encontrada"]

    competencia_formatada = formatar_competencia(
        competencia
    )

    destino_base = (
        Path(pasta_saida)
        / empresa
        / competencia_formatada["pasta"]
    )

    plano_geracao = []
    nomes_destino = set()

    # Primeiro planejamos toda a geração.
    for pagina in resultado["paginas"]:
        numero = pagina["numero"]
        dados = pagina["dados"]

        codigo, nome = dados["funcionarios"][0]

        nome = limpar_nome_arquivo(nome)

        nome_arquivo = (
            f"RECIBO DE PAGAMENTO - "
            f"{nome} - "
            f"{competencia_formatada['arquivo']} - "
            f"{empresa}.pdf"
        )

        destino = destino_base / nome_arquivo

        if destino.name in nomes_destino:
            raise ValueError(
                "dois funcionários gerariam o mesmo "
                f"arquivo: {destino.name}"
            )

        nomes_destino.add(destino.name)

        plano_geracao.append(
            {
                "pagina": numero,
                "codigo": codigo,
                "nome": nome,
                "destino": destino,
            }
        )

    # Não permitimos sobrescrever uma geração anterior.
    arquivos_existentes = [
        item["destino"]
        for item in plano_geracao
        if item["destino"].exists()
    ]

    if arquivos_existentes:
        raise FileExistsError(
            "já existem arquivos gerados para este lote"
        )

    destino_base.mkdir(
        parents=True,
        exist_ok=True,
    )

    arquivos_gerados = []
    geracao_concluida = False

    try:
        with pymupdf.open(resultado["caminho"]) as documento:

            for item in plano_geracao:
                numero_pagina = item["pagina"]
                destino = item["destino"]

                novo_pdf = pymupdf.open()

                try:
                    indice = numero_pagina - 1

                    novo_pdf.insert_pdf(
                        documento,
                        from_page=indice,
                        to_page=indice,
                    )

                    novo_pdf.save(destino)

                finally:
                    novo_pdf.close()

                arquivos_gerados.append(destino)

        if len(arquivos_gerados) != resultado.get("total_recibos", resultado["total_paginas"]):
            raise RuntimeError(
                "a quantidade de PDFs gerados não corresponde "
                "à quantidade de recibos distintos"
            )

        geracao_concluida = True

    finally:
        # Se a geração falhar, verificamos TODOS os destinos
        # planejados, inclusive um possível arquivo parcial.
        if not geracao_concluida:
            remover_destinos_planejados(
                plano_geracao
            )

    return {
        "pasta_saida": destino_base,
        "arquivos": arquivos_gerados,
        "plano": plano_geracao,
    }