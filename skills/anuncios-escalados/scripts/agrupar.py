"""
agrupar.py: prepara o material para o agente nomear os grupos de gancho e confere o resultado.

  preparar  junta aberturas quase iguais em pré-grupos (P1, P2...) e escreve para-agrupar.md,
            com cada criativo, seus números de escala e a abertura transcrita.
  conferir  lê o grupos.json escrito pelo agente e confere que todo criativo caiu em
            exatamente um grupo, que todo grupo tem nome e tipo, e mostra o resultado.

Formato do grupos.json (na pasta de trabalho do concorrente):
{
  "correcoes": [["constorias", "consultorias"]],      # erros de transcrição, trocados em tudo
  "grupos": [
    {"nome": "\"Tô com X mil na poupança, o que eu faço?\"", "tipo": "Pergunta do seguidor com valor",
     "itens": ["P1", "P7", "V33.10"]}
  ]
}
"itens" aceita pré-grupos (P..) e criativos (V.., I.., T..). Criativo citado pelo código vale
mais do que o pré-grupo onde ele estava: é assim que se tira um vídeo de um pré-grupo.

  python3 agrupar.py preparar --apelido loja-exemplo
  python3 agrupar.py conferir --apelido loja-exemplo
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import sys

import comum as C


def normal(t: str, n: int = 160) -> str:
    t = re.sub(r"[^\w\s]", " ", (t or "").lower())
    return " ".join(t.split())[:n]


def dados(p: str):
    T = C.momento_coleta(p)
    anuncios = {r["ad_archive_id"]: r for r in C.ler(p, "anuncios.json", [])}
    cri = C.ler(p, "criativos.json")["criativos"]
    ab = C.ler(p, "aberturas.json", {})
    res = {k: C.resumir([anuncios[i] for i in c["ids"]], T) for k, c in cri.items()}
    return T, anuncios, cri, ab, res


def texto_do_criativo(k, c, anuncios, ab) -> str:
    if c["tipo"] == "video":
        return ab.get(k, "")
    r = anuncios[c["exemplo"]]
    t = ((r["snapshot"].get("title") or "") + " | " + C.texto(r)).strip(" |")
    if c["formato"] == "Retirado pela Meta":
        t = "[conteúdo retirado pela Meta: sem vídeo nem imagem] " + t
    return t


def preparar(a) -> None:
    p = C.pasta(a.apelido)
    T, anuncios, cri, ab, res = dados(p)
    ordem = sorted(cri, key=lambda k: C.ordem_escala(res[k]))
    pre, reps = {}, []  # reps: (id, tipo, texto normalizado)
    for k in ordem:
        c = cri[k]
        t = normal(texto_do_criativo(k, c, anuncios, ab))
        tipo = "video" if c["tipo"] == "video" else "outro"
        alvo = None
        if len(t) >= 25:
            for pid, tp, rt in reps:
                if tp != tipo:
                    continue
                sm = difflib.SequenceMatcher(None, t, rt)
                if sm.real_quick_ratio() >= 0.62 and sm.quick_ratio() >= 0.62 and sm.ratio() >= 0.62:
                    alvo = pid
                    break
        if not alvo:
            alvo = f"P{len(pre) + 1}"
            pre[alvo] = []
            reps.append((alvo, tipo, t))
        pre[alvo].append(k)
    C.gravar(p, "pregrupos.json", pre)

    nome = (C.ler(p, "meta.json", {}) or {}).get("nome", a.apelido)
    L = [f"# Material para agrupar: {nome}", "",
         f"{len(cri)} criativos ({sum(1 for c in cri.values() if c['tipo'] == 'video')} vídeos) em {len(pre)} pré-grupos, "
         f"ordenados pela escala do melhor criativo de cada um. Regras em referencias/como-agrupar.md.",
         "Linha: código | duração | anúncios (ativos) | dias no ar do mais longo | nível | abertura ou texto", ""]
    for pid, ks in pre.items():
        tot = sum(res[k]["n"] for k in ks)
        atv = sum(res[k]["ativos"] for k in ks)
        L.append(f"## {pid}: {len(ks)} criativo(s), {tot} anúncios, {atv} ativos")
        for k in ks:
            c, r = cri[k], res[k]
            dur = f"{c['dur']:.0f}s" if c.get("dur") else c["formato"]
            txt = texto_do_criativo(k, c, anuncios, ab) or "(sem fala: olhar a capa em capas/" + k.replace("?", "x") + ".jpg)"
            L.append(f"- {k} | {dur} | {r['n']} ({r['ativos']}) | {r['maior']}d | {r['nivel'][:1]} | {txt[:260]}")
        L.append("")
    f = os.path.join(p, "para-agrupar.md")
    open(f, "w", encoding="utf-8").write("\n".join(L))
    sem_fala = sum(1 for k, c in cri.items() if c["tipo"] == "video" and len(ab.get(k, "")) < 15)
    print(f"{len(pre)} pré-grupos para {len(cri)} criativos. Vídeos sem fala: {sem_fala}.")
    print(f"Arquivo para o agente: {f}")


def expandir(p: str, grupos: dict) -> tuple:
    """Devolve ({criativo: índice do grupo}, [problemas])."""
    cri = C.ler(p, "criativos.json")["criativos"]
    pre = C.ler(p, "pregrupos.json", {})
    prob, via_pre, direto = [], {}, {}
    nomes = [g.get("nome", "").strip() for g in grupos.get("grupos", [])]
    for i, g in enumerate(grupos.get("grupos", [])):
        if not g.get("nome", "").strip() or not g.get("tipo", "").strip():
            prob.append(f"grupo {i + 1} sem nome ou sem tipo")
        for it in g.get("itens", []):
            if it in pre:
                for k in pre[it]:
                    if k in via_pre and via_pre[k] != i:
                        prob.append(f"pré-grupo {it} citado em dois grupos")
                    via_pre[k] = i
            elif it in cri:
                if it in direto and direto[it] != i:
                    prob.append(f"criativo {it} citado em dois grupos")
                direto[it] = i
            else:
                prob.append(f"código desconhecido: {it}")
    final = dict(via_pre)
    final.update(direto)
    usados = set(final.values())
    for i, g in enumerate(grupos.get("grupos", [])):
        if i not in usados:
            prob.append(f"grupo vazio (todos os itens foram citados em outro grupo): {g.get('nome')}")
    faltam = [k for k in cri if k not in final]
    if faltam:
        prob.append(f"{len(faltam)} criativos sem grupo: {faltam[:30]}")
    rep = {n for n in nomes if nomes.count(n) > 1}
    if rep:
        prob.append(f"nomes repetidos: {sorted(rep)}")
    return final, prob


def conferir(a) -> None:
    p = C.pasta(a.apelido)
    g = C.ler(p, "grupos.json")
    if not g:
        sys.exit("Sem grupos.json na pasta de trabalho.")
    final, prob = expandir(p, g)
    T, anuncios, cri, ab, res = dados(p)
    tot = {}
    for k, i in final.items():
        tot.setdefault(i, []).append(k)
    for i, gr in enumerate(g["grupos"]):
        ks = tot.get(i, [])
        n = sum(res[k]["n"] for k in ks)
        print(f"{i + 1:>3}. {gr.get('nome', '?')[:70]} | {gr.get('tipo', '?')} | {len(ks)} criativos, {n} anúncios")
        if not ks:
            prob.append(f"grupo vazio: {gr.get('nome')}")
    if prob:
        print("\nPROBLEMAS:")
        for x in prob:
            print(" - " + x)
        sys.exit(1)
    print(f"\nCONFERÊNCIA OK: {len(cri)} criativos em {len(g['grupos'])} grupos.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("preparar", "conferir"):
        s = sub.add_parser(n)
        s.add_argument("--apelido", required=True)
    a = ap.parse_args()
    {"preparar": preparar, "conferir": conferir}[a.cmd](a)


if __name__ == "__main__":
    main()
