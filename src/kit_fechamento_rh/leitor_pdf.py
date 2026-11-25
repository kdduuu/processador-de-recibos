from pathlib import Path

import pymupdf

from kit_fechamento_rh.analisador_pagina import (
    analisar_texto_pagina,
)
from kit_fechamento_rh.configuracao_empresas import (
    obter_cnpj_empresa,
    carregar_cnpjs,
)
from kit_fechamento_rh.validador_lote import (
    validar_lote,
)


def validar_pagina(dados):
    """Valida os dados extraídos de uma página."""

    problemas = []

    if len(dados["empresas"]) != 1:
        problemas.append(
            "a página deve possuir exatamente uma empresa"
        )

    if len(dados["cnpjs"]) != 1:
        problemas.append(
            "a página deve possuir exatamente um CNPJ"
        )

    if len(dados["competencias"]) != 1:
        problemas.append(
            "a página deve possuir exatamente uma competência"
        )

    if len(dados["tipos"]) != 1:
        problemas.append(
            "a página deve possuir exatamente um tipo de recibo"
        )

    elif dados["tipos"][0] != "MENSAL":
        problemas.append(
            f"tipo de recibo inválido: {dados['tipos'][0]}"
        )

    if len(dados["funcionarios"]) != 1:
        problemas.append(
            "a página deve possuir exatamente um funcionário"
        )

    if dados["qtd_ocorrencias_funcionario"] != 2:
        problemas.append(
            "o funcionário deve aparecer duas vezes na página"
        )

    return problemas


def obter_cnpj_configurado(
    empresa,
    caminho_config=None,
):
    """Obtém o CNPJ esperado usando a configuração local."""

    if caminho_config is None:
        return obter_cnpj_empresa(
            empresa
        )

    return obter_cnpj_empresa(
        empresa,
        caminho_config,
    )


def analisar_pdf(
    caminho_pdf,
    empresa_esperada,
    competencia_esperada,
    caminho_config=None,
):
    """Analisa e valida um PDF sem gerar arquivos de saída."""

    caminho = Path(caminho_pdf)

    resultado = {
        "caminho": caminho,
        "empresa_esperada": empresa_esperada,
        "competencia_esperada": competencia_esperada,
        "empresa_encontrada": None,
        "competencia_encontrada": None,
        "total_paginas": 0,
        "total_recibos": 0,
        "paginas_ignoradas": [],
        "paginas": [],
        "pendencias": [],
        "problemas_lote": [],
        "aprovado": False,
        "erro_arquivo": None,
        "erro_configuracao": None,
    }

    if not caminho.exists():
        resultado["erro_arquivo"] = (
            f"arquivo não encontrado: {caminho}"
        )
        return resultado

    if caminho.suffix.lower() != ".pdf":
        resultado["erro_arquivo"] = (
            "o arquivo informado não é um PDF"
        )
        return resultado

    try:
        empresas_configuradas = carregar_cnpjs(caminho_config)
        cnpj_esperado = obter_cnpj_configurado(empresa_esperada, caminho_config)

    except (
        FileNotFoundError,
        TypeError,
        ValueError,
    ) as erro:
        resultado["erro_configuracao"] = str(
            erro
        )
        return resultado

    try:
        with pymupdf.open(caminho) as documento:
            resultado["total_paginas"] = len(
                documento
            )

            primeiras_paginas = {}
            for indice, pagina in enumerate(
                documento
            ):
                numero_pagina = indice + 1

                texto = pagina.get_text()

                dados = analisar_texto_pagina(
                    texto, empresas_configuradas
                )

                problemas = validar_pagina(
                    dados
                )

                # Duas vias do MESMO funcionário dentro da mesma página
                # são esperadas. Uma SEGUNDA página idêntica é redundante.
                # Conferimos texto E imagem para não descartar recibos
                # com valores diferentes, mesmo que o nome seja igual.
                duplicata_identica = False
                if not problemas and len(dados["funcionarios"]) == 1:
                    funcionario = dados["funcionarios"][0]
                    primeira = primeiras_paginas.get(funcionario)
                    if primeira is None:
                        primeiras_paginas[funcionario] = (indice, texto)
                    else:
                        indice_original, texto_original = primeira
                        if (texto == texto_original
                                and pagina.rect == documento[indice_original].rect
                                and pagina.get_pixmap(alpha=False).samples
                                == documento[indice_original].get_pixmap(alpha=False).samples):
                            resultado["paginas_ignoradas"].append({
                                "pagina": numero_pagina,
                                "igual_a": indice_original + 1,
                            })
                            duplicata_identica = True

                if not duplicata_identica:
                    resultado["paginas"].append(
                        {
                            "numero": numero_pagina,
                            "dados": dados,
                            "problemas": problemas,
                        }
                    )

                if problemas:
                    resultado["pendencias"].append(
                        (
                            numero_pagina,
                            problemas,
                        )
                    )

    except (OSError, RuntimeError) as erro:
        resultado["erro_arquivo"] = str(
            erro
        )
        return resultado

    resultado["total_recibos"] = len(resultado["paginas"])

    if resultado["pendencias"]:
        return resultado

    paginas_analisadas = [
        pagina["dados"]
        for pagina in resultado["paginas"]
    ]

    problemas_lote = validar_lote(
        paginas_analisadas,
        empresa_esperada,
        competencia_esperada,
        cnpj_esperado,
        empresas_configuradas,
    )

    resultado["problemas_lote"] = (
        problemas_lote
    )

    empresas_encontradas = {
        empresa
        for pagina in paginas_analisadas
        for empresa in pagina["empresas"]
    }

    competencias_encontradas = {
        competencia
        for pagina in paginas_analisadas
        for competencia in pagina["competencias"]
    }

    if len(empresas_encontradas) == 1:
        resultado["empresa_encontrada"] = next(
            iter(empresas_encontradas)
        )

    if len(competencias_encontradas) == 1:
        resultado["competencia_encontrada"] = next(
            iter(competencias_encontradas)
        )

    resultado["aprovado"] = not problemas_lote

    return resultado


def exibir_resultado(resultado):
    """Exibe no terminal o resultado da análise."""

    caminho = resultado["caminho"]

    print(f"Arquivo: {caminho.name}")

    if resultado["erro_arquivo"]:
        print("\nERRO DE ARQUIVO")
        print(f"- {resultado['erro_arquivo']}")
        return

    if resultado["erro_configuracao"]:
        print("\nERRO DE CONFIGURAÇÃO")
        print(
            f"- {resultado['erro_configuracao']}"
        )
        return

    print(
        f"Quantidade de páginas: "
        f"{resultado['total_paginas']}"
    )
    print(f"Recibos distintos: {resultado['total_recibos']}")
    for duplicata in resultado.get("paginas_ignoradas", []):
        print(
            f"- Cópia idêntica ignorada: página {duplicata['pagina']} "
            f"(igual à página {duplicata['igual_a']})"
        )
    print()

    paginas_ok = 0

    for pagina in resultado["paginas"]:
        numero = pagina["numero"]
        problemas = pagina["problemas"]

        if problemas:
            print(
                f"Página {numero}: "
                "PENDÊNCIA"
            )

            for problema in problemas:
                print(f"- {problema}")

        else:
            paginas_ok += 1
            print(
                f"Página {numero}: OK"
            )

    print("\n--- RESUMO DAS PÁGINAS ---")
    print(
        f"Páginas analisadas: "
        f"{resultado['total_paginas']}"
    )
    print(
        f"Páginas OK: {paginas_ok}"
    )
    print(
        f"Pendências: "
        f"{len(resultado['pendencias'])}"
    )

    print("\n--- DADOS INFORMADOS ---")
    print(
        f"Empresa esperada: "
        f"{resultado['empresa_esperada']}"
    )
    print(
        f"Competência esperada: "
        f"{resultado['competencia_esperada']}"
    )

    print("\n--- DADOS ENCONTRADOS ---")
    print(
        f"Empresa encontrada: "
        f"{resultado['empresa_encontrada']}"
    )
    print(
        f"Competência encontrada: "
        f"{resultado['competencia_encontrada']}"
    )

    if resultado["pendencias"]:
        print("\nLOTE: NÃO VALIDADO")
        return

    print("\n--- VALIDAÇÃO DO LOTE ---")

    if resultado["problemas_lote"]:
        print("LOTE: REPROVADO")

        for problema in resultado[
            "problemas_lote"
        ]:
            print(f"- {problema}")

    else:
        print("LOTE: APROVADO")


def ler_pdf(
    caminho_pdf,
    empresa_esperada,
    competencia_esperada,
    caminho_config=None,
):
    """Analisa o PDF, exibe o resultado e retorna os dados."""

    resultado = analisar_pdf(
        caminho_pdf,
        empresa_esperada,
        competencia_esperada,
        caminho_config,
    )

    exibir_resultado(
        resultado
    )

    return resultado