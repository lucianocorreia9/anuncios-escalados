"""
transcrever.py: transcreve no próprio computador (faster-whisper), sem gastar consulta.

RODAR SEMPRE COM O PYTHON DO WHISPER:
  uv run --no-project --python 3.13 --with-requirements ../requirements-transcricao.txt python transcrever.py aberturas --apelido loja-exemplo
  uv run --no-project --python 3.13 --with-requirements ../requirements-transcricao.txt python transcrever.py roteiros  --apelido loja-exemplo --locais

  aberturas       os 16 s iniciais de cada vídeo -> aberturas.json
  roteiros        transcreve os MP4 do lote baixado, começando pelos 15 iniciais.

O que já foi transcrito é pulado. O arquivo é salvo a cada vídeo: se parar no meio, rodar de novo.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum as C  # noqa: E402
from cobertura import plano_lote


def nucleos_rapidos() -> int:
    """Nos Macs M1/M2/M3, usar só os núcleos de desempenho. Com todos (incluindo os econômicos)
    o Whisper fica de 5 a 20x mais lento: medido em 28/09/2026, 68 s contra 3,5 s por abertura."""
    import subprocess
    try:
        n = int(subprocess.run(["sysctl", "-n", "hw.perflevel0.physicalcpu"], capture_output=True, text=True).stdout.strip())
        if n > 0:
            return n
    except Exception:
        pass
    return min(4, os.cpu_count() or 4)


def modelo(nome: str, threads=None):
    from faster_whisper import WhisperModel
    return WhisperModel(nome, device="cpu", compute_type="int8", cpu_threads=threads or nucleos_rapidos(), num_workers=1)


def nome_para_chave(p: str) -> dict:
    cri = C.ler(p, "criativos.json", {}).get("criativos", {})
    return {k.replace("?", "x"): k for k in cri}


def aberturas(a) -> None:
    p = C.pasta(a.apelido)
    mapa = nome_para_chave(p)
    feitas = C.ler(p, "aberturas.json", {})
    # só os recortes de criativos atuais (medir.py pode ter renomeado algum numa nova rodada)
    arquivos = [f for f in sorted(glob.glob(os.path.join(p, "audios", "abertura_*.wav"))) if os.path.basename(f)[9:-4] in mapa]
    falta = [f for f in arquivos if mapa[os.path.basename(f)[9:-4]] not in feitas]
    C.log(f"Aberturas: {len(arquivos)} recortes, {len(falta)} para transcrever (modelo {a.modelo}).")
    if not falta:
        print(f"Aberturas transcritas: {len(feitas)}.")
        return
    m = modelo(a.modelo, a.threads)
    t0 = time.time()
    for n, f in enumerate(falta, 1):
        k = mapa.get(os.path.basename(f)[9:-4])
        if not k:
            continue
        segs, _ = m.transcribe(f, language="pt", beam_size=1, vad_filter=False)
        feitas[k] = " ".join(s.text.strip() for s in segs).strip()
        C.gravar(p, "aberturas.json", feitas)
        if n % 20 == 0:
            C.log(f"  {n}/{len(falta)} ({time.time() - t0:.0f}s)")
    vazias = [k for k, t in feitas.items() if len(t) < 15]
    print(f"Aberturas transcritas: {len(feitas)}. Texto ausente ou curto, revisar áudio: {len(vazias)} {vazias[:20]}")


def roteiros(a) -> None:
    p = C.pasta(a.apelido)
    cri = C.ler(p, "criativos.json")
    feitos = C.ler(p, "roteiros.json", {})
    midias = C.ler(p, "midias-locais.json", {})
    origens = C.ler(p, "roteiros-origens.json", {})
    segmentos = C.ler(p, "roteiros-segmentos.json", {})
    quantidade, baixados, ranking = plano_lote(p, a.ate)
    if a.locais and len(baixados) != quantidade and not a.permitir_parcial:
        raise SystemExit(f'Lote com {len(baixados)} de {quantidade} MP4. Conclua o download antes de transcrever.')
    selecionados = set(baixados)
    ordem = [k for k in ranking if k in selecionados]
    alvo = []
    for k in ordem:
        f = (midias.get(k) or {}).get("arquivo", "") if a.locais else os.path.join(p, "audios", "completo_" + k.replace("?", "x") + ".m4a")
        if a.locais:
            if not f or not os.path.isfile(f) or not midias[k].get("conferido"):
                raise SystemExit(f"MP4 local não conferido: {k}. Rode criativos_locais.py antes.")
            with open(f, "rb") as arquivo:
                digest = hashlib.file_digest(arquivo, "sha256").hexdigest()
            if digest != midias[k].get("sha256"):
                raise SystemExit(f"MP4 alterado desde a conferência: {k}")
        if (not a.locais and k in feitos) or os.path.isfile(f):
            alvo.append((k, f))
    falta = [(k, f) for k, f in alvo if k not in feitos or k in a.refazer_codigos or (a.locais and origens.get(k, {}).get("sha256") != midias[k]["sha256"])]
    C.log(f"Roteiros: {len(alvo)} escolhidos, {len(falta)} para transcrever.")
    if len(alvo) < quantidade:
        C.log(f"ATENÇÃO: só há mídia de {len(alvo)} dos {quantidade} vídeos selecionados; conferir os ganchos pendentes.")
    if falta:
        m = modelo(a.modelo, a.threads)
        for n, (k, f) in enumerate(falta, 1):
            t0 = time.time()
            fonte_audio = f
            canal_esquerdo = k in a.canal_esquerdo_codigos
            if canal_esquerdo:
                os.makedirs(os.path.join(p, 'audios'), exist_ok=True)
                fonte_audio = os.path.join(p, 'audios', 'local_esquerdo_' + k.replace('?', 'x') + '.wav')
                subprocess.run([C.ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-i', f, '-vn', '-af', 'pan=mono|c0=c0', '-ar', '16000', fonte_audio], capture_output=True, check=True, timeout=120)
            segs, info = m.transcribe(fonte_audio, language="pt", beam_size=5, vad_filter=k not in a.sem_vad_codigos, condition_on_previous_text=False, word_timestamps=canal_esquerdo)
            partes, ultimo_fim = [], None
            registros = []
            for s in segs:
                registros.append({"inicio": s.start, "fim": s.end, "texto": s.text.strip(), "no_speech_prob": s.no_speech_prob, "avg_logprob": s.avg_logprob, "palavras": [{"inicio":w.start,"fim":w.end,"texto":w.word} for w in (s.words or [])]})
                if ultimo_fim is not None and s.start - ultimo_fim > 1.2:
                    partes.append("\n\n")
                elif partes:
                    partes.append(" ")
                partes.append(s.text.strip())
                ultimo_fim = s.end
            feitos[k] = "".join(partes).strip()
            C.gravar(p, "roteiros.json", feitos)
            segmentos[k] = {"duracao_s": info.duration, "trechos": registros}
            C.gravar(p, "roteiros-segmentos.json", segmentos)
            if a.locais:
                origens[k] = {"arquivo": f, "sha256": midias[k]["sha256"], "modelo": a.modelo, "canal": "esquerdo" if canal_esquerdo else "padrão"}
                C.gravar(p, "roteiros-origens.json", origens)
            C.log(f"  {n}/{len(falta)} {k} ({info.duration:.0f}s de vídeo em {time.time() - t0:.0f}s)")
    print(f"Roteiros transcritos: {len([k for k, _ in alvo if k in feitos])} de {quantidade} selecionados.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("aberturas")
    x.add_argument("--apelido", required=True)
    x.add_argument("--modelo", default="small", help="small (padrão, ~3 a 4 s por abertura num M1) ou base (~1,5 s, erra muito nome próprio)")
    x.add_argument("--threads", type=int, help="limitar núcleos quando o processamento estiver lento")
    y = sub.add_parser("roteiros")
    y.add_argument("--apelido", required=True)
    y.add_argument("--ate", type=int, help="total acumulado do lote já baixado")
    y.add_argument("--modelo", default="small", help="small (padrão) ou base (3x mais rápido, mais erros)")
    y.add_argument("--threads", type=int, help="limitar núcleos quando o processamento estiver lento")
    y.add_argument("--locais", action="store_true", help="transcrever os MP4 conferidos em midias-locais.json")
    y.add_argument("--permitir-parcial", action="store_true", help="transcrever os MP4 disponíveis quando o lote estiver incompleto")
    y.add_argument("--sem-vad-codigos", nargs="*", default=[], help="códigos com fala cantada ou não reconhecida pelo detector de voz")
    y.add_argument("--refazer-codigos", nargs="*", default=[], help="reprocessar somente os códigos indicados")
    y.add_argument("--canal-esquerdo-codigos", nargs="*", default=[], help="usar só o canal esquerdo nos MP4 cujos canais se anulam na conversão para mono")
    a = ap.parse_args()
    {"aberturas": aberturas, "roteiros": roteiros}[a.cmd](a)


if __name__ == "__main__":
    main()
