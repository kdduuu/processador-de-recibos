from datetime import datetime


def gerar_relatorio_processamento(resultado, pasta_exibida=None):
    """Gera um relatório textual de uma execução concluída."""

    momento = datetime.now().astimezone()

    geracao = resultado["geracao"]
    auditoria = resultado["auditoria"]

    pasta_saida = geracao["pasta_saida"]
    # Em lotes, o PDF e o relatório são preparados em pasta temporária.
    # No relatório exibimos o destino definitivo, não essa pasta.
    pasta_informada = pasta_exibida if pasta_exibida is not None else pasta_saida

    empresa = resultado["empresa_encontrada"]
    competencia = resultado["competencia_encontrada"]

    # Exemplo: 20261007-164530
    identificador = momento.strftime("%Y%m%d-%H%M%S")

    # A pasta já utiliza o formato AAAA-MM.
    competencia_pasta = pasta_saida.name

    nome_relatorio = (
        f"RELATORIO PROCESSAMENTO - "
        f"{empresa} - "
        f"{competencia_pasta} - "
        f"{identificador}.txt"
    )

    caminho_relatorio = pasta_saida / nome_relatorio

    paginas_ok = (
        resultado["total_paginas"]
        - len(resultado["pendencias"])
    )

    linhas = [
        "RELATÓRIO DE PROCESSAMENTO - PROCESSADOR DE RECIBOS",
        "=" * 50,
        "",
        f"Data e hora: {momento.strftime('%d/%m/%Y %H:%M:%S')}",
        f"Arquivo de origem: {resultado['caminho'].name}",
        "",
        "--- IDENTIFICAÇÃO ---",
        f"Empresa esperada: {resultado['empresa_esperada']}",
        f"Empresa encontrada: {empresa}",
        f"Competência esperada: {resultado['competencia_esperada']}",
        f"Competência encontrada: {competencia}",
        "",
        "--- VALIDAÇÃO DO PDF ---",
        f"Páginas analisadas: {resultado['total_paginas']}",
        f"Recibos distintos: {resultado.get('total_recibos', resultado['total_paginas'])}",
        f"Cópias idênticas ignoradas: {len(resultado.get('paginas_ignoradas', []))}",
        *[
            f"  Página {item['pagina']} igual à página {item['igual_a']}"
            for item in resultado.get("paginas_ignoradas", [])
        ],
        f"Páginas aprovadas: {paginas_ok}",
        f"Pendências: {len(resultado['pendencias'])}",
        "Lote: APROVADO",
        "",
        "--- GERAÇÃO ---",
        f"PDFs gerados: {len(geracao['arquivos'])}",
        f"Pasta de saída: {pasta_informada}",
        "",
        "--- AUDITORIA DA SAÍDA ---",
        f"Arquivos auditados: {auditoria['arquivos_auditados']}",
        f"Arquivos aprovados: {auditoria['arquivos_aprovados']}",
        f"Problemas encontrados: {len(auditoria['problemas'])}",
        "Auditoria: APROVADA",
        "",
        "--- RESULTADO FINAL ---",
        "PROCESSAMENTO CONCLUÍDO COM SUCESSO",
        "",
    ]

    conteudo = "\n".join(linhas)

    # Primeiro escreve em um arquivo temporário.
    # Depois substitui pelo relatório definitivo.
    caminho_temporario = caminho_relatorio.with_suffix(".tmp")

    try:
        caminho_temporario.write_text(
            conteudo,
            encoding="utf-8",
        )

        caminho_temporario.replace(caminho_relatorio)

    finally:
        if caminho_temporario.exists():
            caminho_temporario.unlink()

    return caminho_relatorio