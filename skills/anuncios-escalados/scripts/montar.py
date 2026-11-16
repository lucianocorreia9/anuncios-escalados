"""
montar.py: monta a planilha final (.xlsx) de um concorrente e confere o resultado.

Precisa do openpyxl. Rodar pelo uv:
  uv run --no-project --python 3.13 --with openpyxl --with pillow python montar.py --apelido loja-exemplo --saida <pasta>
  --roteiros 15   meta da primeira entrega
  (opcional) --csv           também grava um .csv por aba, numa pasta ao lado

Abas: Como ler | Grupos | Todos os Vídeos | Todos os Anúncios | Roteiros Validados.
Padrão visual e de colunas da planilha do Gabriel Navarro (24/09/2026), com "Grupo" no lugar de
"Família" e a página de destino com o endereço completo.
No fim, reabre o arquivo e confere contagens e links. Se algo não bater, sai com erro.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlparse

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage

import comum as C
from agrupar import expandir
from criativos_locais import nome_pasta
from cobertura import LOTE_INICIAL, verificar
from painel import aplicar as aplicar_painel

AR = "Arial"
H = Font(name=AR, bold=True, color="FFFFFF", size=10)
HF = PatternFill("solid", fgColor="1F3A5F")
N = Font(name=AR, size=10)
B = Font(name=AR, size=10, bold=True)
LNK = Font(name=AR, size=10, color="1155CC", underline="single")
COR_NIVEL = {0: "C6EFCE", 1: "E2F0D9", 2: "FFF2CC", 3: "DDEBF7", 4: "EDEDED", 5: "F8F8F8"}
BORDA = Border(bottom=Side(style="thin", color="D9D9D9"))
LIMITE_CELULA = 32000


class Link:
    def __init__(self, texto, url):
        self.texto, self.url = texto, url


def corrigir(t: str, correcoes) -> str:
    for a, b in correcoes:
        t = t.replace(a, b)
    return re.sub(r"[ \t]+", " ", t).strip()


WHATSAPP = "WhatsApp (anúncio de conversa: a Meta não mostra o número)"


def mostrar_destino(d: str):
    """Link clicável com o endereço completo; texto quando não há endereço útil."""
    if not d:
        return "(sem link)"
    if "whatsapp.com/send" in d and "phone=" not in d:
        return WHATSAPP
    return Link(d, d)


def celula_destinos(rs: list):
    """Um endereço: link clicável. Vários: um por linha, o mais usado primeiro (o Google Sheets
    transforma cada endereço completo em link)."""
    cont = {}
    for r in rs:
        d = mostrar_destino(C.destino(r))
        d = d.url if isinstance(d, Link) else d
        cont[d] = cont.get(d, 0) + 1
    ds = sorted(cont, key=lambda d: (not d.startswith("http"), -cont[d]))  # endereços antes de "(sem link)"
    if len(ds) == 1:
        return Link(ds[0], ds[0]) if ds[0].startswith("http") else ds[0]
    extra = f"\n+ {len(ds) - 8} outras páginas" if len(ds) > 8 else ""
    return "\n".join(ds[:8]) + extra


def aba(ws, cab, linhas, larguras, quebra=(), col_nivel=None, col_situacao=None, congelar="C2"):
    ws.append(cab)
    for c in ws[1]:
        c.font, c.fill = H, HF
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    for linha in linhas:
        ws.append([v.texto if isinstance(v, Link) else v for v in linha])
        rr = ws.max_row
        for j, v in enumerate(linha, 1):
            cel = ws.cell(rr, j)
            cel.font, cel.border = N, BORDA
            cel.alignment = Alignment(vertical="top", wrap_text=(j in quebra))
            if isinstance(v, Link):
                cel.hyperlink, cel.font = v.url, LNK
        if col_nivel:
            cel = ws.cell(rr, col_nivel)
            cel.fill = PatternFill("solid", fgColor=COR_NIVEL[C.NIVEIS.index(cel.value)])
            cel.font = B
        if col_situacao:
            cel = ws.cell(rr, col_situacao)
            cel.fill = PatternFill("solid", fgColor="C6EFCE" if cel.value == "Ativo" else "EDEDED")
    for j, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = congelar
    ws.auto_filter.ref = ws.dimensions


def nome_arquivo(nome: str, T) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    s = "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w)
    return f"Anuncios-Meta-{s}-{T:%Y-%m-%d}.xlsx"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apelido", required=True)
    ap.add_argument("--saida", required=True, help="pasta-base de concorrentes ou a pasta do próprio concorrente")
    ap.add_argument("--concorrente", help="nome do concorrente sem o produto, usado para a pasta nome_sobrenome")
    ap.add_argument("--roteiros", type=int, choices=[LOTE_INICIAL], help="meta da primeira entrega")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument('--permitir-parcial', action='store_true', help='entregar os disponíveis, com cobertura incompleta explícita')
    a = ap.parse_args()
    p = C.pasta(a.apelido)
    meta = C.ler(p, "meta.json")
    pasta_nome = nome_pasta(a.concorrente or meta.get("concorrente") or meta["nome"].split(" - ")[0])
    destino = Path(a.saida).expanduser().resolve()
    if destino.name.lower() != pasta_nome:
        destino = destino / pasta_nome
    midias = C.ler(p, "midias-locais.json", {})
    T = C.momento_coleta(p)
    arq = str(destino / nome_arquivo(meta['nome'], T))
    anterior = C.ler(p, 'ultima-planilha.json', {}).get('arquivo')
    if Path(arq).exists() or (anterior and Path(anterior).is_file()):
        sys.exit('Já existe uma planilha desta pesquisa: ' + (anterior or arq) + '. Editar esse arquivo com atualizar.py ou edição pontual; não reconstruir as abas.')
    anuncios = C.ler(p, "anuncios.json")
    fora = C.ler(p, "fora.json", [])
    por_id = {r["ad_archive_id"]: r for r in anuncios}
    cri_all = C.ler(p, "criativos.json")
    cri = cri_all["criativos"]
    cobertura = verificar(p)
    meta_roteiros = LOTE_INICIAL
    ordem_rot = cobertura['validos'][:meta_roteiros]
    parcial = len(ordem_rot) < meta_roteiros
    if parcial and not a.permitir_parcial:
        sys.exit(f'Lote incompleto: {len(ordem_rot)} de {meta_roteiros} roteiros. Rodar cobertura.py --conferir.')
    gj = C.ler(p, "grupos.json")
    if not gj:
        sys.exit("Sem grupos.json: o agente precisa agrupar antes (agrupar.py preparar / conferir).")
    grupo_de, prob = expandir(p, gj)
    if prob:
        sys.exit("grupos.json com problemas: " + "; ".join(prob))
    corr = gj.get("correcoes", [])
    ab = {k: corrigir(t, corr) for k, t in C.ler(p, "aberturas.json", {}).items()}
    rot = {k: corrigir(t, corr) for k, t in C.ler(p, "roteiros.json", {}).items()}
    G = gj["grupos"]

    def rs_de(ids):
        return [por_id[i] for i in ids]

    def abertura(k):
        c = cri[k]
        if c["tipo"] == "video":
            return ab.get(k) or "(vídeo sem fala nos 16 s iniciais)"
        r = por_id[c["exemplo"]]
        rotulo = ("(anúncio de imagem)" if c["tipo"] == "imagem" else
                  "(conteúdo retirado pela Meta)" if c["formato"] == "Retirado pela Meta" else "(anúncio sem mídia)")
        return f"{rotulo} {r['snapshot'].get('title') or ''} {C.texto(r)}".strip()

    # criativos
    CR = []
    for k, c in cri.items():
        rs = rs_de(c["ids"])
        x = C.resumir(rs, T)
        textos = {}
        for r in rs:
            t = C.texto(r)
            textos[t] = textos.get(t, 0) + 1
        x.update(k=k, g=grupo_de[k], rs=rs, dest=celula_destinos(rs), hook=abertura(k), formato=c["formato"],
                 dur=c.get("dur"), n_textos=len(textos), texto=max(textos, key=textos.get) if textos else "",
                 bloq=sum(1 for r in rs if C.bloqueado(r)))
        CR.append(x)
    # grupos
    GR = []
    for i, g in enumerate(G):
        membros = [x for x in CR if x["g"] == i]
        rs = [r for x in membros for r in x["rs"]]
        y = C.resumir(rs, T)
        membros.sort(key=C.ordem_escala)
        nvid = sum(1 for x in membros if cri[x["k"]]["tipo"] == "video")
        y.update(i=i, nome=g["nome"], tipo=g["tipo"], dest=celula_destinos(rs), hook=membros[0]["hook"],
                 top=membros[0], nvid=nvid or "-", bloq=sum(1 for r in rs if C.bloqueado(r)))
        GR.append(y)
    GR.sort(key=C.ordem_escala)
    pos_g = {y["i"]: n + 1 for n, y in enumerate(GR)}
    CR.sort(key=lambda x: (pos_g[x["g"]],) + C.ordem_escala(x))
    pos_c = {x["k"]: n + 1 for n, x in enumerate(CR)}
    cr_de = {x["k"]: x for x in CR}

    def data_br(d):
        return d.strftime("%d/%m/%Y")

    def ver(r):
        return Link("Abrir anúncio", r["url"])

    wb = Workbook()
    # ---- Como ler
    ws = wb.active
    ws.title = "Como ler"
    ativos = sum(1 for r in anuncios if r.get("is_active"))
    pags = {}
    for r in anuncios:
        pags[r["snapshot"].get("page_name")] = pags.get(r["snapshot"].get("page_name"), 0) + 1
    pags_txt = ", ".join(f'"{k}"' for k in sorted(pags, key=lambda k: -pags[k])[:8]) + (f" e mais {len(pags) - 8}" if len(pags) > 8 else "")
    buscas, vazias = [], []
    for alvo in meta["alvos"]:
        if alvo["tipo"] == "dominio":
            buscas.append("do site " + alvo["valor"].split("//")[-1].split("/")[0])
        elif alvo["tipo"] == "termo" and alvo.get("total"):
            buscas.append(f"da frase \"{alvo['valor']}\"")
        elif alvo["tipo"] == "termo":
            vazias.append(f"\"{alvo['valor']}\"")
    n_pag_alvo = sum(1 for alvo in meta["alvos"] if alvo["tipo"] == "pagina")
    if n_pag_alvo:
        buscas.append(f"de {n_pag_alvo} página{'s' if n_pag_alvo > 1 else ''} do anunciante no Facebook")
    buscas = ", ".join(buscas[:-1]) + " e " + buscas[-1] if len(buscas) > 1 else buscas[0]
    n_rot = len(ordem_rot)
    fora_pags = sorted({r["snapshot"].get("page_name") or "?" for r in fora})
    linhas = [
        (f"Anúncios de {meta['nome']} na biblioteca da Meta", "t"),
        (f"Retrato de {data_br(T)}. {len(anuncios)} anúncios encontrados pela busca {buscas} no Brasil, "
         f"{ativos} ativos no momento da consulta. Páginas anunciantes: {pags_txt}."
         + (f" A busca por {' e '.join(vazias)} não trouxe nenhum anúncio." if vazias else ""), ""),
        ("", ""), ("O que tem em cada aba", "h"),
        ("Grupos: um grupo por gancho, do mais escalado para o menos escalado.", ""),
        ("Todos os Vídeos: cada vídeo diferente (e cada imagem diferente), com os números de escala dele.", ""),
        ("Todos os Anúncios: cada anúncio encontrado, com o link para ele na biblioteca da Meta.", ""),
        (f"Roteiros Validados: {n_rot} vídeos baixados e transcritos. Cobertura: {cobertura['grupos_cobertos']} de {cobertura['total_grupos_video']} ganchos em vídeo. "
         "A ordem segue as cópias de cada vídeo, o maior tempo no ar e o número de ativos.", ""),
        ("", ""), ("O que é um Grupo", "h"),
        ("O grupo é definido pela abertura do vídeo (o gancho): os primeiros 16 segundos de cada vídeo foram transcritos e "
         "agrupados com um nome para o gancho. A identificação de vídeos compara prints de momentos diferentes, "
         "duração e capa. Anúncios de imagem ficam em grupos próprios, pelo tema do texto.", ""),
        ("", ""), ("Como a ordem foi feita (critérios de escala)", "h"),
        ("1) Mais cópias do criativo ou do grupo vêm primeiro, mesmo quando já pausadas.", ""),
        ("2) Desempate pelo maior tempo histórico no ar, depois mais ativos e melhor posição na busca.", ""),
        ("3) Os níveis descrevem o histórico. Cópias e dias são sinais indiretos, sem comprovar conversão ou lucro.", ""),
        ("", ""), ("Níveis de escala", "h")] + [(n, "") for n in C.NIVEIS] + [
        ("", ""), ("Limites (o que a planilha não mostra)", "h"),
        ("A Meta não mostra no Brasil gasto, alcance nem engajamento de anúncio comercial. \"Posição por impressões\" é a "
         "ordem em que a própria Meta lista os anúncios do mais exibido para o menos exibido, dentro da busca feita: "
         "indica volume relativo, não número absoluto.", ""),
        ("As aberturas e os roteiros são transcrição automática. Erros de fala óbvios foram corrigidos, mas pode sobrar algum.", ""),
    ]
    bloq = [r for r in anuncios if C.bloqueado(r)]
    if bloq:
        tipos = {}
        for r in bloq:
            tipos[C.situacao_meta(r)] = tipos.get(C.situacao_meta(r), 0) + 1
        plural = {"Derrubado pela Meta": "derrubados pela Meta", "Conta de anúncios desativada": "de conta de anúncios desativada",
                  "Página desativada": "de página desativada"}
        linhas.append((f"{len(bloq)} dos {len(anuncios)} anúncios saíram do ar por ação da Meta ("
                       + ", ".join(f"{v} {plural.get(k, k)}" for k, v in sorted(tipos.items(), key=lambda t: -t[1]))
                       + "). Nesses casos, \"pausado\" não foi decisão do anunciante: veja a coluna \"Situação na Meta\" "
                       "em Todos os Anúncios. Anúncio derrubado pela Meta não mostra mais o vídeo nem o texto.", ""))
    if fora:
        linhas.append((f"{len(fora)} anúncios de outros anunciantes que apareceram na busca foram retirados "
                       f"({', '.join(fora_pags[:6])}{'...' if len(fora_pags) > 6 else ''}).", ""))
    for t, estilo in linhas:
        ws.append([t])
        c = ws.cell(ws.max_row, 1)
        c.font = Font(name=AR, size=12 if estilo == "t" else 11 if estilo == "h" else 10, bold=bool(estilo))
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 100

    # ---- Grupos
    ws = wb.create_sheet("Grupos")
    aba(ws, ["Posição", "Grupo de gancho (abertura do vídeo)", "Tipo de gancho", "Nível de escala", "Anúncios ativos agora",
             "Dias no ar do anúncio ativo mais antigo", "Dias no ar do anúncio mais longo (histórico)",
             "Dias em uso (1º anúncio ao último)", "Total de anúncios", "Vídeos diferentes",
             "Melhor posição por impressões (1 = mais exibido)", "1º anúncio", "Último dia", "Páginas de destino",
             "Abertura do vídeo mais escalado (transcrição automática)", "Anúncio de exemplo",
             "Anúncios derrubados ou bloqueados pela Meta"],
        [[n + 1, y["nome"], y["tipo"], y["nivel"], y["ativos"], y["dias_ativo"] or "-", y["maior"], y["uso"], y["n"], y["nvid"],
          y["rank"], data_br(y["primeiro"]), y["ultimo"], y["dest"], y["hook"], ver(y["top"]["melhor"]), y["bloq"]]
         for n, y in enumerate(GR)],
        [8, 48, 26, 30, 10, 12, 12, 12, 10, 10, 13, 12, 12, 45, 70, 15, 13], quebra=(2, 3, 4, 14, 15), col_nivel=4)

    # ---- Todos os Vídeos
    ws = wb.create_sheet("Todos os Vídeos")
    aba(ws, ["Posição", "Grupo de gancho", "Nível de escala", "Formato", "Anúncios ativos agora",
             "Dias no ar do anúncio ativo mais antigo", "Dias no ar do anúncio mais longo (histórico)", "Dias em uso",
             "Total de anúncios (cópias do vídeo)", "Páginas anunciantes", "Melhor posição por impressões",
             "Duração do vídeo (s)", "1º anúncio", "Último dia", "Páginas de destino",
             "Abertura (primeiros 16 s, transcrição automática)", "Textos de anúncio usados", "Texto principal do anúncio",
             "Anúncio de exemplo", "Grupo (posição)", "Código do vídeo", "Anúncios derrubados ou bloqueados pela Meta"],
        [[pos_c[x["k"]], G[x["g"]]["nome"], x["nivel"], x["formato"], x["ativos"], x["dias_ativo"] or "-", x["maior"], x["uso"],
          x["n"], x["paginas"], x["rank"], x["dur"] if x["dur"] else "-", data_br(x["primeiro"]), x["ultimo"], x["dest"],
          x["hook"], x["n_textos"], x["texto"], ver(x["melhor"]), pos_g[x["g"]], x["k"], x["bloq"]] for x in CR],
        [8, 40, 30, 10, 10, 12, 12, 10, 12, 10, 12, 10, 12, 12, 45, 70, 10, 50, 15, 10, 10, 13], quebra=(2, 3, 15, 16, 18), col_nivel=3)

    # ---- Todos os Anúncios
    ws = wb.create_sheet("Todos os Anúncios")
    ks = {r["ad_archive_id"]: k for k, c in cri.items() for r in rs_de(c["ids"])}
    ordem_an = sorted(anuncios, key=lambda r: (pos_g[grupo_de[ks[r["ad_archive_id"]]]], pos_c[ks[r["ad_archive_id"]]],
                                                not r.get("is_active"), -C.dias_no_ar(r, T)))
    linhas_an = []
    for r in ordem_an:
        k = ks[r["ad_archive_id"]]
        d = C.destino(r)
        linhas_an.append([pos_g[grupo_de[k]], G[grupo_de[k]]["nome"], pos_c[k], "Ativo" if r.get("is_active") else "Pausado",
                          C.situacao_meta(r), C.dias_no_ar(r, T), data_br(C.data(r["start_date"])),
                          "no ar hoje" if r.get("is_active") else data_br(C.fim(r, T)), r.get("_rank"),
                          r["snapshot"].get("page_name"), C.midia(r)["formato"], mostrar_destino(d),
                          r["snapshot"].get("title") or "", C.texto(r), ver(r), r["ad_archive_id"]])
    aba(ws, ["Grupo (posição)", "Grupo de gancho", "Vídeo (posição)", "Situação", "Situação na Meta", "Dias no ar", "Início",
             "Fim", "Posição por impressões", "Página anunciante", "Formato", "Página de destino", "Título", "Texto do anúncio",
             "Biblioteca da Meta", "ID do anúncio"],
        linhas_an, [9, 40, 9, 10, 16, 9, 11, 11, 11, 24, 10, 40, 26, 50, 14, 18], quebra=(2, 5), col_situacao=4)
    for rr in range(2, ws.max_row + 1):
        if ws.cell(rr, 5).value != "Normal":
            ws.cell(rr, 5).fill = PatternFill("solid", fgColor="F8CBAD")

    # ---- Roteiros Validados
    ws = wb.create_sheet("Roteiros Validados")
    esc = list(ordem_rot)
    linhas_rot = []
    for n, k in enumerate(esc, 1):
        x = cr_de[k]
        t = rot[k]
        media = midias.get(k, {})
        arquivo = Path(media.get("arquivo", ""))
        if not media.get("conferido") or not arquivo.is_file() or not media.get("print") or not Path(media["print"]).is_file():
            sys.exit(f"MP4 ou print não conferido para {k}. Rode criativos_locais.py antes de montar.")
        if not t.strip():
            sys.exit(f"Transcrição vazia para {k}; revisar o áudio antes de contar como roteiro validado.")
        if len(t) > LIMITE_CELULA:
            sys.exit(f'Transcrição de {k} excede uma célula; distribuir em continuação antes de entregar, sem cortar a fala.')
        linhas_rot.append([n, G[x["g"]]["nome"], G[x["g"]]["tipo"], pos_c[k], x["nivel"], "Ativo" if x["ativos"] else "Pausado",
                           x["maior"], x["ativos"], x["n"], x["dur"] or "-", x["dest"], Link("Assistir vídeo", arquivo.resolve().as_uri()), t, ""])
    aba(ws, ["Posição", "Grupo de gancho", "Tipo de gancho", "Vídeo (posição)", "Nível de escala", "Situação hoje",
             "Dias no ar do anúncio mais longo", "Anúncios ativos agora", "Total de anúncios (cópias do vídeo)",
             "Duração do vídeo (s)", "Página de destino", "Vídeo baixado (MP4)", "Roteiro completo (transcrição automática)", "Print do vídeo (2 segundos)"],
        linhas_rot, [8, 36, 22, 9, 28, 10, 11, 10, 11, 10, 40, 19, 110, 41], quebra=(2, 3, 5, 11, 13), col_nivel=5, col_situacao=6)
    for rr, k in enumerate(esc, 2):
        image = XLImage(midias[k]["print"])
        scale = min(270 / image.width, 460 / image.height)
        image.width, image.height = image.width * scale, image.height * scale
        ws.add_image(image, f"N{rr}")
        ws.row_dimensions[rr].height = 360

    aplicar_painel(wb, p)
    os.makedirs(destino, exist_ok=True)
    wb.save(arq)

    # ---- conferência: reabre o arquivo salvo
    wb2 = load_workbook(arq)
    erros = []
    esperado = {"Como ler": None, "Grupos": len(GR), "Todos os Vídeos": len(CR), "Todos os Anúncios": len(anuncios),
                "Roteiros Validados": len(esc)}
    if wb2.sheetnames != list(esperado):
        erros.append(f"abas: {wb2.sheetnames}")
    for nome, n in esperado.items():
        if n is not None and wb2[nome].max_row - 1 != n:
            erros.append(f"{nome}: {wb2[nome].max_row - 1} linhas, esperado {n}")
    for nome, col in (("Grupos", 14), ("Todos os Vídeos", 15), ("Todos os Anúncios", 12), ("Roteiros Validados", 11)):
        for rr in range(2, wb2[nome].max_row + 1):
            v = str(wb2[nome].cell(rr, col).value or "")
            ruins = [x for x in v.split("\n") if not x.startswith(("http", "WhatsApp", "(sem link)", "+ "))]
            if ruins:
                erros.append(f"{nome} linha {rr}: destino sem endereço completo ({ruins[0][:40]})")
                break
    if len({r["ad_archive_id"] for r in anuncios}) != len(anuncios):
        erros.append("anúncio repetido")
    sem_grupo = [x["k"] for x in CR if x["g"] is None]
    if sem_grupo:
        erros.append(f"criativos sem grupo: {sem_grupo[:10]}")
    if not parcial and len(esc) != meta_roteiros:
        erros.append(f'{len(esc)} roteiros gravados para uma meta de {meta_roteiros}')
    if len(wb2['Roteiros Validados']._images) != len(esc):
        erros.append('quantidade de prints diferente da quantidade de roteiros')
    if wb2.active.title != 'Como ler' or len(wb2['Como ler']._charts) != bool(cobertura['total_grupos_video']):
        erros.append('painel inicial ou gráfico ausente')
    for rr, k in enumerate(esc, 2):
        link = wb2['Roteiros Validados'].cell(rr,12).hyperlink
        if not link or urlparse(link.target).scheme != 'file' or not Path(unquote(urlparse(link.target).path)).is_file():
            erros.append(f'atalho local inválido na linha {rr}')

    if a.csv:
        pasta_csv = arq[:-5] + "-csv"
        os.makedirs(pasta_csv, exist_ok=True)
        wb3 = load_workbook(arq)
        for n, nome in enumerate(wb3.sheetnames, 1):
            with open(os.path.join(pasta_csv, f"{n}-{nome.replace(' ', '-')}.csv"), "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.writer(fh)
                for row in wb3[nome].iter_rows():
                    w.writerow([(c.hyperlink.target if c.hyperlink and c.value in ("Abrir anúncio", "Assistir vídeo") else c.value) if c.value is not None else "" for c in row])
        print(f"CSV: {pasta_csv}")

    print(f"Planilha: {arq}")
    print(f"{len(anuncios)} anúncios ({ativos} ativos) | {len(CR)} criativos | {len(GR)} grupos | {len(esc)} roteiros")
    print("Top 5 grupos:")
    for n, y in enumerate(GR[:5], 1):
        print(f"  {n}. {y['nome']} | {y['nivel']} | {y['ativos']} ativos | {y['dias_ativo'] or y['maior']} dias | {y['n']} anúncios")
    if erros:
        print("CONFERÊNCIA COM PROBLEMAS:")
        for e in erros:
            print(" - " + e)
        sys.exit(1)
    if parcial:
        print(f'CONFERÊNCIA ESTRUTURAL OK. ENTREGA PARCIAL com {len(esc)} de {meta_roteiros} roteiros.')
    else:
        print("CONFERÊNCIA OK")
    C.gravar(p, 'ultima-planilha.json', {'arquivo': arq})


if __name__ == "__main__":
    main()
