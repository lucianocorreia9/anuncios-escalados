"""Painel da primeira guia, calculado a partir das tabelas do próprio XLSX."""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill

import comum as C


def linhas(ws):
    return [list(row) for row in ws.iter_rows(min_row=2, values_only=True) if any(v is not None for v in row)]


def aplicar(wb, p):
    ws = wb['Como ler']
    if ws.sheet_properties.codeName != 'HapogeuPainel':
        if 'painel' in str(ws['A1'].value or '').lower():
            raise ValueError('Já existe um painel personalizado. Editar seus campos pontualmente, sem substituí-lo.')
        if ws._images or ws._charts:
            raise ValueError('A primeira guia contém objetos próprios. Preservá-los em uma edição pontual.')
        ws.insert_rows(1, 44)
        ws.sheet_properties.codeName = 'HapogeuPainel'
    # Só a área reservada ao painel é alterada; o guia e demais abas permanecem.
    for merged in list(ws.merged_cells.ranges):
        if merged.max_row <= 44:
            ws.unmerge_cells(str(merged))
    for row in ws.iter_rows(min_row=1, max_row=44, max_col=14):
        for c in row:
            c.value = None
            c.hyperlink = None
    ws._charts = [c for c in ws._charts if c.title and 'Cópias por gancho' not in str(c.title)]
    for col in range(1, 15):
        ws.column_dimensions[chr(64+col)].width = 13
    for row in range(1, 45):
        ws.row_dimensions[row].height = 24
    # O guia original ocupa uma coluna; mesclar só as suas linhas, sem apagá-lo.
    for row in range(45, ws.max_row+1):
        if ws.cell(row, 1).value and not any(ws.cell(row, c).value is not None for c in range(2, 15)):
            if not any(r.min_row <= row <= r.max_row for r in ws.merged_cells.ranges):
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=14)
                ws.row_dimensions[row].height = 42
    ads, videos, scripts = linhas(wb['Todos os Anúncios']), linhas(wb['Todos os Vídeos']), linhas(wb['Roteiros Validados'])
    vg = defaultdict(lambda: {'copias': 0, 'ativos': 0, 'historico': 0})
    for row in videos:
        if isinstance(row[11], (int, float)):
            d = vg[row[1]]
            d['copias'] += row[8]
            d['ativos'] += row[4]
            d['historico'] = max(d['historico'], row[6])
    order = sorted(vg, key=lambda g: (-vg[g]['copias'], -vg[g]['historico'], -vg[g]['ativos']))
    representantes = {}
    for rr in range(2, wb['Roteiros Validados'].max_row+1):
        c = wb['Roteiros Validados'].cell(rr, 2)
        if c.value in vg and wb['Roteiros Validados'].cell(rr, 13).value:
            representantes.setdefault(c.value, rr)
    T = C.momento_coleta(p)
    dia = T.date()
    novos = 0
    for row in ads:
        try:
            inicio = row[6].date() if isinstance(row[6], dt.datetime) else row[6] if isinstance(row[6], dt.date) else dt.datetime.strptime(row[6], '%d/%m/%Y').date()
            novos += dia-dt.timedelta(days=6) <= inicio <= dia
        except (ValueError, TypeError):
            raise ValueError('Data de início inválida em Todos os Anúncios: ' + str(row[6]))
    ativos = [r for r in ads if r[3] == 'Ativo']
    total_video = sum(v['copias'] for v in vg.values())
    top5 = sum(vg[g]['copias'] for g in order[:5])
    meta = C.ler(p, 'meta.json', {})
    limites = '; '.join(f"{a['tipo']} {a['valor']}: " + ('concluído' if a.get('esgotado') is True else 'limitado' if a.get('esgotado') is False else 'cobertura não informada') for a in meta.get('alvos', []))
    scope = meta.get('escopo') or limites or 'Resultados coletados; limites de busca não informados.'
    def faixa(row, start, end, value, size=11, bold=False, background=None):
        ws.merge_cells(start_row=row, start_column=start, end_row=row, end_column=end)
        c = ws.cell(row, start, value)
        c.font = Font(name='Arial', size=size, bold=bold, color='FFFFFF' if background else '203A5D')
        c.alignment = Alignment(wrap_text=True, vertical='center')
        if background:
            for cells in ws.iter_rows(min_row=row, max_row=row, min_col=start, max_col=end):
                for cell in cells:
                    cell.fill = PatternFill('solid', fgColor=background)
        return c
    faixa(1, 1, 14, 'Painel do concorrente', 20, True, '203A5D')
    faixa(2, 1, 14, meta.get('nome', 'Concorrente'), 14, True)
    faixa(3, 1, 14, f'Retrato de {dia:%d/%m/%Y}. {scope}')
    ws.row_dimensions[3].height = 60
    cards = [
        ('Anúncios ativos na consulta', len(ativos)), ('Anúncios únicos coletados', len({r[15] for r in ads})),
        ('Vídeos diferentes', sum(isinstance(r[11], (int, float)) for r in videos)),
        ('Ganchos em vídeo com roteiro', f'{len(representantes)} de {len(vg)}'),
        ('Novos anúncios em sete dias', novos), ('Cópias do gancho líder', vg[order[0]]['copias'] if order else 0),
        ('Maior tempo ativo (dias)', max((r[5] for r in ativos), default=0)),
        ('Cópias nos cinco maiores ganchos', top5/total_video if total_video else 0)]
    for i, (label, value) in enumerate(cards):
        row, col = 5+(i//4)*4, 1+(i%4)*3
        faixa(row, col, col+2, label, 10, True)
        c = faixa(row+1, col, col+2, value, 22, True)
        c.alignment = Alignment(horizontal='center', vertical='center')
        if i == 7:
            c.number_format = '0.0%'
    faixa(13, 1, 14, f'Denominador: {total_video} anúncios com vídeo identificável. Maior histórico: {max((r[5] for r in ads), default=0)} dias. Ativo refere-se à data da consulta.')
    faixa(14, 1, 14, 'Cópias e tempo no ar são sinais indiretos; não comprovam conversão ou lucro. Capas sem MP4 podem esconder vídeos ativos.')
    ws.row_dimensions[14].height = 36
    faixa(16, 1, 14, 'Cinco ganchos de vídeo com mais cópias', 13, True)
    headers = [(1, 6, 'Gancho'), (7, 7, 'Cópias'), (8, 8, 'Ativos'), (9, 10, 'Histórico (dias)'), (11, 12, 'Vídeo'), (13, 14, 'Roteiro')]
    for start, end, label in headers:
        faixa(17, start, end, label, 10, True, '203A5D')
    for rr, g in enumerate(order[:5], 18):
        faixa(rr, 1, 6, g, 10)
        ws.row_dimensions[rr].height = 42
        ws.cell(rr, 7, vg[g]['copias'])
        ws.cell(rr, 8, vg[g]['ativos'])
        ws.cell(rr, 7).alignment = Alignment(horizontal='center', vertical='center')
        ws.cell(rr, 8).alignment = Alignment(horizontal='center', vertical='center')
        faixa(rr, 9, 10, vg[g]['historico'])
        target = representantes.get(g)
        if target:
            link = wb['Roteiros Validados'].cell(target, 12).hyperlink
            if link:
                faixa(rr, 11, 12, 'Assistir vídeo').hyperlink = link.target
            faixa(rr, 13, 14, 'Ler roteiro').hyperlink = f"#'Roteiros Validados'!M{target}"
        else:
            faixa(rr, 11, 14, 'Sem roteiro neste lote')
    if order:
        chart = BarChart()
        chart.type = 'bar'
        chart.title = 'Cópias por gancho'
        chart.x_axis.title = 'Cópias'
        chart.x_axis.scaling.min = 0
        chart.y_axis.scaling.orientation = 'maxMin'
        chart.add_data(Reference(ws, min_col=7, min_row=17, max_row=17+min(5, len(order))), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=18, max_row=17+min(5, len(order))))
        chart.legend = None
        chart.width, chart.height = 27, 9
        ws.add_chart(chart, 'A25')
    ws.freeze_panes = 'A17'
    ws.sheet_view.showGridLines = False
    wb.active = wb.sheetnames.index('Como ler')
