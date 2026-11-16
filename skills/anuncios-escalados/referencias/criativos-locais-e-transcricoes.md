# Criativos locais e transcrições

O entregável permite assistir aos criativos sem depender dos endereços temporários da Meta. Atalho `.webloc` não é vídeo baixado.

## 1. Seleção do lote

- Salvar o XLSX em `<pasta-do-projeto>/pesquisas-meta/<nome_do_concorrente>/` e os MP4 em `criativos/`. Isolar concorrentes e preservar arquivos anteriores.
- Concluir os grupos antes da seleção. Escolher os 15 vídeos visualmente distintos com mais cópias. Desempatar pelo maior tempo no ar e depois pelo número de ativos.
- Antes do download integral, comparar os candidatos do lote com os demais já selecionados, inclusive os entregues anteriormente. A mesma fala pode aparecer em vídeos diferentes, com outro cenário, roupa ou imagens. Uma mudança de capa, compressão ou recorte do mesmo vídeo, por si só, é uma cópia.
- `selecionados.json` registra os códigos dos MP4 conferidos e a meta do lote. Se um vídeo estiver indisponível, avançar no ranking até preencher o lote. Conferir também os substitutos pelos quadros coletados. Se faltar mídia, registrar o total que falta e pedir aprovação antes de novas chamadas pagas.
- Comparar prints dos momentos iniciais e posteriores, além de duração e capa. Recompressão, corte ou outra capa do mesmo conteúdo não contam automaticamente como outro vídeo. Registrar evidência em `revisao-visual.json`.
- Em alterações posteriores, a seleção aprovada é a própria aba Roteiros Validados. Preservar os vídeos, códigos, textos e vínculos, inserindo novos itens conforme a ordem geral.
- Nomear MP4 como `<posição>-<código>-<grupo>.mp4`. Associar código, anúncio original, endereço da mídia, arquivo, hash, print e transcrição. O endereço da Biblioteca de Anúncios não é o endereço do MP4.

## 2. Download e conferência

1. Baixar um arquivo por vez, integralmente, para `.part`. Não substituir por capa, áudio ou atalho.
2. Conferir resposta HTTP, tipo de conteúdo e tamanho recebido. HTML com extensão MP4 não é vídeo. Nova coleta paga continua sujeita ao teto aprovado.
3. Confirmar contêiner MP4, faixa de vídeo, duração coerente e áudio quando esperado. Se precisar converter contêiner, usar ffmpeg, preservando a origem.
4. Decodificar o arquivo inteiro com `ffmpeg -v error -i "<arquivo.mp4>" -f null -`. Só considerar completo quando terminar sem erro.
5. Registrar código, posição, arquivo, bytes, duração, hash e conferência em `midias-locais.json`. Reutilizar arquivos íntegros.

## 3. Transcrição do arquivo local

Usar a mídia completa como fonte quando a reprodução integral for permitida. Havendo impedimento, declarar a pendência sem preencher o campo com resumo ou análise.

```bash
uv run --no-project --python 3.13 python criativos_locais.py --apelido <apelido> --pasta-concorrente "<pasta>"
uv run --no-project --python 3.13 --with-requirements ../requirements-transcricao.txt python transcrever.py roteiros --apelido <apelido> --locais
uv run --no-project --python 3.13 python cobertura.py --apelido <apelido> --conferir
```

A transcrição deve estar vinculada ao hash do MP4 em `roteiros-origens.json`. A conferência de cobertura exige MP4, print, texto não vazio e vínculo com o arquivo atual; isso não substitui ouvir o vídeo para conferir reconhecimento completo.

Usar uma transcrição por vez, `small` como padrão e `medium --refazer-codigos <códigos>` para falhas pontuais. Usar `--sem-vad-codigos` para fala cantada ou perdida pelo detector. Se os canais se anularem ao somar para mono, conferir os canais e usar `--canal-esquerdo-codigos`, preservando o MP4 original. Corrigir também a abertura após recuperar fala antes não reconhecida.

Manter a fala do início ao fim, em parágrafos legíveis. Corrigir erros evidentes após ouvir ou conferir legendas. Marcar trechos não reconhecidos e não inventar palavras. Não afirmar que só há música após uma única tentativa de reconhecimento.

## 4. Planilha existente, print e extras

- Preencher a transcrição integral e um hiperlink nativo `Assistir vídeo` para o MP4 local. Nas outras abas, manter links da Biblioteca da Meta.
- Incorporar um print do próprio MP4, normalmente aos dois segundos, ajustando se o quadro estiver vazio. Os outros frames auxiliam a comparação visual; não usar print de outro representante do grupo.
- Atualizações carregam o XLSX já entregue e salvam no mesmo caminho. Ao inserir um extra no ranking, manter transcrição, print, links e anotações vinculados ao mesmo vídeo.
- Entregar os 15 primeiro. Perguntar se o usuário quer mais 5, mais 10 ou outra quantidade. Só então usar `--ate <total-acumulado-autorizado>` no download e na transcrição. Atualizar o XLSX com `atualizar.py --adicionar-roteiros --painel`.
- Reabrir o arquivo e conferir a ordem e todos os vínculos. Informar quantos MP4 e roteiros foram entregues e, se o lote ficar abaixo da meta, quantos faltam.
