"""Quadros de momentos distintos para auxiliar a conferência visual dos criativos."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import comum as C


def quadros(url, duracao, pasta):
    if not url or not duracao:
        return []
    source = urlsplit(url)
    chave = hashlib.sha256((source.netloc + source.path).encode()).hexdigest()[:20]
    destino = Path(pasta) / chave
    destino.mkdir(parents=True, exist_ok=True)
    resultado = []
    tempos = (min(2, duracao*.15), min(8, duracao*.5), min(14, duracao*.85), duracao*.5, duracao*.85)
    for n, tempo in enumerate(tempos, 1):
        arquivo = destino / f'{n}.jpg'
        try:
            if not arquivo.is_file():
                subprocess.run([C.ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(tempo),
                                '-i', str(url), '-frames:v', '1', '-vf', 'scale=640:-2', str(arquivo)],
                               capture_output=True, check=True, timeout=90)
            raw = subprocess.run([C.ffmpeg(), '-hide_banner', '-loglevel', 'error', '-i', str(arquivo),
                                  '-vf', 'scale=17:16,format=gray', '-frames:v', '1', '-f', 'rawvideo', '-'],
                                 capture_output=True, check=True, timeout=30).stdout
            if len(raw) != 272:
                continue
            assinatura = ''.join('1' if raw[y*17+x] > raw[y*17+x+1] else '0'
                                 for y in range(16) for x in range(16))
            resultado.append({'tempo': round(tempo, 3), 'arquivo': str(arquivo), 'assinatura': assinatura})
        except (subprocess.SubprocessError, OSError):
            continue
    return resultado


def mesmos_quadros(a, b):
    """Conferir abertura, meio e final; ausência de evidência não junta vídeos."""
    if len(a or []) != 5 or len(b or []) != 5:
        return False
    # Quadros uniformes ou sem mudança são indício insuficiente para unir peças.
    if len({q.get('assinatura') for q in a}) < 2 or len({q.get('assinatura') for q in b}) < 2:
        return False
    for x, y in zip(a, b):
        sx, sy = x.get('assinatura', ''), y.get('assinatura', '')
        if len(sx) != 256 or len(sy) != 256 or sum(p != q for p, q in zip(sx, sy)) > 14:
            return False
    return True
