"""Regressões offline: cobertura, cópias, prints, painel e edição no mesmo arquivo."""
from contextlib import redirect_stdout
import datetime as dt
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import load_workbook
from openpyxl.styles import Font
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'anuncios-escalados' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import comum as C
import coletar
from cobertura import selecionar, verificar
from visual import mesmos_quadros, quadros
from atualizar import atualizar, estado
import montar
import criativos_locais
import transcrever


class Consultas(unittest.TestCase):
    def test_sondagem_acima_do_teto_recusa_antes_da_rede(self):
        args = SimpleNamespace(apelido='exemplo', nome=None, nome_pagina=None,
                               dominio=['loja-exemplo.invalid'], termo=['Curso Exemplo'],
                               pagina=None, teto=1)
        with tempfile.TemporaryDirectory() as pasta, patch.object(C, 'pasta', return_value=pasta):
            with patch.object(C, 'chamar') as chamada:
                with self.assertRaisesRegex(SystemExit, 'exige 2 consultas'):
                    coletar.sondar(args)
                chamada.assert_not_called()

    def test_falha_de_rede_nao_repete_consulta(self):
        with patch.object(C, 'chave', return_value='ficticia'):
            with patch.object(C.urllib.request, 'urlopen', side_effect=TimeoutError) as abrir:
                with self.assertRaisesRegex(C.ParadaNaAPI, 'Confira o saldo'):
                    C.chamar('', 'search/ads', {'query': 'exemplo'})
                abrir.assert_called_once()


class Fluxo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='anuncios-skill-test-')
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)/'cache'
        self.p.mkdir()
        self.out = Path(self.tmp.name)/'entrega'
        self.print = self.p/'frame.png'
        Image.new('RGB', (64, 96), '#203a5d').save(self.print)
        self.mp4 = self.p/'video.mp4'
        subprocess.run([C.ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                        '-i', 'testsrc2=size=96x128:rate=3', '-t', '3', '-c:v', 'libx264', str(self.mp4)], check=True)
        self.digest = hashlib.sha256(self.mp4.read_bytes()).hexdigest()
        self.T = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)
        meta = {'nome': 'Exemplo', 'coleta': self.T.isoformat(), 'alvos': [{'tipo': 'dominio', 'valor': 'exemplo.invalid'}],
                'escopo': 'Coleta fictícia parcial por páginas; domínio esgotado.'}
        self.cri, self.ads, self.groups = {}, [], []
        for i in range(18):
            code = f'V3.00-{i}'
            self.add_creative(code, i, 20 if i == 0 else 2 if i == 1 else 1, days=5 if i == 0 else 150 if i == 1 else 7)
        self.add_creative('V3.00-extra', 0, 3, days=2)
        self.add_creative('I1', 18, 1, video=False)
        self.add_creative('T1', 19, 1, video=False)
        for name, obj in [('meta.json', meta), ('criativos.json', {'criativos': self.cri, 'ordem_roteiros': list(self.cri)[:-2]}),
                          ('anuncios.json', self.ads), ('grupos.json', {'grupos': self.groups}),
                          ('aberturas.json', {k: 'Fala original de abertura '+k for k in self.cri})]:
            C.gravar(str(self.p), name, obj)
        self.prepare_media(selecionar(str(self.p)))

    def add_creative(self, code, group, copies, days=7, video=True):
        while len(self.groups) <= group:
            self.groups.append({'nome': 'Gancho '+str(len(self.groups)), 'tipo': 'Pergunta', 'itens': []})
        ids = []
        for j in range(copies):
            aid = str(len(self.ads)+1)
            ids.append(aid)
            snapshot = {'page_name': 'Página fictícia', 'title': 'Título original', 'body': {'text': 'Texto original'},
                        'display_format': 'VIDEO' if video else 'IMAGE', 'link_url': 'https://exemplo.invalid/pv',
                        'videos': [{'video_sd_url': 'https://midia.invalid/'+code+'.mp4'}] if video else []}
            self.ads.append({'ad_archive_id': aid, 'snapshot': snapshot, 'start_date': int((self.T-dt.timedelta(days=days-1)).timestamp()),
                             'is_active': group != 1, 'end_date': int(self.T.timestamp()), '_rank': len(self.ads)+1,
                             'gated_type': 'ELIGIBLE', 'url': 'https://facebook.invalid/'+aid})
        self.cri[code] = {'tipo': 'video' if video else 'imagem' if code.startswith('I') else 'texto',
                          'dur': 3 if video else None, 'ids': ids, 'exemplo': ids[0], 'formato': 'Vídeo' if video else 'Imagem'}
        self.groups[group]['itens'].append(code)

    def prepare_media(self, codes):
        manifest = C.ler(str(self.p), 'midias-locais.json', {})
        scripts = C.ler(str(self.p), 'roteiros.json', {})
        origins = C.ler(str(self.p), 'roteiros-origens.json', {})
        for k in codes:
            manifest[k] = {'conferido': True, 'arquivo': str(self.mp4), 'print': str(self.print), 'sha256': self.digest}
            scripts[k] = 'Transcrição integral fictícia para conferir vínculo do arquivo. '+k
            origins[k] = {'sha256': self.digest}
        for name, obj in [('midias-locais.json', manifest), ('roteiros.json', scripts), ('roteiros-origens.json', origins)]:
            C.gravar(str(self.p), name, obj)
        C.gravar(str(self.p), 'selecionados.json', {'codigos': codes})

    def build(self, extra_args=()):
        args = ['montar.py', '--apelido', 'ficticio', '--saida', str(self.out), *extra_args]
        with patch.object(C, 'pasta', return_value=str(self.p)), patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()) as out:
            montar.main()
        self.arq = Path(C.ler(str(self.p), 'ultima-planilha.json')['arquivo'])
        return out.getvalue()

    def test_lote_de_15_e_ranking_global_aceita_mesmo_gancho(self):
        codes = selecionar(str(self.p))
        self.assertEqual(len(codes), 15)
        self.assertEqual(codes[:3], ['V3.00-0', 'V3.00-extra', 'V3.00-1'])
        self.assertNotIn('I1', codes)
        self.assertEqual(verificar(str(self.p))['grupos_cobertos'], 14)
        with self.assertRaises(ValueError):
            selecionar(str(self.p), 14)
        extended = selecionar(str(self.p), 19)
        self.assertEqual(extended[:15], codes)
        self.assertEqual(len(extended), 19)

    def test_transcricao_parcial_usa_mp4_disponivel(self):
        escolhido = selecionar(str(self.p))[0]
        self.prepare_media([escolhido])
        C.gravar(str(self.p), 'roteiros.json', {})
        trecho = SimpleNamespace(start=0, end=1, text='Fala de teste.',
                                  no_speech_prob=0.0, avg_logprob=-0.1, words=None)
        args = SimpleNamespace(apelido='ficticio', ate=None, locais=True, permitir_parcial=True,
                               refazer_codigos=[], sem_vad_codigos=[], canal_esquerdo_codigos=[],
                               modelo='small', threads=None)
        with patch.object(C, 'pasta', return_value=str(self.p)):
            with patch.object(transcrever, 'modelo') as modelo, redirect_stdout(io.StringIO()):
                modelo.return_value.transcribe.return_value = ([trecho], SimpleNamespace(duration=3))
                transcrever.roteiros(args)
        self.assertEqual(verificar(str(self.p))['validos'], [escolhido])
        self.assertEqual(C.ler(str(self.p), 'roteiros.json'), {escolhido: 'Fala de teste.'})

    def test_desempates_de_tempo_e_ativos(self):
        maior = dict(n=3, maior=80, ativos=0, rank=50)
        menor = dict(n=3, maior=79, ativos=3, rank=1)
        self.assertLess(C.ordem_roteiros(maior), C.ordem_roteiros(menor))
        mais_ativos = dict(maior, ativos=2, rank=99)
        self.assertLess(C.ordem_roteiros(mais_ativos), C.ordem_roteiros(maior))

    def test_pendente_hash_e_bloqueio_de_conclusao(self):
        origins = C.ler(str(self.p), 'roteiros-origens.json')
        origins['V3.00-13']['sha256'] = 'incorreto'
        C.gravar(str(self.p), 'roteiros-origens.json', origins)
        result = verificar(str(self.p))
        self.assertEqual(result['grupos_cobertos'], 13)
        self.assertEqual(result['faltam'], 1)
        self.assertIn('V3.00-13', result['falhas'])
        with self.assertRaises(SystemExit):
            self.build()
        self.assertFalse(self.out.exists())
        output = self.build(['--permitir-parcial'])
        self.assertIn('ENTREGA PARCIAL', output)
        self.assertNotIn('\nCONFERÊNCIA OK\n', output)
        wb = load_workbook(self.arq)
        self.assertEqual(wb['Como ler']['J6'].value, '13 de 18')

    def test_painel_e_atualizacao_no_mesmo_arquivo(self):
        self.assertIn('CONFERÊNCIA OK', self.build())
        wb = load_workbook(self.arq)
        self.assertEqual(wb.active.title, 'Como ler')
        panel = wb['Como ler']
        self.assertEqual(len(panel._charts), 1)
        self.assertEqual(panel['A6'].value, sum(r['is_active'] for r in self.ads))
        self.assertEqual(panel['D6'].value, len(self.ads))
        self.assertEqual(panel['G6'].value, 19)
        self.assertEqual(panel['J6'].value, '14 de 18')
        self.assertEqual(panel['D10'].value, 23)
        self.assertEqual(panel['A10'].value, len(self.ads)-2)
        self.assertAlmostEqual(panel['J10'].value, 28/41)
        self.assertEqual(panel['A18'].value, 'Gancho 0')
        self.assertTrue(panel['K18'].hyperlink.target.startswith('file:'))
        self.assertTrue(panel['M18'].hyperlink.target.startswith('#'))
        videos = wb['Todos os Vídeos']
        videos['X1'] = 'Anotação do usuário'
        videos['X2'] = 'Preservar esta nota'
        videos['X2'].font = Font(bold=True, color='FF0000')
        wb.save(self.arq)
        before = load_workbook(self.arq)
        untouched = {name: estado(before[name]) for name in before.sheetnames if name != 'Como ler'}
        old_images = len(before['Roteiros Validados']._images)
        atualizar(self.arq, str(self.p), painel=True)
        after = load_workbook(self.arq)
        self.assertEqual(len(after['Como ler']._charts), 1)
        self.assertEqual(len(after['Roteiros Validados']._images), old_images)
        for name, expected in untouched.items():
            self.assertEqual(estado(after[name]), expected, name)
        self.assertEqual(list(self.arq.parent.glob('*.xlsx')), [self.arq])
        digest = hashlib.sha256(self.arq.read_bytes()).hexdigest()
        with self.assertRaises(SystemExit):
            self.build()
        self.assertEqual(hashlib.sha256(self.arq.read_bytes()).hexdigest(), digest)

    def test_extras_preservam_linhas_e_prints(self):
        self.build()
        old = load_workbook(self.arq)
        codes = selecionar(str(self.p), 19)
        self.prepare_media(codes)
        self.assertEqual(atualizar(self.arq, str(self.p), painel=True, adicionar=True), 4)
        after = load_workbook(self.arq)
        self.assertEqual(after['Roteiros Validados'].max_row, 20)
        self.assertEqual(len(after['Roteiros Validados']._images), 19)
        for row in range(1, 17):
            for col in range(1, 15):
                self.assertEqual(old['Roteiros Validados'].cell(row, col).value, after['Roteiros Validados'].cell(row, col).value)

    def test_extra_mais_copiado_sobe_com_print_link_e_anotacao(self):
        codes = selecionar(str(self.p))
        first = codes[0]
        self.prepare_media(codes[1:] + ['V3.00-14'])
        self.build()
        wb = load_workbook(self.arq)
        from openpyxl.comments import Comment
        ws = wb['Roteiros Validados']
        old_code_position = ws['D2'].value
        ws['M2'].comment = Comment('Nota do usuário', 'Usuário')
        wb.save(self.arq)
        self.prepare_media([first] + codes[1:] + ['V3.00-14'])
        self.assertEqual(atualizar(self.arq, str(self.p), adicionar=True), 1)
        wb = load_workbook(self.arq)
        ws = wb['Roteiros Validados']
        self.assertEqual(ws['I2'].value, 20)
        self.assertEqual(ws['D3'].value, old_code_position)
        self.assertEqual(ws['M3'].comment.text, 'Nota do usuário')
        self.assertTrue(ws['L3'].hyperlink.target.startswith('file:'))
        self.assertEqual(sorted(img.anchor._from.row for img in ws._images), list(range(1, 17)))

    def test_frames_reais_e_falta_nao_comprova_igualdade(self):
        frames = quadros(str(self.mp4), 3, self.p/'frames')
        self.assertEqual(len(frames), 5)
        self.assertTrue(all(Path(q['arquivo']).is_file() for q in frames))
        self.assertTrue(mesmos_quadros(frames, frames))
        self.assertFalse(mesmos_quadros(frames, []))
        changed = [dict(q, assinatura=''.join('0' if bit == '1' else '1' for bit in q['assinatura'])) for q in frames]
        self.assertFalse(mesmos_quadros(frames, changed))
        late_change = [dict(q) for q in frames]
        late_change[-1] = changed[-1]
        self.assertFalse(mesmos_quadros(frames, late_change))

    def test_download_avanca_no_ranking_e_para_em_15(self):
        C.gravar(str(self.p), 'selecionados.json', {'codigos': []})
        target = Path(self.tmp.name)/'concorrente'/'criativos'
        target.mkdir(parents=True)
        prints = self.p/'prints-validados'
        prints.mkdir()
        for k in self.cri:
            if k.startswith('V') and k != 'V3.00-0':
                shutil.copy2(self.mp4, target/f'00-{k}-exemplo.mp4')
                shutil.copy2(self.print, prints/f'{k}.png')
        args = ['criativos_locais.py', '--apelido', 'ficticio', '--pasta-concorrente', str(target.parent)]
        with patch.object(C, 'pasta', return_value=str(self.p)), patch.object(sys, 'argv', args), \
             patch('urllib.request.urlopen', side_effect=OSError('Mídia indisponível')), \
             patch.object(criativos_locais, 'conferir', return_value={'duracao_s': 3., 'audio': False}), redirect_stdout(io.StringIO()):
            criativos_locais.main()
        selected = C.ler(str(self.p), 'selecionados.json')['codigos']
        self.assertEqual(len(selected), 15)
        self.assertNotIn('V3.00-0', selected)
        self.assertIn('V3.00-extra', selected)
        self.assertIn('V3.00-14', selected)
        self.assertNotIn('V3.00-15', selected)
        with patch.object(C, 'pasta', return_value=str(self.p)), patch.object(sys, 'argv', args + ['--ate', '20']):
            with self.assertRaisesRegex(SystemExit, 'Entregue a primeira planilha'):
                criativos_locais.main()


if __name__ == '__main__':
    unittest.main()
