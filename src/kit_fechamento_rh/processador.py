from kit_fechamento_rh.auditor_saida import auditar_geracao
from kit_fechamento_rh.gerador_kits import (
    gerar_kits,
    remover_arquivos_gerados,
)
from kit_fechamento_rh.leitor_pdf import ler_pdf
from kit_fechamento_rh.relatorio_processamento import (
    gerar_relatorio_processamento,
)


def processar_kit(
    caminho_pdf,
    empresa,
    competencia,
    pasta_saida="saidas",
    caminho_config=None,
    pasta_relatorio=None,
    analise_prevalidada=None,
):
    """Executa validação, geração, auditoria e relatório do Kit Fechamento."""

    # O fechamento coletivo já examinou cada PDF na pré-validação.
    # Reaproveitamos o resultado para não ler todas as páginas duas vezes,
    # especialmente quando os PDFs são acessados pela rede.
    resultado = (
        analise_prevalidada
        if analise_prevalidada is not None
        else ler_pdf(caminho_pdf, empresa, competencia, caminho_config)
    )

    resultado["status"] = "FALHA"
    resultado["processamento_concluido"] = False

    if not resultado["aprovado"]:
        print("\nNenhum arquivo foi gerado.")
        return resultado

    try:
        geracao = gerar_kits(
            resultado,
            pasta_saida,
        )

    except FileExistsError as erro:
        print("\nGERAÇÃO INTERROMPIDA")
        print(f"- {erro}")
        return resultado

    except (
        OSError,
        ValueError,
        RuntimeError,
    ) as erro:
        print("\nERRO DURANTE A GERAÇÃO")
        print(f"- {erro}")
        return resultado

    resultado["geracao"] = geracao

    print("\n--- GERAÇÃO DOS KITS ---")
    print(
        f"PDFs gerados: "
        f"{len(geracao['arquivos'])}"
    )
    print(
        f"Pasta de saída: "
        f"{geracao['pasta_saida']}"
    )

    print("\n--- AUDITORIA DA SAÍDA ---")

    auditoria = auditar_geracao(
        resultado,
        geracao,
    )

    resultado["auditoria"] = auditoria

    print(
        f"Arquivos auditados: "
        f"{auditoria['arquivos_auditados']}"
    )
    print(
        f"Arquivos aprovados: "
        f"{auditoria['arquivos_aprovados']}"
    )

    if not auditoria["aprovado"]:
        print("AUDITORIA: REPROVADA")

        for problema in auditoria["problemas"]:
            print(f"- {problema}")

        print(
            "\nOs arquivos desta tentativa serão removidos "
            "para evitar uma entrega inconsistente."
        )

        remover_arquivos_gerados(
            geracao
        )

        return resultado

    print("AUDITORIA: APROVADA")

    resultado["processamento_concluido"] = True

    print("\n--- RELATÓRIO DE PROCESSAMENTO ---")

    try:
        # Em processamento coletivo, o relatório aponta para o destino
        # definitivo, embora ainda seja criado na área de preparação.
        if pasta_relatorio is None:
            caminho_relatorio = gerar_relatorio_processamento(resultado)
        else:
            caminho_relatorio = gerar_relatorio_processamento(
                resultado, pasta_exibida=pasta_relatorio
            )

    except OSError as erro:
        resultado["erro_relatorio"] = str(
            erro
        )
        resultado["status"] = (
            "SUCESSO_COM_RESSALVA"
        )

        print("RELATÓRIO: NÃO GERADO")
        print(f"- {erro}")

        print(
            "\nPROCESSAMENTO CONCLUÍDO COM RESSALVA: "
            "os recibos foram gerados e auditados, "
            "mas o relatório não pôde ser salvo."
        )

        return resultado

    resultado["relatorio"] = (
        caminho_relatorio
    )
    resultado["status"] = "SUCESSO"

    print("RELATÓRIO: GERADO")
    print(
        f"Arquivo: {caminho_relatorio}"
    )

    print(
        "\nPROCESSAMENTO CONCLUÍDO COM SUCESSO."
    )

    return resultado