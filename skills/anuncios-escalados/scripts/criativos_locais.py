"""Baixa e confere os MP4 selecionados, um por vez, e captura os prints locais."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import urllib.error
import urllib.request

import comum as C
from cobertura import LOTE_INICIAL, candidatos, plano_lote


def nome_pasta(nome):
    plain = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', plain).strip('_')


def conferir(arquivo):
    result = subprocess.run([C.ffmpeg(), '-hide_banner', '-i', str(arquivo)], capture_output=True, text=True, timeout=45)
    assert 'Video:' in result.stderr, 'Arquivo sem faixa de vídeo'
    assert re.search(r'Input #0, (?:mov,mp4|.*mp4)', result.stderr), 'Contêiner não reconhecido como MP4'
    duration = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', result.stderr)
    assert duration, 'Duração não reconhecida'
    h, m, s = map(float, duration.groups())
    decode = subprocess.run([C.ffmpeg(), '-hide_banner', '-v', 'error', '-i', str(arquivo), '-f', 'null', '-'], capture_output=True, text=True, timeout=600)
    assert decode.returncode == 0 and not decode.stderr.strip(), 'Erro na decodificação integral'
    return {'duracao_s': h * 3600 + m * 60 + s, 'audio': 'Audio:' in result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apelido', required=True)
    parser.add_argument('--pasta-concorrente', required=True)
    parser.add_argument('--ate', type=int, help='total acumulado autorizado após o primeiro lote de 15')
    args = parser.parse_args()
    cache = C.pasta(args.apelido)
    data = C.ler(cache, 'criativos.json')
    meta, previous, ranking = plano_lote(cache, args.ate)
    entregue = C.ler(cache, 'ultima-planilha.json', {}).get('arquivo')
    if meta > LOTE_INICIAL and meta > len(previous):
        if len(previous) < LOTE_INICIAL or not entregue or not Path(entregue).is_file():
            raise SystemExit('Entregue a primeira planilha com 15 roteiros antes de baixar extras.')
    existing = set(previous)
    selected = previous + [k for k in ranking if k not in existing]
    _, group_of, _ = candidatos(cache)
    groups = C.ler(cache, 'grupos.json')
    ads = {str(ad['ad_archive_id']): ad for ad in C.ler(cache, 'anuncios.json')}
    folder = Path(args.pasta_concorrente).expanduser().resolve()
    target = folder / 'criativos'
    target.mkdir(parents=True, exist_ok=True)
    prints = Path(cache) / 'prints-validados'
    prints.mkdir(exist_ok=True)
    manifest = C.ler(cache, 'midias-locais.json', {})
    failures = []
    final = existing.copy()
    C.gravar(cache, 'selecionados.json', {'codigos': previous, 'meta': meta})
    for code in selected:
        if code not in existing and len(final) >= meta:
            break
        position = previous.index(code) + 1 if code in existing else len(final) + 1
        creative = data['criativos'][code]
        title = groups['grupos'][group_of[code]]['nome']
        title = nome_pasta(title).replace('_', '-')[:85]
        matches = list(target.glob(f'*-{code}-*.mp4'))
        assert len(matches) <= 1, f'Mais de um arquivo local para {code}'
        file = matches[0] if matches else target / f'{position:02d}-{code}-{title}.mp4'
        partial = file.with_suffix('.mp4.part')
        novo = not file.exists()
        try:
            if not file.exists():
                urls = list(dict.fromkeys(C.midia(ads[str(aid)])['video'] for aid in creative['ids']))
                last_error = None
                for url in filter(None, urls[:5]):
                    try:
                        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(request, timeout=60) as response:
                            assert response.status == 200
                            kind = response.headers.get('Content-Type', '')
                            assert 'video' in kind or 'octet-stream' in kind
                            size = int(response.headers.get('Content-Length', '0'))
                            with partial.open('xb') as stream:
                                while True:
                                    block = response.read(1024 * 1024)
                                    if not block:
                                        break
                                    stream.write(block)
                        assert partial.stat().st_size > 10000
                        assert not size or partial.stat().st_size == size
                        details = conferir(partial)
                        partial.rename(file)
                        break
                    except Exception as error:
                        partial.unlink(missing_ok=True)
                        last_error = f'HTTP {error.code}' if isinstance(error, urllib.error.HTTPError) else type(error).__name__
                if not file.exists():
                    raise RuntimeError(last_error or 'Sem endereço de vídeo')
            else:
                details = conferir(file)
            expected = creative.get('dur')
            assert not expected or abs(details['duracao_s'] - expected) < .25, 'Duração diverge do criativo'
            frame = prints / f'{code}.png'
            if not frame.is_file():
                subprocess.run([C.ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(min(2, details['duracao_s']/2)), '-i', str(file), '-frames:v', '1', '-vf', 'scale=640:-2', str(frame)], capture_output=True, check=True, timeout=60)
            manifest[code] = {'codigo': code, 'posicao': position, 'arquivo': str(file), 'print': str(frame), 'bytes': file.stat().st_size, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'conferido': True, **details}
            C.gravar(cache, 'midias-locais.json', manifest)
            final.add(code)
            C.gravar(cache, 'selecionados.json', {'codigos': [k for k in ranking if k in final], 'meta': meta})
            print(f'{position:02d}/{meta} OK: {code}, {details["duracao_s"]:.2f}s, {file.stat().st_size/1048576:.1f} MB', flush=True)
        except Exception as error:
            partial.unlink(missing_ok=True)
            if novo:
                file.unlink(missing_ok=True)
            failures.append(code)
            print(f'{position:02d}/{meta} FALHOU: {code} ({type(error).__name__})', flush=True)
    if len(final) < meta or any(k in existing for k in failures):
        raise SystemExit(f'Lote incompleto: {len(final)} de {meta} selecionados. Confira as falhas de download acima.')
    if failures:
        print('Candidatos indisponíveis substituídos pelos próximos do ranking: ' + ', '.join(failures))
    print(f'CONFERÊNCIA OK: {len(final)} MP4 completos.')


if __name__ == '__main__':
    main()
