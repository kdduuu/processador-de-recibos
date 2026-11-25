import hashlib

import pymupdf


def gerar_hash_visual(pagina):
    """Gera uma assinatura do conteúdo visual renderizado da página."""

    imagem = pagina.get_pixmap(alpha=False)

    return hashlib.sha256(imagem.samples).hexdigest()


def auditar_geracao(resultado, geracao):
    """Confere se os PDFs gerados correspondem às páginas originais."""

    problemas = []
    arquivos_aprovados = 0

    plano_geracao = geracao["plano"]
    arquivos_gerados = geracao["arquivos"]

    # Primeira conferência: quantidade planejada e quantidade criada.
    if len(arquivos_gerados) != resultado.get("total_recibos", resultado["total_paginas"]):
        problemas.append(
            "quantidade de arquivos gerados diferente "
            "da quantidade de recibos distintos"
        )

    try:
        with pymupdf.open(resultado["caminho"]) as documento_original:

            for item in plano_geracao:
                numero_pagina = item["pagina"]
                destino = item["destino"]

                if not destino.exists():
                    problemas.append(
                        f"página {numero_pagina}: arquivo não encontrado"
                    )
                    continue

                try:
                    with pymupdf.open(destino) as documento_gerado:

                        # Cada recibo individual deve possuir somente 1 página.
                        if len(documento_gerado) != 1:
                            problemas.append(
                                f"página {numero_pagina}: "
                                "PDF gerado não possui exatamente 1 página"
                            )
                            continue

                        pagina_original = documento_original[
                            numero_pagina - 1
                        ]
                        pagina_gerada = documento_gerado[0]

                        texto_original = (
                            pagina_original.get_text().strip()
                        )
                        texto_gerado = (
                            pagina_gerada.get_text().strip()
                        )

                        if texto_original != texto_gerado:
                            problemas.append(
                                f"página {numero_pagina}: "
                                "texto diferente do original"
                            )
                            continue

                        # Confere também as dimensões físicas da página.
                        if pagina_original.rect != pagina_gerada.rect:
                            problemas.append(
                                f"página {numero_pagina}: "
                                "dimensões diferentes do original"
                            )
                            continue

                        # Por último, compara a renderização visual.
                        hash_original = gerar_hash_visual(
                            pagina_original
                        )
                        hash_gerado = gerar_hash_visual(
                            pagina_gerada
                        )

                        if hash_original != hash_gerado:
                            problemas.append(
                                f"página {numero_pagina}: "
                                "renderização visual diferente do original"
                            )
                            continue

                        arquivos_aprovados += 1

                except (OSError, RuntimeError) as erro:
                    problemas.append(
                        f"página {numero_pagina}: "
                        f"não foi possível auditar o PDF: {erro}"
                    )

    except (OSError, RuntimeError) as erro:
        problemas.append(
            f"não foi possível auditar o PDF original: {erro}"
        )

    return {
        "aprovado": not problemas,
        "arquivos_auditados": len(plano_geracao),
        "arquivos_aprovados": arquivos_aprovados,
        "problemas": problemas,
    }