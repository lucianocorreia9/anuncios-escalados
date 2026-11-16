"""
medir.py: descobre quais anúncios usam o mesmo vídeo e prepara o áudio para transcrever.

Grátis (não usa a ScrapeCreators), mas depende dos links de vídeo da coleta, que a Meta
invalida em uns 4 a 5 dias. Rodar logo depois do coletar.py baixar.

O que faz, nesta ordem:
  1. lê a duração exata de cada vídeo só pelo cabeçalho do link (sem baixar) e a "impressão
     digital" da capa (uma miniatura de 8x8 pontos);
  2. compara cinco quadros da abertura, meio e final; duração/capa isoladas não bastam;
     imagem igual -> um criativo; anúncio sem mídia -> criativo pelo texto;
  3. baixa uma capa pequena de cada criativo (capas/), para o agente olhar quando precisar;
  4. recorta os 16 segundos iniciais de cada vídeo (audios/abertura_*.wav);

Pode rodar de novo: o que já foi medido ou baixado é pulado.

  python3 medir.py --apelido loja-exemplo
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import os
import re
import subprocess
import threading
from collections import Counter
from urllib.parse import urlsplit

import comum as C
from visual import quadros, mesmos_quadros

FF = C.ffmpeg()


def ahash(url: str):
    if not url:
        return None
    try:
        out = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i", url, "-vf", "scale=8:8,format=gray",
                              "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True, timeout=60).stdout
    except Exception:
        return None
    if len(out) < 64:
        return None
    px = list(out[:64])
    m = sum(px) / 64
    return "".join("1" if x > m else "0" for x in px)


def duracao(url: str):
    try:
        e = subprocess.run([FF, "-hide_banner", "-i", url], capture_output=True, text=True, timeout=60).stderr
    except Exception:
        return None
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", e)
    return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2) if m else None


def distancia(a, b) -> int:
    return sum(x != y for x, y in zip(a, b)) if a and b else 99


def validade(url: str):
    m = re.search(r"[?&]oe=([0-9A-Fa-f]+)", url or "")
    return dt.datetime.fromtimestamp(int(m.group(1), 16)) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apelido", required=True)
    a = ap.parse_args()
    p = C.pasta(a.apelido)
    T = C.momento_coleta(p)
    anuncios = C.ler(p, "anuncios.json")
    if not anuncios:
        raise SystemExit("Sem anuncios.json: rode coletar.py baixar (e filtrar) antes.")
    por_id = {r["ad_archive_id"]: r for r in anuncios}

    validades = [v for v in (validade(C.midia(r)["video"]) for r in anuncios) if v]
    if validades:
        menor = min(validades)
        C.log(f"Links de vídeo valem até {menor:%d/%m/%Y %H:%M}.")
        if menor < dt.datetime.now():
            C.log("ATENÇÃO: parte dos links já expirou. Os vídeos desses anúncios vão falhar; seria preciso coletar de novo (gasta consulta).")

    # 1. medidas (duração e capa) --------------------------------------------------
    medidas = C.ler(p, "medidas.json", {})
    # O mesmo arquivo costuma aparecer em muitas cópias com parâmetros de acesso diferentes.
    locks, sources = {}, {}
    guard = threading.Lock()

    def medir(r):
        m = C.midia(r)
        res = {"formato": m["formato"]}
        if m["video"]:
            u = urlsplit(m['video'])
            key = u.netloc + u.path
            with guard:
                lock = locks.setdefault(key, threading.Lock())
            with lock:
                if key not in sources:
                    d = duracao(m['video'])
                    sources[key] = {'dur': d, 'frames': quadros(m['video'], d, os.path.join(p, 'frames'))}
                res.update(sources[key])
        res["capa"] = ahash(m["capa"])
        return r["ad_archive_id"], res

    falta = [r for r in anuncios if r["ad_archive_id"] not in medidas or (C.midia(r)["video"] and
             (not medidas[r["ad_archive_id"]].get("dur") or len(medidas[r["ad_archive_id"]].get('frames', [])) != 5))]
    C.log(f"Medindo {len(falta)} anúncios...")
    with cf.ThreadPoolExecutor(8) as ex:
        for aid, res in ex.map(medir, falta):
            medidas[aid] = res
    C.gravar(p, "medidas.json", medidas)

    # 2. criativos -----------------------------------------------------------------
    ordem = sorted(anuncios, key=lambda r: r.get("_rank", 10**9))
    videos, imagens, textos = {}, [], {}
    chave_de = {}
    for r in ordem:
        aid = r["ad_archive_id"]
        md = medidas[aid]
        m = C.midia(r)
        if m["video"]:
            d = md.get("dur")
            balde = videos.setdefault(d if d else "?", [])
            origem = urlsplit(m["video"])
            fonte = (origem.netloc, origem.path)
            for g in balde:
                if fonte in g['fontes'] or mesmos_quadros(g.get('frames'), md.get('frames')):
                    g["ids"].append(aid)
                    g["fontes"].add(fonte)
                    break
            else:
                balde.append({"capa": md.get("capa"), "frames": md.get('frames', []), "ids": [aid], "fontes": {fonte}})
        elif md.get("capa"):
            for g in imagens:
                if distancia(g["capa"], md["capa"]) <= 5:
                    g["ids"].append(aid)
                    break
            else:
                imagens.append({"capa": md["capa"], "ids": [aid]})
        else:
            t = (r["snapshot"].get("title") or "") + " " + C.texto(r)
            textos.setdefault(" ".join(t.lower().split())[:200], []).append(aid)

    criativos = {}
    for d, baldes in videos.items():
        for i, g in enumerate(baldes):
            k = (f"V{d:.2f}" if d != "?" else "V?") + ("" if i == 0 else chr(ord("a") + i - 1) if i <= 26 else f"-{i}")
            criativos[k] = {"tipo": "video", "dur": d if d != "?" else None, "ids": g["ids"]}
    for i, g in enumerate(imagens, 1):
        criativos[f"I{i}"] = {"tipo": "imagem", "dur": None, "ids": g["ids"]}
    for i, ids in enumerate(textos.values(), 1):
        criativos[f"T{i}"] = {"tipo": "texto", "dur": None, "ids": ids}
    # Fusões entre cortes/recompressões exigem revisão dos prints e registro explícito.
    for decisao in C.ler(p, 'revisao-visual.json', {}).get('mesclar', []):
        manter, repetido = decisao['manter'], decisao['duplicado']
        if not decisao.get('evidencia') or manter not in criativos or repetido not in criativos or manter == repetido:
            raise SystemExit('Revisão visual inválida: conferir códigos e evidência antes de medir novamente.')
        if criativos[manter]['tipo'] != 'video' or criativos[repetido]['tipo'] != 'video':
            raise SystemExit('A fusão visual só pode juntar vídeos.')
        criativos[manter]['ids'] = list(dict.fromkeys(criativos[manter]['ids'] + criativos.pop(repetido)['ids']))
    for k, c in criativos.items():
        rs = [por_id[i] for i in c["ids"]]
        melhor = min(rs, key=lambda r: r.get("_rank", 10**9))
        c["exemplo"] = melhor["ad_archive_id"]
        c["formato"] = Counter(C.midia(r)["formato"] for r in rs).most_common(1)[0][0]
        for i in c["ids"]:
            chave_de[i] = k
    for aid in por_id:
        medidas[aid]["criativo"] = chave_de[aid]
    C.gravar(p, "medidas.json", medidas)

    # ordem dos candidatos a roteiro (só vídeos)
    res = {k: C.resumir([por_id[i] for i in c["ids"]], T) for k, c in criativos.items() if c["tipo"] == "video"}
    ordem_rot = sorted(res, key=lambda k: C.ordem_roteiros(res[k]))
    C.gravar(p, "criativos.json", {"criativos": criativos, "ordem_roteiros": ordem_rot})

    # 3-4. capas e aberturas -------------------------------------------------------
    for sub in ("capas", "audios"):
        os.makedirs(os.path.join(p, sub), exist_ok=True)

    def urls_video(k):
        ids = sorted(criativos[k]["ids"], key=lambda i: por_id[i].get("_rank", 10**9))
        return [u for u in (C.midia(por_id[i])["video"] for i in ids[:4]) if u]

    def baixar_capa(k):
        out = os.path.join(p, "capas", k.replace("?", "x") + ".jpg")
        if os.path.exists(out):
            return True
        for i in criativos[k]["ids"][:3]:
            u = C.midia(por_id[i])["capa"]
            if u:
                subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", u, "-vf", "scale=360:-2", "-frames:v", "1", out],
                               capture_output=True, timeout=60)
                if os.path.exists(out) and os.path.getsize(out) > 500:
                    return True
        return False

    def recortar(k):
        nome = "abertura_" + k.replace("?", "x") + ".wav"
        out = os.path.join(p, "audios", nome)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return True
        for u in urls_video(k):
            cmd = [FF, "-hide_banner", "-loglevel", "error", "-y", "-t", "16", "-i", u,
                   "-vn", "-ac", "1", "-ar", "16000", out]
            try:
                subprocess.run(cmd, capture_output=True, timeout=90)
            except Exception:
                continue
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                return True
        return False

    vids = [k for k, c in criativos.items() if c["tipo"] == "video"]
    with cf.ThreadPoolExecutor(24) as ex:
        capas_ok = sum(ex.map(baixar_capa, list(criativos)))
        abert_ok = list(ex.map(recortar, vids))
    falhas_ab = [k for k, ok in zip(vids, abert_ok) if not ok]

    fmt = Counter(C.midia(r)["formato"] for r in anuncios)
    print(f"Anúncios: {len(anuncios)} ({', '.join(f'{k} {v}' for k, v in fmt.most_common())})")
    print(f"Criativos diferentes: {len(vids)} vídeos, {len(imagens)} imagens, {len(textos)} só texto")
    sem_frames = sum(1 for aid, md in medidas.items() if aid in por_id and C.midia(por_id[aid])['video'] and len(md.get('frames', [])) != 5)
    if sem_frames:
        print(f'PENDÊNCIA VISUAL: {sem_frames} anúncios sem cinco quadros; não foram unidos por capa/duração.')
    sem_dur = sum(1 for aid, m in medidas.items() if aid in por_id and C.midia(por_id[aid])["video"] and not m.get("dur"))
    if sem_dur:
        print(f"ATENÇÃO: {sem_dur} anúncios de vídeo sem duração lida (link falhou); ficaram no criativo V?.")
    print(f"Capas baixadas: {capas_ok} de {len(criativos)}")
    print(f"Aberturas recortadas: {len(vids) - len(falhas_ab)} de {len(vids)}" + (f" | falharam: {falhas_ab[:15]}" if falhas_ab else ""))
    print(f"Pasta de trabalho: {p}")


if __name__ == "__main__":
    main()
