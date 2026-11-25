"""Processamento coletivo com preparação e publicação controlada.

Os PDFs são gerados e auditados primeiro em uma área temporária.
Apenas quando todas as empresas selecionadas terminam com SUCESSO
as pastas são movidas para o destino final. Em falhas tratáveis,
as pastas publicadas nesta tentativa são devolvidas e descartadas.
"""

from contextlib import ExitStack, contextmanager
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from kit_fechamento_rh.configuracao_empresas import empresas_disponiveis
from kit_fechamento_rh.gerador_kits import formatar_competencia
from kit_fechamento_rh.leitor_pdf import analisar_pdf
from kit_fechamento_rh.processador import processar_kit


@contextmanager
def _pasta_preparacao(pai):
    """Cria uma pasta exclusiva com a herança normal do destino.

    TemporaryDirectory usa modo 0o700, que no Python 3.13/Windows
    restringe a ACL ao criador e administradores. Ao mover uma pasta
    dessa árvore, a restrição pode permanecer. mkdir normal deixa o
    servidor aplicar sua política de acesso, sem alterar ACLs.
    """
    pai = Path(pai)
    pai_criado = False
    if not pai.is_dir():
        try:
            pai.mkdir(exist_ok=False)
            pai_criado = True
        except FileExistsError:
            if not pai.is_dir():
                raise

    try:
        # Nome curto para evitar estourar o limite de caminhos do Windows,
        # principalmente em revisões (que têm um nível adicional).
        # 48 bits aleatórios + mkdir exclusivo: colisões falham sem reutilizar.
        pasta = pai / f".kit_{uuid4().hex[:12]}"
        # Criação exclusiva: nunca reutilizar/apagar uma pasta de outro lote.
        pasta.mkdir(exist_ok=False)
        try:
            yield pasta
        finally:
            rmtree(pasta)
    finally:
        if pai_criado:
            # Se uma revisão falhou, retirar apenas o pai vazio criado
            # nesta tentativa. Nunca remover conteúdo de outra execução.
            try:
                pai.rmdir()
            except OSError:
                pass


def obter_problemas_prevalidacao(resultado):
    """Reúne erros de entrada antes de qualquer geração."""
    problemas = []

    if resultado["erro_arquivo"]:
        problemas.append(resultado["erro_arquivo"])

    if resultado["erro_configuracao"]:
        problemas.append(resultado["erro_configuracao"])

    for numero, problemas_pagina in resultado["pendencias"]:
        problemas.append(f"página {numero}: {', '.join(problemas_pagina)}")

    problemas.extend(resultado["problemas_lote"])
    return problemas


def _marcar_execucao_falha(resultados, mensagem):
    """Impede que PDFs de preparação sejam anunciados como entregues."""
    for resultado in resultados.values():
        resultado["status"] = "FALHA"
        resultado["processamento_concluido"] = False
        resultado["erro_lote"] = mensagem
        # Os caminhos temporários deixarão de existir ao final da função.
        resultado.pop("geracao", None)
        resultado.pop("relatorio", None)
    print(f"\nRESULTADO DA EXECUÇÃO: FALHA\n- {mensagem}")
    return resultados


def _atualizar_caminhos(resultado, pasta_final):
    """Aponta os resultados para os arquivos que foram publicados."""
    geracao = resultado["geracao"]
    geracao["pasta_saida"] = pasta_final
    geracao["arquivos"] = [
        pasta_final / arquivo.name for arquivo in geracao["arquivos"]
    ]
    for item in geracao["plano"]:
        item["destino"] = pasta_final / item["destino"].name
    resultado["relatorio"] = pasta_final / resultado["relatorio"].name


def _publicar_pastas(resultados, destinos):
    """Move pastas completas e desfaz os movimentos se uma delas falhar.

    Cada pasta de competência/revisão deve estar livre. Isso impede
    misturar recibos antigos com novos e elimina sobrescritas.
    """
    movimentos = []
    try:
        for empresa, resultado in resultados.items():
            origem = resultado["geracao"]["pasta_saida"]
            destino = destinos[empresa]

            # Reconfere antes de publicar, pois alguém pode ter criado
            # essa pasta depois da pré-verificação.
            if destino.exists():
                raise FileExistsError(
                    f"a pasta de {empresa} já existe: {destino}"
                )
            destino.parent.mkdir(parents=True, exist_ok=True)
            origem.rename(destino)
            movimentos.append((origem, destino))
    except OSError as erro:
        falhas_reversao = []
        for origem, destino in reversed(movimentos):
            try:
                destino.rename(origem)
            except OSError:
                # Não apagamos à força uma pasta que não conseguimos
                # devolver. Relatamos o caminho para correção manual.
                falhas_reversao.append(str(destino))

        if falhas_reversao:
            raise RuntimeError(
                "A publicação falhou e algumas pastas não puderam ser "
                "revertidas. NÃO UTILIZE A ENTREGA. Verifique: "
                + "; ".join(falhas_reversao)
            ) from erro
        raise OSError(f"publicação cancelada e revertida: {erro}") from erro

    for empresa, resultado in resultados.items():
        _atualizar_caminhos(resultado, destinos[empresa])


def _escolher_destinos(pasta_final, empresas, nome_competencia):
    """Entrega direta em EMPRESA; reprocessamentos em EMPRESA/REVISAO NN.

    A competência está no nome dos PDFs e do relatório; cabe ao RH
    selecionar uma pasta de destino específica para aquela competência.
    Mantemos o mesmo número de revisão para todas as empresas da execução.
    Se existir qualquer pasta da empresa, não misturamos ou sobrescrevemos.
    """
    empresas = tuple(empresas)
    maior_revisao = 0
    ha_entrega_anterior = False
    prefixo_revisao = "REVISAO "

    for empresa in empresas:
        pasta_empresa = pasta_final / empresa
        if not pasta_empresa.exists():
            continue
        # Se há uma pasta já existente, preservamo-la sempre, até se for
        # uma entrega antiga no formato EMPRESA/AAAA-MM.
        ha_entrega_anterior = True
        if not pasta_empresa.is_dir():
            raise OSError(f"o destino de {empresa} não é uma pasta: {pasta_empresa}")
        for caminho in pasta_empresa.iterdir():
            if caminho.name.startswith(prefixo_revisao):
                sufixo = caminho.name[len(prefixo_revisao):]
                if sufixo.isdecimal():
                    maior_revisao = max(maior_revisao, int(sufixo))

    if not ha_entrega_anterior:
        return {empresa: pasta_final / empresa for empresa in empresas}

    numero = maior_revisao + 1
    while True:
        nome_revisao = f"REVISAO {numero:02d}"
        destinos = {
            empresa: pasta_final / empresa / nome_revisao
            for empresa in empresas
        }
        if all(not destino.exists() for destino in destinos.values()):
            return destinos
        numero += 1


def processar_fechamento(
    arquivos,
    competencia,
    pasta_saida="saidas",
    caminho_config=None,
):
    """Valida, prepara e publica somente um fechamento integralmente aprovado."""
    if not arquivos:
        print("Nenhuma empresa foi informada para processamento.")
        return {}

    try:
        empresas_suportadas = set(empresas_disponiveis(caminho_config))
    except (FileNotFoundError, TypeError, ValueError) as erro:
        print(f"Configuração inválida: {erro}")
        return {}
    empresas_recebidas = set(arquivos)
    empresas_inesperadas = empresas_recebidas - empresas_suportadas
    if empresas_inesperadas:
        print("PROCESSAMENTO NÃO INICIADO\nEmpresas não suportadas:")
        for empresa in sorted(empresas_inesperadas):
            print(f"- {empresa}")
        return {}

    escopo = (
        "FECHAMENTO COMPLETO"
        if empresas_recebidas == empresas_suportadas
        else "PROCESSAMENTO PARCIAL"
    )
    print("=" * 60)
    print("PROCESSAMENTO DO PROCESSADOR DE RECIBOS")
    print("=" * 60)
    print(f"Escopo: {escopo}")
    print("\n" + "=" * 60)
    print("PRÉ-VALIDAÇÃO DOS LOTES")
    print("=" * 60)

    analises = {}
    prevalidacao_aprovada = True
    for empresa, caminho_pdf in arquivos.items():
        analise = analisar_pdf(caminho_pdf, empresa, competencia, caminho_config)
        analises[empresa] = analise
        if analise["aprovado"]:
            print(f"{empresa}: OK")
        else:
            prevalidacao_aprovada = False
            print(f"{empresa}: REPROVADA")
            for problema in obter_problemas_prevalidacao(analise):
                print(f"- {problema}")

    if not prevalidacao_aprovada:
        print("\nPROCESSAMENTO NÃO INICIADO")
        print("Nenhum arquivo foi gerado porque um lote foi reprovado.")
        return analises

    print("\nPRÉ-VALIDAÇÃO: APROVADA")
    print("Todos os lotes selecionados podem ser processados.")

    pasta_final = Path(pasta_saida).resolve()
    try:
        nome_competencia = formatar_competencia(competencia)["pasta"]
    except (ValueError, AttributeError) as erro:
        return _marcar_execucao_falha(analises, f"competência inválida: {erro}")

    # O RH escolhe a pasta da competência. Os arquivos ficam diretamente
    # em EMPRESA/ e reprocessamentos em EMPRESA/REVISAO NN.
    try:
        destinos = _escolher_destinos(pasta_final, arquivos, nome_competencia)
    except OSError as erro:
        return _marcar_execucao_falha(
            analises, f"não foi possível consultar entregas anteriores: {erro}"
        )

    resultados = {}
    try:
        pasta_final.mkdir(parents=True, exist_ok=True)
        # Preparar sob o mesmo pai da entrega, inclusive nas revisões,
        # para manter o volume e a política de acesso do destino correto.
        # ExitStack conserva todas as áreas até a publicação ou o descarte.
        with ExitStack() as pilha:
            preparacoes = {}
            for empresa, caminho_pdf in arquivos.items():
                pai = destinos[empresa].parent
                if pai not in preparacoes:
                    preparacoes[pai] = pilha.enter_context(_pasta_preparacao(pai))
                pasta_temporaria = preparacoes[pai]
                print("\n" + "=" * 60)
                print(f"EMPRESA: {empresa} (preparação)")
                print("=" * 60)
                resultado = processar_kit(
                    caminho_pdf,
                    empresa,
                    competencia,
                    pasta_temporaria,
                    caminho_config,
                    pasta_relatorio=destinos[empresa],
                    analise_prevalidada=analises[empresa],
                )
                resultados[empresa] = resultado
                if resultado.get("status") != "SUCESSO":
                    return _marcar_execucao_falha(
                        resultados,
                        f"{empresa} não foi concluída integralmente. "
                        "Nenhum recibo desta execução foi publicado.",
                    )

            # Publica apenas após validação, geração, auditoria E relatório
            # concluídos para TODAS as empresas escolhidas.
            _publicar_pastas(resultados, destinos)

    except (OSError, RuntimeError, ValueError) as erro:
        return _marcar_execucao_falha(
            resultados if resultados else analises,
            f"não foi possível concluir o fechamento: {erro}",
        )

    print("\n" + "=" * 60)
    print("RESUMO GERAL")
    print("=" * 60)
    total = 0
    for empresa, resultado in resultados.items():
        quantidade = len(resultado["geracao"]["arquivos"])
        total += quantidade
        print(f"{empresa}: {quantidade} recibo(s) - OK ({destinos[empresa]})")
    print(f"\nEscopo: {escopo}")
    print(f"Empresas concluídas: {len(resultados)}/{len(arquivos)}")
    print(f"Total de recibos gerados: {total}")
    print("RESULTADO DA EXECUÇÃO: SUCESSO")
    return resultados
