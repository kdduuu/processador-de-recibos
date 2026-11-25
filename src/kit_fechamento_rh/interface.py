"""Janela para organizar os recibos de pagamento do Processador de Recibos.

Execute com: python -m kit_fechamento_rh.interface

"""

import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox, ttk

from kit_fechamento_rh.configuracao_empresas import empresas_disponiveis
from kit_fechamento_rh.processador_fechamento import processar_fechamento

MESES = (

    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",

    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",

)


# Paleta inspirada no VS Code Dark: grafite neutro, sem reflexo azulado.

# Centralizamos as cores para manter a interface fácil de personalizar.

FUNDO = "#121212"         # Base da janela, quase preta

PAINEL = "#1C1C1C"        # Cartões/áreas agrupadas

CAMPO = "#111111"         # Entradas e área de resultados

BORDA = "#333333"         # Bordas discretas

BOTAO = "#292929"         # Botões secundários

BOTAO_HOVER = "#373737"

TEXTO = "#E6E6E6"         # Texto principal

SECUNDARIO = "#B0B0B0"    # Textos de apoio

AZUL = "#0E639C"          # Azul próximo ao do VS Code

AZUL_HOVER = "#1177BB"

VERDE = "#4EC9B0"

AMARELO = "#DCDCAA"

VERMELHO = "#F48771"

def _problemas_do_lote(resultado: dict) -> list[str]:

    """Reúne somente informações úteis ao RH, sem expor CNPJ ou salário."""

    problemas = [

        resultado.get("erro_configuracao"),

        resultado.get("erro_arquivo"),

        resultado.get("erro_lote"),

        *resultado.get("problemas_lote", []),

    ]

    for numero, mensagens in resultado.get("pendencias", []):

        problemas.append(f"Página {numero}: {', '.join(mensagens)}")

    return [str(problema) for problema in problemas if problema]

def resumir_execucao(resultados: dict, destino: str) -> tuple[str, str, int]:

    """Devolve (situação, texto do relatório visual, quantidade gerada).

    Situação: sucesso, ressalva ou falha. Não depende de uma janela Tk.

    """

    if not resultados:

        return "falha", "Nenhum resultado foi recebido do processamento.", 0

    # A pré-validação coletiva retorna análises, antes de existir 'status'.

    if all("status" not in dados for dados in resultados.values()):

        linhas = [

            "PRÉ-VALIDAÇÃO REPROVADA",

            "Nenhum recibo foi gerado. Corrija os problemas e tente novamente.",

            "",

        ]

        for empresa, dados in resultados.items():

            if dados.get("aprovado"):

                linhas.append(f"{empresa}: VALIDADA — não processada porque outro lote falhou.")

            else:

                linhas.append(f"{empresa}: REPROVADA")

                for problema in _problemas_do_lote(dados):

                    linhas.append(f"  • {problema}")

            linhas.append("")

        linhas.append(f"Destino selecionado: {destino}")

        return "falha", "\n".join(linhas), 0

    total = 0

    falhas = 0

    ressalvas = 0

    linhas = ["RESULTADO DO PROCESSAMENTO", ""]

    for empresa, dados in resultados.items():

        status = dados.get("status", "FALHA")

        if status in {"SUCESSO", "SUCESSO_COM_RESSALVA"}:

            quantidade = len(dados["geracao"]["arquivos"])

            total += quantidade

            if status == "SUCESSO":

                linhas.append(f"{empresa}: SUCESSO — {quantidade} recibo(s) gerado(s) e auditado(s).")
                ignoradas = dados.get("paginas_ignoradas", [])
                if ignoradas:
                    linhas.append(
                        f"  • {len(ignoradas)} página(s) idêntica(s) ignorada(s). "
                        "Confira o relatório de processamento."
                    )

            else:

                ressalvas += 1

                linhas.append(f"{empresa}: COM RESSALVA — {quantidade} recibo(s) auditado(s).")

                linhas.append("  • Os PDFs foram gerados, mas houve falha no relatório.")

        else:

            falhas += 1

            linhas.append(f"{empresa}: NÃO CONCLUÍDA")

            problemas = _problemas_do_lote(dados)

            if not problemas and dados.get("auditoria"):

                problemas = dados["auditoria"].get("problemas", [])

            if not problemas:

                problemas = [

                    "Verifique se já existem recibos no destino ou se há "

                    "problemas de permissão."

                ]

            for problema in problemas:

                linhas.append(f"  • {problema}")

        # Mostra onde cada empresa foi publicada, inclusive revisões.
        if status in {"SUCESSO", "SUCESSO_COM_RESSALVA"}:
            pasta_publicada = dados.get("geracao", {}).get("pasta_saida")
            if pasta_publicada is not None:
                linhas.append(f"  Pasta da empresa: {pasta_publicada}")

        linhas.append("")

    linhas.append(f"Total de recibos gerados: {total}")

    linhas.append(f"Pasta de destino: {destino}")

    if falhas:

        linhas.append("ATENÇÃO: não envie arquivos sem conferir as pendências.")

        return "falha", "\n".join(linhas), total

    if ressalvas:

        return "ressalva", "\n".join(linhas), total

    return "sucesso", "\n".join(linhas), total

class InterfaceRH:

    """Interface de uma janela. O motor roda fora da thread visual."""

    def __init__(self, janela: tk.Tk) -> None:

        self.janela = janela

        self.janela.title("Processador de Recibos")

        altura = min(850, max(710, janela.winfo_screenheight() - 85))

        self.janela.geometry(f"900x{altura}")

        self.janela.minsize(810, 690)

        self.janela.configure(bg=FUNDO)

        self.mes = tk.StringVar(value="Selecione o mês")

        self.ano = tk.StringVar(value=str(datetime.now(timezone.utc).astimezone().year))

        self.pasta_saida = tk.StringVar()

        self.status = tk.StringVar(value="Pronto para selecionar arquivos")

        self.arquivos: dict[str, Path] = {}

        self.rotulos: dict[str, tk.Label] = {}

        self.controles: list[tk.Widget] = []

        self.fila: Queue = Queue()

        self.processando = False

        self.texto_resultado = ""

        self.empresas = empresas_disponiveis()

        self._configurar_estilos()

        self._montar_tela()

        self.janela.protocol("WM_DELETE_WINDOW", self._fechar)

    def _configurar_estilos(self) -> None:

        estilo = ttk.Style(self.janela)

        estilo.theme_use("clam")

        estilo.configure(

            "Escuro.TCombobox", foreground=TEXTO, background=CAMPO,

            fieldbackground=CAMPO, selectbackground=CAMPO,

            selectforeground=TEXTO, arrowcolor=SECUNDARIO,

            bordercolor=BORDA, lightcolor=BORDA, darkcolor=BORDA,

            padding=7, font=("Segoe UI", 10),

        )

        estilo.map(

            "Escuro.TCombobox",

            fieldbackground=[("readonly", CAMPO), ("disabled", PAINEL)],

            foreground=[("disabled", SECUNDARIO)],

            selectbackground=[("readonly", CAMPO)],

            selectforeground=[("readonly", TEXTO)],

        )

        estilo.configure(

            "Escuro.Horizontal.TProgressbar", troughcolor=CAMPO,

            background=AZUL, bordercolor=CAMPO, lightcolor=AZUL,

            darkcolor=AZUL, thickness=5,

        )

        estilo.configure(

            "Escuro.Vertical.TScrollbar", background=BORDA,

            troughcolor=CAMPO, bordercolor=CAMPO, arrowcolor=SECUNDARIO,

        )

        # O menu de seleção do mês usa o padrão nativo do Windows.

        self.janela.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    @staticmethod

    def _rotulo(parent, texto, tamanho=10, cor=TEXTO, negrito=False, **kwargs):

        return tk.Label(

            parent, text=texto, bg=parent.cget("bg"), fg=cor,

            font=("Segoe UI", tamanho, "bold" if negrito else "normal"),

            anchor="w", **kwargs,

        )

    @staticmethod

    def _painel(parent) -> tk.Frame:

        return tk.Frame(parent, bg=PAINEL, highlightthickness=1, highlightbackground=BORDA)

    def _botao(self, parent, texto, comando, principal=False, largura=None) -> tk.Button:

        botao = tk.Button(

            parent, text=texto, command=comando,

            bg=AZUL if principal else BOTAO,

            fg="#FFFFFF" if principal else TEXTO,

            activebackground=AZUL_HOVER if principal else BOTAO_HOVER,

            activeforeground="#FFFFFF", borderwidth=0,

            font=("Segoe UI", 10, "bold" if principal else "normal"),

            cursor="hand2", padx=14, pady=8,

            width=largura, disabledforeground=SECUNDARIO,

        )

        return botao

    def _montar_tela(self) -> None:

        conteudo = tk.Frame(self.janela, bg=FUNDO, padx=22, pady=17)

        conteudo.pack(fill="both", expand=True)

        conteudo.columnconfigure(0, weight=1)

        conteudo.rowconfigure(6, weight=1)

        cabecalho = tk.Frame(conteudo, bg=FUNDO)

        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self._rotulo(cabecalho, "Processador de Recibos", tamanho=19, negrito=True).pack(anchor="w")

        self._rotulo(

            cabecalho, "Organize recibos de pagamento com segurança.",

            cor=SECUNDARIO,

        ).pack(anchor="w", pady=(3, 0))

        competencia = self._painel(conteudo)

        competencia.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self._rotulo(competencia, "COMPETÊNCIA", tamanho=9, cor=SECUNDARIO, negrito=True).pack(

            anchor="w", padx=14, pady=(9, 5)

        )

        linha_mes = tk.Frame(competencia, bg=PAINEL)

        linha_mes.pack(fill="x", padx=14, pady=(0, 11))

        self.meses = ttk.Combobox(

            linha_mes, textvariable=self.mes, values=MESES,

            state="readonly", width=20, style="Escuro.TCombobox",

        )

        self.meses.pack(side="left", padx=(0, 16))

        self._rotulo(linha_mes, "Ano", cor=SECUNDARIO).pack(side="left", padx=(0, 7))

        self.campo_ano = tk.Entry(

            linha_mes, textvariable=self.ano, bg=CAMPO, fg=TEXTO,

            insertbackground=TEXTO, relief="flat", highlightthickness=1,

            highlightbackground=BORDA, highlightcolor=AZUL,

            font=("Segoe UI", 10), width=8, justify="center",

        )

        self.campo_ano.pack(side="left", ipady=6)

        self.controles.extend([self.meses, self.campo_ano])

        recibos = self._painel(conteudo)

        recibos.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        recibos.columnconfigure(1, weight=1)

        self._rotulo(recibos, "ARQUIVOS POR EMPRESA", tamanho=9, cor=SECUNDARIO, negrito=True).grid(

            row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(9, 5)

        )

        for indice, empresa in enumerate(self.empresas, start=1):

            self._rotulo(recibos, empresa, negrito=True).grid(

                row=indice, column=0, sticky="w", padx=(14, 14), pady=3

            )

            rotulo = self._rotulo(recibos, "Nenhum PDF selecionado", cor=SECUNDARIO)

            rotulo.grid(row=indice, column=1, sticky="ew", padx=(0, 10))

            self.rotulos[empresa] = rotulo

            selecionar = self._botao(

                recibos, "Selecionar PDF", lambda nome=empresa: self._selecionar_pdf(nome)

            )

            selecionar.grid(row=indice, column=2, sticky="e", pady=3, padx=(0, 7))

            limpar = self._botao(recibos, "Limpar", lambda nome=empresa: self._limpar_pdf(nome))

            limpar.grid(row=indice, column=3, sticky="e", pady=3, padx=(0, 14))

            self.controles.extend([selecionar, limpar])

        self._rotulo(

            recibos, "Escolha apenas as empresas que deseja processar.", cor=SECUNDARIO, tamanho=9,

        ).grid(row=len(self.empresas)+1, column=0, columnspan=4, sticky="w", padx=14, pady=(6, 10))

        destino = self._painel(conteudo)

        destino.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        destino.columnconfigure(0, weight=1)

        self._rotulo(destino, "PASTA DE DESTINO", tamanho=9, cor=SECUNDARIO, negrito=True).grid(

            row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(9, 6)

        )

        self.campo_destino = tk.Entry(

            destino, textvariable=self.pasta_saida, state="readonly",

            readonlybackground=CAMPO, fg=TEXTO, relief="flat",

            font=("Segoe UI", 10), highlightthickness=1,

            highlightbackground=BORDA,

        )

        self.campo_destino.grid(row=1, column=0, sticky="ew", padx=(14, 10), pady=(0, 11), ipady=7)

        botao_pasta = self._botao(destino, "Escolher pasta", self._selecionar_pasta)

        botao_pasta.grid(row=1, column=1, padx=(0, 7), pady=(0, 11))

        botao_limpar_pasta = self._botao(destino, "Limpar", self._limpar_pasta)

        botao_limpar_pasta.grid(row=1, column=2, padx=(0, 14), pady=(0, 11))

        self.controles.extend([botao_pasta, botao_limpar_pasta])

        acoes = tk.Frame(conteudo, bg=FUNDO)

        acoes.grid(row=4, column=0, sticky="ew", pady=(0, 8))

        acoes.columnconfigure(0, weight=1)

        self.botao_processar = self._botao(

            acoes, "PROCESSAR RECIBOS", self._iniciar, principal=True

        )

        self.botao_processar.grid(row=0, column=0, sticky="ew", ipady=3)

        self.linha_status = tk.Frame(conteudo, bg=FUNDO)

        self.linha_status.grid(row=5, column=0, sticky="ew", pady=(0, 9))

        self.linha_status.columnconfigure(0, weight=1)

        self.rotulo_status = self._rotulo(self.linha_status, "", cor=SECUNDARIO, tamanho=9)

        self.rotulo_status.configure(textvariable=self.status)

        self.rotulo_status.grid(row=0, column=0, sticky="w")

        self.progresso = ttk.Progressbar(

            self.linha_status, mode="indeterminate", style="Escuro.Horizontal.TProgressbar",

            length=150,

        )

        self.progresso.grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.progresso.grid_remove()

        caixa_resultados = self._painel(conteudo)
        caixa_resultados.grid(row=6, column=0, sticky="nsew")
        caixa_resultados.columnconfigure(0, weight=1)
        caixa_resultados.rowconfigure(1, weight=1)

        topo_resultados = tk.Frame(caixa_resultados, bg=PAINEL)
        topo_resultados.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        topo_resultados.columnconfigure(0, weight=1)
        self._rotulo(
            topo_resultados, "RESULTADO DA EXECUÇÃO", tamanho=9,
            cor=SECUNDARIO, negrito=True,
        ).grid(row=0, column=0, sticky="w")
        self.botao_ampliar = self._botao(
            topo_resultados, "Ver detalhes completos", self._ampliar_resultado
        )
        self.botao_ampliar.grid(row=0, column=1, sticky="e")

        # Resumo sem Text/scrollbar: o RH vê todas as empresas e o total.
        resumo = tk.Frame(caixa_resultados, bg=CAMPO, padx=14, pady=10)
        resumo.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        resumo.columnconfigure(0, weight=1)
        self.resumo_titulo = self._rotulo(
            resumo, "Aguardando processamento", tamanho=11, negrito=True
        )
        self.resumo_titulo.grid(row=0, column=0, sticky="w", pady=(0, 7))
        self.resumo_empresas = self._rotulo(
            resumo, "Selecione os PDFs e a pasta de destino.", cor=SECUNDARIO,
            justify="left", wraplength=760
        )
        self.resumo_empresas.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.resumo_total = self._rotulo(resumo, "", negrito=True)
        self.resumo_total.grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.resumo_destino = self._rotulo(
            resumo, "", cor=SECUNDARIO, tamanho=9, wraplength=760,
            justify="left"
        )
        self.resumo_destino.grid(row=3, column=0, sticky="ew")
        resumo.bind(
            "<Configure>",
            lambda evento: (
                self.resumo_empresas.configure(wraplength=max(350, evento.width - 28)),
                self.resumo_destino.configure(wraplength=max(350, evento.width - 28)),
            ),
        )
        self._exibir_resultado(
            "O resumo do processamento aparecerá aqui.\n"
            "Os recibos originais nunca são alterados."
        )

    def _atualizar_resumo_visual(self, resultados: dict, destino: str, situacao: str, total: int) -> None:
        """Resumo imediato; mensagens extensas permanecem na janela de detalhes."""
        cores = {"sucesso": VERDE, "ressalva": AMARELO, "falha": VERMELHO}
        titulos = {
            "sucesso": "Processamento concluído com sucesso",
            "ressalva": "Concluído com ressalvas — confira os detalhes",
            "falha": "Processamento não concluído — confira os detalhes",
        }
        self.resumo_titulo.configure(text=titulos[situacao], fg=cores[situacao])
        linhas = []
        for empresa, dados in resultados.items():
            status = dados.get("status")
            if status in {"SUCESSO", "SUCESSO_COM_RESSALVA"}:
                quantidade = len(dados.get("geracao", {}).get("arquivos", []))
                etiqueta = "OK" if status == "SUCESSO" else "RESSALVA"
                pasta_publicada = dados.get("geracao", {}).get("pasta_saida")
                if pasta_publicada is not None and Path(pasta_publicada).name.startswith("REVISAO "):
                    revisao = Path(pasta_publicada).name.split("REVISAO ", 1)[1]
                    etiqueta_empresa = f"{empresa} (REVISÃO {revisao})"
                else:
                    etiqueta_empresa = empresa
                copia_ignorada = len(dados.get("paginas_ignoradas", []))
                sufixo = f" — {copia_ignorada} cópia(s) idêntica(s) ignorada(s)" if copia_ignorada else ""
                linhas.append(f"{etiqueta_empresa}: {quantidade} recibo(s) auditado(s) — {etiqueta}{sufixo}")
            elif status is None and dados.get("aprovado"):
                linhas.append(f"{empresa}: validada, mas não processada")
            else:
                linhas.append(f"{empresa}: FALHA — consulte os detalhes")
        self.resumo_empresas.configure(text="\n".join(linhas) or "Nenhuma empresa processada.")
        self.resumo_total.configure(text=f"Total de recibos gerados: {total}")
        self.resumo_destino.configure(text=f"Destino: {destino}")

    def _selecionar_pdf(self, empresa: str) -> None:

        arquivo = filedialog.askopenfilename(

            parent=self.janela,

            title=f"Selecionar recibos de {empresa}",

            filetypes=[("Arquivos PDF", "*.pdf")],

        )

        if arquivo:

            self.arquivos[empresa] = Path(arquivo)

            nome = Path(arquivo).name

            self.rotulos[empresa].configure(

                text=nome if len(nome) <= 52 else nome[:49] + "...", fg=TEXTO,

            )

    def _limpar_pdf(self, empresa: str) -> None:

        self.arquivos.pop(empresa, None)

        self.rotulos[empresa].configure(text="Nenhum PDF selecionado", fg=SECUNDARIO)

    def _selecionar_pasta(self) -> None:

        pasta = filedialog.askdirectory(

            parent=self.janela, title="Selecionar pasta de saída", mustexist=True,

        )

        if pasta:

            self.pasta_saida.set(pasta)

    def _limpar_pasta(self) -> None:

        self.pasta_saida.set("")

    def _validacao_falhou(self, titulo: str, mensagem: str) -> None:

        self.status.set("Preencha os campos indicados para continuar")

        self.rotulo_status.configure(fg=AMARELO)

        self._exibir_resultado("Processamento não iniciado.\n" + mensagem)
        self.resumo_titulo.configure(text="Processamento não iniciado", fg=AMARELO)
        self.resumo_empresas.configure(text=mensagem)
        self.resumo_total.configure(text="")
        self.resumo_destino.configure(text="")

        messagebox.showwarning(titulo, mensagem, parent=self.janela)

    def _iniciar(self) -> None:

        if self.processando:

            return

        # Não exibir o resultado da execução anterior numa tentativa nova.

        self._exibir_resultado("")

        self.status.set("Conferindo os dados informados...")

        self.rotulo_status.configure(fg=SECUNDARIO)

        mes = self.mes.get()

        ano = self.ano.get().strip()

        if mes not in MESES or len(ano) != 4 or not ano.isdigit() or not 2000 <= int(ano) <= 2100:

            self._validacao_falhou("Competência", "Selecione um mês e informe um ano com quatro dígitos.")

            return

        if not self.arquivos:

            self._validacao_falhou("Recibos", "Selecione pelo menos um PDF.")

            return

        if not self.pasta_saida.get():

            self._validacao_falhou("Destino", "Selecione a pasta onde salvar os recibos.")

            return

        if any(not arquivo.is_file() for arquivo in self.arquivos.values()):

            self._validacao_falhou("Arquivo não encontrado", "Um PDF selecionado não existe mais.")

            return

        if not Path(self.pasta_saida.get()).is_dir():

            self._validacao_falhou("Destino", "A pasta selecionada não existe ou não está acessível.")

            return

        competencia = f"{mes}/{ano}"

        arquivos = dict(self.arquivos)

        destino = self.pasta_saida.get()

        empresas = ", ".join(arquivos)

        confirmar = messagebox.askyesno(

            "Confirmar processamento",

            f"Competência: {competencia}\nEmpresas: {empresas}\n\n"

            f"Destino: {destino}\n\nDeseja iniciar?",

            parent=self.janela,

        )

        if not confirmar:

            self.status.set("Processamento cancelado")

            return

        self._alternar_processamento(True)

        Thread(

            target=self._executar, args=(arquivos, competencia, destino), daemon=False,

        ).start()

        self.janela.after(120, self._verificar_fila)

    def _executar(self, arquivos: dict, competencia: str, destino: str) -> None:

        try:

            resultados = processar_fechamento(

                arquivos, competencia, pasta_saida=destino,

            )

        except Exception as erro:  # noqa: BLE001 — proteção da interface contra erros inesperados

            self.fila.put(("erro", f"{type(erro).__name__}: {erro}"))

        else:

            self.fila.put(("resultado", (resultados, destino)))

    def _verificar_fila(self) -> None:

        try:

            tipo, conteudo = self.fila.get_nowait()

        except Empty:

            self.janela.after(120, self._verificar_fila)

            return

        self._alternar_processamento(False)

        if tipo == "erro":

            self.status.set("Execução interrompida por um erro inesperado")

            self.rotulo_status.configure(fg=VERMELHO)

            self._exibir_resultado(f"Não foi possível concluir a execução.\n\nDetalhes: {conteudo}")
            self.resumo_titulo.configure(text="Erro inesperado", fg=VERMELHO)
            self.resumo_empresas.configure(text="Confira os detalhes completos.")

            messagebox.showerror("Erro", "O processamento foi interrompido. Confira o resultado.", parent=self.janela)

            return

        resultados, destino = conteudo

        self._mostrar_resumo(resultados, destino)

    def _mostrar_resumo(self, resultados: dict, destino: str) -> None:

        situacao, texto, total = resumir_execucao(resultados, destino)

        self._exibir_resultado(texto)
        self._atualizar_resumo_visual(resultados, destino, situacao, total)

        if situacao == "falha":

            self.status.set("Não concluído — confira as pendências")

            self.rotulo_status.configure(fg=VERMELHO)

            messagebox.showwarning(

                "Atenção", "O processamento não foi concluído integralmente. Confira o resultado.",

                parent=self.janela,

            )

        elif situacao == "ressalva":

            self.status.set("Concluído com ressalvas")

            self.rotulo_status.configure(fg=AMARELO)

            messagebox.showwarning(

                "Ressalva", "Os PDFs foram gerados, mas houve ressalvas no relatório.",

                parent=self.janela,

            )

        else:

            self.status.set("Concluído com sucesso")

            self.rotulo_status.configure(fg=VERDE)

            total_copias = sum(
                len(dados.get("paginas_ignoradas", []))
                for dados in resultados.values()
            )
            complemento = (
                f"\n{total_copias} cópia(s) idêntica(s) ignorada(s). "
                "Confira os detalhes e o relatório."
                if total_copias else ""
            )
            messagebox.showinfo(

                "Concluído", f"{total} recibos gerados e auditados.{complemento}", parent=self.janela,

            )

    def _ampliar_resultado(self) -> None:

        """Abre o resumo em uma janela maior e rolável, sem repetir o motor."""

        detalhes = tk.Toplevel(self.janela)

        detalhes.title("Resultado completo — Processador de Recibos")

        detalhes.configure(bg=FUNDO)

        detalhes.geometry("790x520")

        detalhes.minsize(600, 390)

        detalhes.transient(self.janela)

        corpo = tk.Frame(detalhes, bg=FUNDO, padx=18, pady=15)

        corpo.pack(fill="both", expand=True)

        self._rotulo(

            corpo, "Resultado completo", tamanho=16, negrito=True,

        ).pack(anchor="w", pady=(0, 12))

        area = tk.Frame(corpo, bg=CAMPO)

        area.pack(fill="both", expand=True)

        campo = tk.Text(

            area, wrap="word", bg=CAMPO, fg=TEXTO,

            font=("Consolas", 11), relief="flat", padx=16, pady=14,

            borderwidth=0, highlightthickness=0,

        )

        campo.pack(side="left", fill="both", expand=True)

        barra = ttk.Scrollbar(

            area, orient="vertical", command=campo.yview,

            style="Escuro.Vertical.TScrollbar",

        )

        barra.pack(side="right", fill="y")

        campo.configure(yscrollcommand=barra.set)

        campo.insert("1.0", self.texto_resultado or "Nenhum resultado disponível.")

        campo.configure(state="disabled")

        self._botao(corpo, "Fechar", detalhes.destroy).pack(anchor="e", pady=(12, 0))

    def _exibir_resultado(self, texto: str) -> None:

        """Guarda o relatório completo para a janela de detalhes.

        O resumo principal agora é composto por rótulos, não por tk.Text.
        """

        self.texto_resultado = texto

    def _alternar_processamento(self, ativo: bool) -> None:

        self.processando = ativo

        self.botao_processar.configure(state="disabled" if ativo else "normal")

        for controle in self.controles:

            if controle is self.meses:

                controle.configure(state="disabled" if ativo else "readonly")

            elif controle is self.campo_ano:

                controle.configure(state="disabled" if ativo else "normal")

            else:

                controle.configure(state="disabled" if ativo else "normal")

        if ativo:

            self.progresso.grid()

            self.progresso.start(12)

            self.rotulo_status.configure(fg=AZUL)

            self.status.set("Processando e auditando... aguarde sem fechar a janela")

        else:

            self.progresso.stop()

            self.progresso.configure(value=0)

            self.progresso.grid_remove()

    def _fechar(self) -> None:

        if self.processando:

            messagebox.showwarning(

                "Processamento em andamento", "Aguarde a conclusão antes de fechar a janela.",

                parent=self.janela,

            )

            return

        self.janela.destroy()

def main() -> None:

    janela = tk.Tk()

    InterfaceRH(janela)

    janela.mainloop()

if __name__ == "__main__":

    main()
