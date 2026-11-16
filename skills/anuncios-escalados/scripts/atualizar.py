"""Edita o XLSX existente no mesmo caminho; preserva as outras abas e conteúdos."""
from __future__ import annotations

import argparse
from copy import copy
import csv
import hashlib
import os
from pathlib import Path
import tempfile
import zipfile

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage

import comum as C
from cobertura import candidatos, verificar
from painel import aplicar


def estado(ws):
    """Conteúdo, vínculos e aparência das células que não devem ser alteradas."""
    return ([(c.coordinate, c.value, str(c._style), c.number_format,
              c.hyperlink.target if c.hyperlink else None, c.comment.text if c.comment else None)
             for row in ws for c in row if c.value is not None or c.has_style],
            str(ws.auto_filter), str(ws.freeze_panes), str(ws.merged_cells),
            [(k, str(v)) for k, v in ws.row_dimensions.items()],
            [(k, str(v)) for k, v in ws.column_dimensions.items()], len(ws._images), len(ws._charts))


def imagens(arquivo):
    with zipfile.ZipFile(arquivo) as z:
        return sorted(hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('xl/media/'))


def linhas_por_video(ws):
    return {linha[3].value: linha for linha in ws.iter_rows(min_row=2) if linha[3].value is not None}


def estado_dos_roteiros(ws):
    return {pos: [(c.value, str(c._style), c.number_format,
                   (c.hyperlink.target, c.hyperlink.location) if c.hyperlink else None,
                   c.comment.text if c.comment else None)
                  for c in linha[1:] if c.value is not None or c.has_style or c.hyperlink or c.comment]
            for pos, linha in linhas_por_video(ws).items()}


def ordenar_roteiros(ws, videos, p):
    _, _, resumos = candidatos(p)
    linhas = linhas_por_video(ws)
    ordem = sorted(linhas, key=lambda pos: C.ordem_roteiros(resumos[videos[pos]]))
    if ordem == list(linhas):
        return
    dados = {pos: [(c.value, c.data_type, copy(c._style), copy(c.hyperlink), copy(c.comment)) for c in linha]
             for pos, linha in linhas.items()}
    origem = {linha[0].row: pos for pos, linha in linhas.items()}
    destino = {pos: row for row, pos in enumerate(ordem, 2)}
    alturas = {pos: ws.row_dimensions[row].height for row, pos in origem.items()}
    for pos, row in destino.items():
        for col, (value, tipo, estilo, link, comentario) in enumerate(dados[pos], 1):
            cell = ws.cell(row, col)
            cell.value = row - 1 if col == 1 else value
            cell.data_type = tipo
            cell._style = estilo
            cell.hyperlink = link
            cell.comment = comentario
        ws.row_dimensions[row].height = alturas[pos]
    for imagem in ws._images:
        if isinstance(imagem.anchor, str):
            c = ws[imagem.anchor]
            imagem.anchor = ws.cell(destino[origem[c.row]], c.column).coordinate
        elif imagem.anchor._from.row + 1 in origem:
            old_row = imagem.anchor._from.row + 1
            new_row = destino[origem[old_row]]
            imagem.anchor._from.row = new_row - 1
            if hasattr(imagem.anchor, 'to'):
                imagem.anchor.to.row += new_row - old_row


def acrescentar(wb, p, permitir_parcial=False):
    resultado = verificar(p)
    if (resultado['faltam'] or resultado['falhas']) and not permitir_parcial:
        raise ValueError('Lote de roteiros incompleto. Rodar cobertura.py --conferir antes de atualizar.')
    media = C.ler(p, 'midias-locais.json', {})
    rot = C.ler(p, 'roteiros.json', {})
    correcoes = C.ler(p, 'grupos.json', {}).get('correcoes', [])
    videos = {r[20]: list(r) for r in wb['Todos os Vídeos'].iter_rows(min_row=2, values_only=True) if r[20]}
    por_pos = {r[0]: k for k, r in videos.items()}
    ws = wb['Roteiros Validados']
    presentes = set()
    for rr in range(2, ws.max_row+1):
        if ws.cell(rr, 4).value not in por_pos:
            raise ValueError('Posição de vídeo sem código correspondente; conciliar sem trocar linhas existentes.')
        presentes.add(por_pos[ws.cell(rr, 4).value])
    additions = [k for k in resultado['validos'] if k not in presentes]
    if any(k not in videos for k in additions):
        raise ValueError('Há novos criativos fora de Todos os Vídeos. Atualizar pontualmente as tabelas de dados, preservando códigos e linhas, antes de acrescentar roteiros.')
    tipos = {r[1]: r[2] for r in wb['Grupos'].iter_rows(min_row=2, values_only=True) if r[1]}
    for k in additions:
        x, m = videos[k], media[k]
        texto = rot[k]
        for antes, depois in correcoes:
            texto = texto.replace(antes, depois)
        if len(texto) > 32000:
            raise ValueError('Transcrição excede uma célula; distribuir em continuação sem cortar o texto: ' + k)
        rr = ws.max_row+1
        values = [rr-1, x[1], tipos[x[1]], x[0], x[2], 'Ativo' if x[4] else 'Pausado',
                  x[6], x[4], x[8], x[11], x[14], 'Assistir vídeo', texto, None]
        for col, value in enumerate(values, 1):
            cell = ws.cell(rr, col, value)
            if rr > 2:
                cell._style = copy(ws.cell(rr-1, col)._style)
        ws.cell(rr, 12).hyperlink = Path(m['arquivo']).resolve().as_uri()
        image = XLImage(m['print'])
        scale = min(270/image.width, 460/image.height)
        image.width, image.height = image.width*scale, image.height*scale
        ws.add_image(image, f'N{rr}')
        ws.row_dimensions[rr].height = 360
    if additions:
        ws.auto_filter.ref = ws.dimensions
        ordenar_roteiros(ws, por_pos, p)
    return len(additions)


def atualizar(arquivo, p, painel=False, adicionar=False, permitir_parcial=False):
    arquivo = Path(arquivo).expanduser().resolve(strict=True)
    wb = load_workbook(arquivo)
    painel = painel or adicionar
    afetadas = ({'Como ler'} if painel else set()) | ({'Roteiros Validados'} if adicionar else set())
    antes = {ws.title: estado(ws) for ws in wb if ws.title not in afetadas}
    anteriores = estado_dos_roteiros(wb['Roteiros Validados']) if adicionar else {}
    imgs = imagens(arquivo)
    count = acrescentar(wb, p, permitir_parcial) if adicionar else 0
    if painel:
        aplicar(wb, p)
    with tempfile.TemporaryDirectory(prefix='hapogeu-xlsx-') as tmp:
        candidato = Path(tmp)/arquivo.name
        wb.save(candidato)
        conferido = load_workbook(candidato)
        for nome, expected in antes.items():
            if estado(conferido[nome]) != expected:
                raise ValueError('Alteração inesperada em ' + nome + '; arquivo original preservado.')
        if adicionar:
            atual = estado_dos_roteiros(conferido['Roteiros Validados'])
            if any(atual.get(pos) != original for pos, original in anteriores.items()):
                raise ValueError('Conteúdo dos roteiros anteriores mudou; arquivo original preservado.')
        depois = imagens(candidato)
        if any(depois.count(h) < imgs.count(h) for h in set(imgs)):
            raise ValueError('Uma imagem anterior mudou ou sumiu; arquivo original preservado.')
        tem_video = any(isinstance(conferido['Todos os Vídeos'].cell(rr, 12).value, (int, float))
                        for rr in range(2, conferido['Todos os Vídeos'].max_row+1))
        if painel and (conferido.active.title != 'Como ler' or len(conferido['Como ler']._charts) != bool(tem_video)):
            raise ValueError('Painel não conferido; arquivo original preservado.')
        # O temporário fica fora da entrega; substituição atômica no mesmo nome.
        mode = arquivo.stat().st_mode
        fd, stage_name = tempfile.mkstemp(prefix='.'+arquivo.name+'-', suffix='.part', dir=arquivo.parent)
        os.close(fd)
        staged = Path(stage_name)
        try:
            with candidato.open('rb') as source, staged.open('wb') as target:
                while True:
                    block = source.read(1024*1024)
                    if not block:
                        break
                    target.write(block)
            os.chmod(staged, mode)
            os.replace(staged, arquivo)
        finally:
            staged.unlink(missing_ok=True)
    C.gravar(p, 'ultima-planilha.json', {'arquivo': str(arquivo)})
    return count


def exportar_csv(arquivo):
    wb = load_workbook(arquivo)
    pasta = Path(arquivo).with_suffix('')
    pasta = pasta.with_name(pasta.name+'-csv')
    pasta.mkdir(exist_ok=True)
    for n, ws in enumerate(wb, 1):
        with (pasta/f"{n}-{ws.title.replace(' ', '-')}.csv").open('w', encoding='utf-8-sig', newline='') as out:
            writer = csv.writer(out)
            for row in ws:
                writer.writerow([c.hyperlink.target if c.hyperlink and c.value in ('Assistir vídeo', 'Abrir anúncio') else c.value for c in row])
    return pasta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apelido', required=True)
    ap.add_argument('--arquivo', help='arquivo final já entregue; usa ultima-planilha.json se omitido')
    ap.add_argument('--painel', action='store_true')
    ap.add_argument('--adicionar-roteiros', action='store_true')
    ap.add_argument('--csv', action='store_true')
    ap.add_argument('--permitir-parcial', action='store_true', help='acrescentar os disponíveis com pendências explícitas')
    args = ap.parse_args()
    p = C.pasta(args.apelido)
    arquivo = args.arquivo or C.ler(p, 'ultima-planilha.json', {}).get('arquivo')
    if not arquivo or not Path(arquivo).is_file():
        raise SystemExit('Localizar o XLSX final existente antes de editar; nenhum arquivo foi criado.')
    if not (args.painel or args.adicionar_roteiros or args.csv):
        raise SystemExit('Informar --painel, --adicionar-roteiros ou --csv.')
    if args.painel or args.adicionar_roteiros:
        n = atualizar(arquivo, p, args.painel, args.adicionar_roteiros, args.permitir_parcial)
        cobertura = verificar(p)
        status = 'ATUALIZAÇÃO CONFERIDA COM LOTE PARCIAL' if args.adicionar_roteiros and (cobertura['faltam'] or cobertura['falhas']) else 'CONFERÊNCIA OK'
        print(f'{status}: mesmo arquivo atualizado; {n} roteiros acrescentados. {arquivo}')
    if args.csv:
        print('CSV: ' + str(exportar_csv(arquivo)))


if __name__ == '__main__':
    main()
