"""
coletar.py: busca os anúncios de um concorrente na biblioteca da Meta pela ScrapeCreators.

Três etapas, sempre nesta ordem:

  sondar   1 consulta por alvo. Mostra quantos anúncios existem e quantas consultas a busca
           completa vai gastar. Guarda a 1ª página (não se paga duas vezes por ela).
  baixar   continua cada alvo de onde a sondagem parou, até o fim ou até o teto.
           SÓ RODAR DEPOIS DO OK DO USUÁRIO PARA O GASTO.
  filtrar  separa o que é do concorrente do que não é (homônimo, outro anunciante que usa a
           mesma palavra). Grátis, pode rodar quantas vezes quiser.

Alvos da sondagem (pode misturar vários):
  --dominio loja-exemplo.invalid     busca pelo nome do site (o jeito que pega todas as páginas)
  --termo "Curso Exemplo"   busca por frase exata (produto, bordão)
  --pagina 123456789          todos os anúncios de uma página, pelo número dela
  --nome-pagina "Loja Exemplo"        só lista páginas com esse nome e seus números (1 consulta)

Exemplos:
  python3 coletar.py sondar  --apelido loja-exemplo --nome "Loja Exemplo" --dominio loja-exemplo.invalid --termo "Curso Exemplo" --teto 2
  python3 coletar.py baixar  --apelido loja-exemplo --teto 120
  python3 coletar.py filtrar --apelido loja-exemplo --excluir-pagina "Página de Outro Anunciante"
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import Counter

import comum as C

SUFIXOS = {"com", "br", "org", "net", "io", "co", "app", "online", "site", "digital", "info", "me",
           "shop", "store", "pro", "biz", "tv", "club", "academy", "education", "blog", "ai", "gov", "edu"}


def rotulo(dominio: str) -> str:
    """loja-exemplo.invalid -> loja-exemplo (o nome do site sem subdomínio e sem .com.br)."""
    d = dominio.lower().split("//")[-1].split("/")[0].split("?")[0]
    partes = [x for x in d.split(".") if x and x != "www"]
    while len(partes) > 1 and partes[-1] in SUFIXOS:
        partes.pop()
    return partes[-1] if partes else d


def juntar(p: str, linhas: list, alvo_id: int, deslocamento: int) -> int:
    """Soma linhas novas ao bruto.json. Guarda a posição por impressões dentro de cada alvo."""
    bruto = {r["ad_archive_id"]: r for r in C.ler(p, "bruto.json", [])}
    novos = 0
    for i, r in enumerate(linhas):
        aid = r["ad_archive_id"]
        pos = deslocamento + i + 1
        if aid in bruto:
            ranks = bruto[aid].setdefault("_ranks", {})
            ranks.setdefault(str(alvo_id), pos)
            bruto[aid]["_rank"] = min(ranks.values())
            continue
        r["_ranks"] = {str(alvo_id): pos}
        r["_rank"] = pos
        r["_alvo"] = alvo_id
        bruto[aid] = r
        novos += 1
    C.gravar(p, "bruto.json", list(bruto.values()))
    return novos


def params_do_alvo(a: dict, cursor=None) -> tuple:
    if a["tipo"] == "pagina":
        pr = {"pageId": a["valor"], "country": "BR", "status": "ALL"}
        ep = "company/ads"
    else:
        pr = {"query": a["consulta"], "country": "BR", "status": "ALL", "sort_by": "total_impressions"}
        if a["tipo"] == "termo":
            pr["search_type"] = "keyword_exact_phrase"
        ep = "search/ads"
    if cursor:
        pr["cursor"] = cursor
    return ep, pr


def sondar(a) -> None:
    p = C.pasta(a.apelido)
    meta = C.ler(p, "meta.json", {}) or {"apelido": a.apelido, "criado": dt.datetime.now().isoformat(timespec="seconds"), "alvos": [], "dominios": []}
    if a.nome:
        meta["nome"] = a.nome
    meta.setdefault("nome", a.apelido)

    nomes = list(dict.fromkeys(a.nome_pagina or []))
    alvos = [("dominio", v) for v in a.dominio or []] + [("termo", v) for v in a.termo or []] + [("pagina", v) for v in a.pagina or []]
    vistos = {(x["tipo"], x["valor"]) for x in meta["alvos"]}
    novos_alvos = [alvo for alvo in dict.fromkeys(alvos) if alvo not in vistos]
    consultas = len(nomes) + len(novos_alvos)
    if consultas > a.teto:
        sys.exit(f"A sondagem exige {consultas} consultas. Ajuste os alvos ao teto de {a.teto}.")

    for nome in nomes:
        d = C.chamar(p, "search/companies", {"query": nome})
        linhas = d.get("searchResults") or d.get("results") or []
        print(f"\nPáginas com o nome \"{nome}\":")
        for x in linhas[:15]:
            print(f"  página {x.get('page_id')} | {x.get('name')} | curtidas {x.get('likes')} | ig {x.get('ig_username')} | {x.get('category') or ''}")

    for tipo, valor in novos_alvos:
        alvo = {"id": len(meta["alvos"]) + 1, "tipo": tipo, "valor": valor}
        if tipo == "dominio":
            alvo["consulta"] = rotulo(valor)
            if alvo["consulta"] not in meta["dominios"]:
                meta["dominios"].append(alvo["consulta"])
        elif tipo == "termo":
            alvo["consulta"] = valor
        ep, pr = params_do_alvo(alvo)
        d = C.chamar(p, ep, pr)
        linhas = d.get("searchResults") or d.get("results") or []
        total = d.get("searchResultsCount") or len(linhas)
        alvo.update(total=total, estimativa=C.estimar_consultas(total), cursor=d.get("cursor"),
                    esgotado=not d.get("cursor") or not linhas, baixados=len(linhas), consultas=1)
        juntar(p, linhas, alvo["id"], 0)
        meta["alvos"].append(alvo)
        C.gravar(p, "meta.json", meta)
        pags = Counter(f"{r['snapshot'].get('page_name')} [{r.get('page_id')}]" for r in linhas)
        sites = Counter(rotulo(r["snapshot"].get("caption") or C.destino(r) or "-") for r in linhas)
        ativos = sum(1 for r in linhas if r.get("is_active"))
        print(f"\n[{tipo}] {valor} (busca: {alvo.get('consulta', valor)})")
        print(f"  anúncios encontrados: {total} | nesta 1ª página: {len(linhas)} ({ativos} ativos)")
        print(f"  consultas para baixar tudo: ~{alvo['estimativa']} (1 já gasta)")
        print(f"  páginas que aparecem: {', '.join(f'{k} ({v})' for k, v in pags.most_common(8))}")
        print(f"  sites que aparecem: {', '.join(f'{k} ({v})' for k, v in sites.most_common(8))}")
    C.gravar(p, "meta.json", meta)
    gastas, resto = C.consultas_gastas(p)
    falta = sum(max(0, x["estimativa"] - x["consultas"]) for x in meta["alvos"] if not x.get("esgotado"))
    print(f"\nRESUMO {meta['nome']}: consultas gastas até agora {gastas} | faltam ~{falta} para baixar tudo | saldo da conta {resto}")


def baixar(a) -> None:
    p = C.pasta(a.apelido)
    meta = C.ler(p, "meta.json")
    if not meta:
        sys.exit("Rode a sondagem antes.")
    gasto = 0
    for alvo in meta["alvos"]:
        if a.alvo and alvo["id"] not in a.alvo:
            continue
        while not alvo.get("esgotado") and gasto < a.teto:
            ep, pr = params_do_alvo(alvo, alvo.get("cursor"))
            try:
                d = C.chamar(p, ep, pr)
            except C.ParadaNaAPI as e:
                C.gravar(p, "meta.json", meta)
                sys.exit(f"Parei sem insistir: {e}")
            gasto += 1
            alvo["consultas"] += 1
            linhas = d.get("searchResults") or d.get("results") or []
            juntar(p, linhas, alvo["id"], alvo["baixados"])
            alvo["baixados"] += len(linhas)
            anterior, alvo["cursor"] = alvo.get("cursor"), d.get("cursor")
            # Anúncio já visto em outro alvo não é sinal de fim: só para sem próxima página,
            # página vazia ou a mesma página de novo.
            if not alvo["cursor"] or not linhas or alvo["cursor"] == anterior or alvo["baixados"] >= alvo["total"]:
                alvo["esgotado"] = True
            C.gravar(p, "meta.json", meta)
            if alvo["consultas"] % 10 == 0:
                C.log(f"  [{alvo['tipo']}] {alvo['valor']}: {alvo['baixados']} de {alvo['total']} ({alvo['consultas']} consultas)")
        print(f"[{alvo['tipo']}] {alvo['valor']}: {alvo['baixados']} anúncios lidos de {alvo['total']} anunciados, {alvo['consultas']} consultas.")
        if gasto >= a.teto:
            print(f"Teto de {a.teto} consultas atingido. Uma nova rodada requer novo teto aprovado.")
            break
    meta["coleta"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    C.gravar(p, "meta.json", meta)
    gastas, resto = C.consultas_gastas(p)
    print(f"Consultas desta rodada: {gasto} | total deste concorrente: {gastas} | saldo da conta: {resto}")
    filtrar(a)


def filtrar(a) -> None:
    p = C.pasta(a.apelido)
    meta = C.ler(p, "meta.json")
    bruto = C.ler(p, "bruto.json", [])
    if getattr(a, "excluir_pagina", None):
        meta["paginas_excluir"] = sorted(set(meta.get("paginas_excluir", [])) | set(a.excluir_pagina))
    if getattr(a, "incluir_pagina", None):
        meta["paginas_incluir"] = sorted(set(meta.get("paginas_incluir", [])) | set(a.incluir_pagina))
    doms = meta.get("dominios", [])
    excluir = set(meta.get("paginas_excluir", []))
    incluir = set(meta.get("paginas_incluir", []))
    paginas_alvo = {x["valor"] for x in meta["alvos"] if x["tipo"] == "pagina"}

    def do_site(r):
        s = r["snapshot"]
        alvo = ((s.get("caption") or "") + " " + C.destino(r)).lower()
        return any(d in alvo for d in doms)

    # Páginas do concorrente: as que têm pelo menos um anúncio levando ao site dele.
    paginas_dele = {r.get("page_id") for r in bruto if do_site(r) and r["snapshot"].get("page_name") not in excluir}
    paginas_dele |= paginas_alvo
    ficam, fora = [], []
    for r in bruto:
        nome = r["snapshot"].get("page_name")
        if nome in excluir:
            motivo = "página excluída à mão"
        elif nome in incluir or r.get("page_id") in paginas_dele:
            motivo = None
        elif do_site(r):
            motivo = None
        else:
            motivo = "outro anunciante (não leva ao site e não é página do concorrente)"
        if motivo:
            r["_motivo"] = motivo
            fora.append(r)
        else:
            ficam.append(r)
    C.gravar(p, "anuncios.json", ficam)
    C.gravar(p, "fora.json", fora)
    C.gravar(p, "meta.json", meta)
    ativos = sum(1 for r in ficam if r.get("is_active"))
    print(f"\nFICAM {len(ficam)} anúncios ({ativos} ativos). SEPARADOS {len(fora)}.")
    pags = Counter(r["snapshot"].get("page_name") for r in ficam)
    print("Páginas que ficaram: " + "; ".join(f"{k} ({v})" for k, v in pags.most_common(20)))
    if fora:
        pf = Counter((r["snapshot"].get("page_name"), r["_motivo"]) for r in fora)
        print("Separados (conferir se nenhum é do concorrente):")
        for (nome, motivo), n in pf.most_common(25):
            ex = next(r for r in fora if r["snapshot"].get("page_name") == nome)
            print(f"  {nome} ({n}) | {motivo} | ex.: {C.texto(ex)[:110]} | {C.destino(ex)[:70]}")


def teto_positivo(valor: str) -> int:
    teto = int(valor)
    if teto < 1:
        raise argparse.ArgumentTypeError("Informe um teto de pelo menos uma consulta.")
    return teto


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sondar")
    s.add_argument("--apelido", required=True)
    s.add_argument("--nome")
    s.add_argument("--dominio", action="append")
    s.add_argument("--termo", action="append")
    s.add_argument("--pagina", action="append")
    s.add_argument("--nome-pagina", action="append")
    s.add_argument("--teto", type=teto_positivo, required=True, help="máximo de consultas aprovado para a sondagem")
    b = sub.add_parser("baixar")
    b.add_argument("--apelido", required=True)
    b.add_argument("--teto", type=teto_positivo, required=True, help="máximo de consultas aprovado para esta rodada")
    b.add_argument("--alvo", type=int, action="append", help="só estes alvos (número mostrado na sondagem)")
    f = sub.add_parser("filtrar")
    f.add_argument("--apelido", required=True)
    f.add_argument("--excluir-pagina", action="append")
    f.add_argument("--incluir-pagina", action="append")
    a = ap.parse_args()
    try:
        {"sondar": sondar, "baixar": baixar, "filtrar": filtrar}[a.cmd](a)
    except C.ParadaNaAPI as e:
        sys.exit(f"Parei sem repetir: {e}")


if __name__ == "__main__":
    main()
