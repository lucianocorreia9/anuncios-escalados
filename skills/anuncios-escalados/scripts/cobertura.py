"""Seleciona os vídeos do lote e confere os roteiros, sem consultas pagas."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import comum as C
from agrupar import expandir

LOTE_INICIAL = 15


def candidatos(p):
    cri = C.ler(p, 'criativos.json')['criativos']
    grupos = C.ler(p, 'grupos.json', {})
    grupo_de, erros = expandir(p, grupos)
    if erros:
        raise ValueError('Grupos pendentes: ' + '; '.join(erros))
    anuncios = {str(r['ad_archive_id']): r for r in C.ler(p, 'anuncios.json')}
    T = C.momento_coleta(p)
    por_grupo, resumos = {}, {}
    for k, c in cri.items():
        if c['tipo'] == 'video':
            por_grupo.setdefault(grupo_de[k], []).append(k)
            resumos[k] = C.resumir([anuncios[str(i)] for i in c['ids']], T)
    for ks in por_grupo.values():
        ks.sort(key=lambda k: C.ordem_roteiros(resumos[k]))
    ordem = sorted(por_grupo, key=lambda i: C.ordem_escala(C.resumir(
        [anuncios[str(aid)] for k in por_grupo[i] for aid in cri[k]['ids']], T)))
    return {i: por_grupo[i] for i in ordem}, grupo_de, resumos


def plano_lote(p, ate=None):
    """Retorna a meta, os códigos já selecionados e a fila global de candidatos."""
    _, _, resumos = candidatos(p)
    selecao = C.ler(p, 'selecionados.json', {})
    anteriores = list(dict.fromkeys(selecao.get('codigos', [])))
    desconhecidos = [k for k in anteriores if k not in resumos]
    if desconhecidos:
        raise ValueError('Seleção antiga exige conciliação, sem trocar códigos: ' + ', '.join(desconhecidos))
    minimo = max(LOTE_INICIAL, len(anteriores))
    meta = max(minimo, selecao.get('meta', minimo)) if ate is None else ate
    if meta < minimo:
        raise ValueError(f'O total deve ser de pelo menos {minimo} vídeos.')
    ranking = sorted(resumos, key=lambda k: C.ordem_roteiros(resumos[k]))
    return meta, anteriores, ranking


def selecionar(p, ate=None):
    meta, anteriores, ranking = plano_lote(p, ate)
    existentes = set(anteriores)
    novos = [k for k in ranking if k not in existentes]
    escolha = existentes.union(novos[:meta - len(existentes)])
    return [k for k in ranking if k in escolha]


def verificar(p, codigos=None):
    por_grupo, grupo_de, _ = candidatos(p)
    meta, anteriores, ranking = plano_lote(p)
    grupos = C.ler(p, 'grupos.json')['grupos']
    midias = C.ler(p, 'midias-locais.json', {})
    roteiros = C.ler(p, 'roteiros.json', {})
    origens = C.ler(p, 'roteiros-origens.json', {})
    if codigos is None:
        selecionados = set(anteriores)
        codigos = [k for k in ranking if k in selecionados]
    validos, falhas = [], {}
    for k in codigos:
        m = midias.get(k, {})
        arquivo, quadro = Path(m.get('arquivo') or ''), Path(m.get('print') or '')
        if k not in grupo_de or not m.get('conferido') or not arquivo.is_file() or not quadro.is_file():
            falhas[k] = 'MP4 ou print não conferido'
        elif not roteiros.get(k, '').strip():
            falhas[k] = 'transcrição pendente'
        else:
            digest = hashlib.sha256(arquivo.read_bytes()).hexdigest()
            if digest != m.get('sha256') or digest != origens.get(k, {}).get('sha256'):
                falhas[k] = 'transcrição ou manifesto não vinculado ao MP4 atual'
            else:
                validos.append(k)
    cobertos = {grupo_de[k] for k in validos}
    pendentes = [{'grupo': i, 'nome': grupos[i]['nome'], 'candidatos': ks}
                 for i, ks in por_grupo.items() if i not in cobertos]
    return {'total_grupos_video': len(por_grupo), 'grupos_cobertos': len(cobertos),
            'validos': validos, 'falhas': falhas, 'pendentes': pendentes,
            'meta': meta, 'disponiveis': len(ranking), 'faltam': max(0, meta - len(validos))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apelido', required=True)
    ap.add_argument('--ate', type=int)
    ap.add_argument('--conferir', action='store_true')
    a = ap.parse_args()
    p = C.pasta(a.apelido)
    if not a.conferir:
        escolha = selecionar(p, a.ate)
        print(f'Prévia do lote: {len(escolha)} vídeos em ordem de cópias.')
        print(', '.join(escolha))
        return
    resultado = verificar(p)
    C.gravar(p, 'cobertura.json', resultado)
    print(f"Cobertura: {resultado['grupos_cobertos']} de {resultado['total_grupos_video']} ganchos em vídeo.")
    if resultado['faltam'] or resultado['falhas']:
        for k, erro in resultado['falhas'].items():
            print(f'{k}: {erro}')
        raise SystemExit(f"Lote incompleto: {len(resultado['validos'])} de {resultado['meta']} roteiros validados.")
    print(f"CONFERÊNCIA OK: {len(resultado['validos'])} MP4 e roteiros vinculados.")


if __name__ == '__main__':
    main()
