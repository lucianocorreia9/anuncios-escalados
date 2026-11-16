---
name: anuncios-escalados
description: "Pesquisa anúncios de concorrentes na Meta pela ScrapeCreators, agrupa pelo gancho dos 16 segundos iniciais e entrega uma planilha com painel e os 15 vídeos distintos mais bem colocados por cópias, baixados e transcritos. Lotes adicionais exigem autorização e entram na mesma planilha. Aceita site, Instagram, Facebook, produto ou nicho. Use somente quando o usuário invocar /anuncios-escalados no Claude Code ou $anuncios-escalados no Codex."
disable-model-invocation: true
---

# Anúncios escalados na biblioteca da Meta

Use a **quantidade de anúncios que repetem o criativo**, seguida pelo tempo no ar, para identificar quais vídeos vale estudar. Cada ID único da Biblioteca da Meta que usa aquele vídeo conta uma vez, incluindo o primeiro anúncio. Mudanças no texto do anúncio, título ou destino mantêm a contagem do vídeo quando a gravação e a edição são as mesmas. A Biblioteca não informa conversão ou lucro.

O entregável é **uma planilha .xlsx por concorrente**, com painel na primeira guia e **15 vídeos distintos** na aba Roteiros Validados na primeira entrega. Cada linha tem MP4 local, print e transcrição completa. A quantidade de ganchos encontrados não amplia o lote.

## Regras permanentes

1. **Aprovar gastos antes de executar:** no modo nicho, aprovar a lista de concorrentes. Em qualquer modo, consultar o usuário por uma pergunta com opções antes da sondagem paga e antes da coleta. Mostrar estimativa de consultas, custo em créditos, saldo conhecido e teto com eventual margem já incluída. Aplicar o teto também para renovar links ou buscar vídeos para preencher o lote.
2. **Consulta paga que falhou exige diagnóstico:** ler o erro e corrigir a causa antes de repetir. Não repetir recusas da ScrapeCreators às cegas.
3. **Conclusão exige evidência:** conferir o XLSX salvo, seus links, prints e transcrições. A primeira entrega completa tem 15 roteiros validados, mesmo que sobrem ganchos sem roteiro. Se houver menos de 15 vídeos verificáveis, informar o número entregue e o que falta para atingir 15. Consultar o gasto antes de continuar a busca paga.
4. **Isolamento:** uma pasta por concorrente. Não incluir dados privados, copy ou estratégia de outro cliente ou projeto.
5. **Linguagem:** português do Brasil, sem jargão e sem travessão.
6. **Arquivo real e texto fiel:** entregar MP4 completos em `criativos/`, conferir a decodificação integral e transcrever o próprio arquivo local quando a reprodução integral for permitida. `.webloc`, resumo e análise não substituem vídeo nem transcrição. Manter as aberturas, textos e títulos originais em seus campos; análises ficam separadas.
7. **Diversidade verificada:** comparar prints do início, meio e fim, além de duração e capa. O mesmo gancho ou texto falado pode aparecer em mais de uma linha quando o vídeo for visualmente diferente, por exemplo por outra gravação, cenário, roupa ou imagens usadas na edição. Outra capa, compressão ou recorte da mesma gravação, por si só, conta como cópia. Se os quadros forem insuficientes, rever a mídia antes de validar. Documentar as decisões em `revisao-visual.json`.
8. **Um arquivo final por pesquisa:** alterações e adições posteriores editam o XLSX existente no mesmo caminho, sem reconstruir a planilha do zero. Preservar abas, linhas, códigos, transcrições, prints, links, filtros, estilos e anotações não afetados. Não criar versões `v2`, `Complemento` ou equivalentes. Ver o Passo 3b.

## Entradas e preparação

Aceitar site, página de venda, Instagram, Facebook, nome de concorrente, produto ou nicho. Só nicho começa no Passo 0; concorrente conhecido começa no Passo 1. Vários concorrentes recebem pesquisas e arquivos separados.

- Resolva os caminhos a partir da pasta que contém este `SKILL.md`. Execute os comandos abaixo com `scripts/` como pasta de trabalho do terminal, sem alterar a pasta da sessão do usuário.
- Verifique `uv` e `ffmpeg` no terminal. O Python 3.13 e as bibliotecas são carregados pelo `uv`. A primeira transcrição pode baixar o modelo de voz.
- A coleta usa `SCRAPECREATORS_API_KEY` ou, para apps abertos fora do terminal, `~/.config/anuncios-escalados/.env`. Nunca imprimir a chave. Na falta dela, orientar a configuração antes da coleta.
- Use um apelido exclusivo por pesquisa, com letras minúsculas ASCII, números e hífens, como `loja-exemplo`. Os dados intermediários ficam em `~/.cache/anuncios-escalados/<apelido>/` por padrão. Defina a pasta absoluta de entrega na pasta de trabalho do usuário ou onde ele pedir.

## Passo 0: os maiores do nicho

Seguir [como pesquisar os maiores do nicho](referencias/passo-0-maiores-do-nicho.md). Pesquisar audiência, sinais de venda e site ou produto. Quando o ambiente e o usuário autorizarem ajudantes, essas frentes podem rodar em paralelo.

Mostrar candidatos e fontes, com os recomendados primeiro, e pedir a escolha por uma pergunta com opções. Só os aprovados seguem para consultas pagas.

## Passo 1: achar e baixar os anúncios

**1a. Montar alvos gratuitamente:** site como alvo principal, produto ou bordão como frase exata e página do Facebook por número. Quando só houver Instagram ou nome, localizar o site na bio, página de venda ou pesquisa pública. Busca por nome pode trazer homônimos.

**1b. Sondar somente após aprovar o custo:** uma consulta por alvo; `--nome-pagina` também custa uma consulta. A sondagem guarda a primeira página para não pagar duas vezes.

```bash
uv run --no-project --python 3.13 python coletar.py sondar --apelido <apelido> --nome "<Nome>" --teto <teto-aprovado> --dominio <site> [--termo "<produto>"] [--pagina <número>]
```

Conferir páginas e sites retornados. Mostrar, por alvo, o volume encontrado, consultas restantes estimadas, saldo e custo máximo proposto. Oferecer coleta completa, somente alvo principal ou teto menor. Se for necessário ampliar para páginas do anunciante, incluir esse custo na aprovação antes de sondar ou coletar essas páginas.

**1c. Baixar dentro do teto aprovado:** a margem de 10%, quando usada, deve estar expressa no teto que o usuário aprovou; não acrescentar margem depois do OK.

```bash
uv run --no-project --python 3.13 python coletar.py baixar --apelido <apelido> --teto <teto-aprovado>
```

Ler a lista de anúncios separados em `fora.json`. Corrigir inclusão ou exclusão de páginas com `coletar.py filtrar --apelido <apelido> --incluir-pagina "<nome>"` ou `--excluir-pagina "<nome>"`. Filtrar não custa consultas. Registrar se cada alvo foi esgotado ou limitado, para não apresentar a amostra como toda a operação.

## Passo 2: medir, comparar e agrupar

Rodar logo após a coleta, porque os endereços de mídia expiram. Renovação paga continua sujeita à aprovação prévia. Baixar e comparar mídia já retornada não gasta ScrapeCreators.

```bash
uv run --no-project --python 3.13 python medir.py --apelido <apelido>
uv run --no-project --python 3.13 --with-requirements ../requirements-transcricao.txt python transcrever.py aberturas --apelido <apelido>
uv run --no-project --python 3.13 python agrupar.py preparar --apelido <apelido>
```

- `medir.py` compara duração, capa e assinaturas de quadros do vídeo. Os prints ficam em `frames/`. Conferir visualmente os candidatos, especialmente cortes, recompressões e durações próximas; coincidência de capa ou duração não basta. A falta de quadros é pendência de identificação, nunca prova de igualdade.
- Ler [como agrupar](referencias/como-agrupar.md), olhar os prints, ouvir as aberturas e gravar `grupos.json`. Gancho é a ideia dos primeiros 16 segundos. Vídeos diferentes podem compartilhar um gancho; duplicatas do mesmo vídeo somam cópias, sem inflar a diversidade. Registrar decisões em `revisao-visual.json` e aplicar correções nos dados antes de fechar os grupos.
- Para comparar criativos, acessar apenas o necessário para extrair os quadros e os 16 segundos iniciais. Não guardar MP4 nem áudio integral em lote para essa análise. Depois de concluir os grupos, baixar e transcrever integralmente só o lote autorizado.
- Rodar `uv run --no-project --python 3.13 python agrupar.py conferir --apelido <apelido>` até `CONFERÊNCIA OK`. Todo criativo precisa pertencer a exatamente um grupo.
- Manter uma transcrição por vez, usando só os núcleos rápidos. `small` é o padrão; `medium` serve para revisar falhas pontuais. `base` só quando o usuário aceitar menor precisão. No Codex, executar em sequência.

**Ordem dos Roteiros Validados.** Ordenar globalmente pelos três critérios, em ordem decrescente: cópias do próprio vídeo, maior número de dias no ar entre seus anúncios e número de anúncios ativos do vídeo. O ranking considera todos os vídeos distintos da coleta. Vídeos distintos com o mesmo gancho podem entrar. As demais abas continuam usando a classificação por grupo e os níveis históricos.

## Passo 2b: baixar e transcrever os 15 primeiros vídeos

Ler [como baixar e transcrever os criativos](referencias/criativos-locais-e-transcricoes.md). Usar `<pasta-do-projeto>/pesquisas-meta/<nome_do_concorrente>/` por padrão, com o nome sem produto, em minúsculas, sem acentos e com `_`. Planilha e `criativos/` ficam nessa mesma pasta.

```bash
uv run --no-project --python 3.13 python criativos_locais.py --apelido <apelido> --pasta-concorrente "<pasta-do-concorrente>"
uv run --no-project --python 3.13 --with-requirements ../requirements-transcricao.txt python transcrever.py roteiros --apelido <apelido> --locais
uv run --no-project --python 3.13 python cobertura.py --apelido <apelido> --conferir
```

Baixar integralmente os 15 vídeos distintos mais bem colocados. Se um vídeo estiver indisponível, seguir para o próximo do ranking até chegar a 15 MP4 conferidos. Imagens, carrosséis sem vídeo e anúncios só de texto ficam fora do lote. A conferência exige MP4 íntegro, print do próprio arquivo e transcrição não vazia vinculada ao arquivo. Conferir também a fidelidade da transcrição ouvindo o vídeo.

Para erros relevantes, usar `--modelo medium --refazer-codigos <códigos>`. Fala cantada ou perdida pelo detector pode exigir `--sem-vad-codigos <códigos>`. Se os canais se anularem na conversão para mono, conferir separadamente e usar `--canal-esquerdo-codigos <códigos>`. Não inventar palavras nem classificar como música sem ouvir.

Se o download resultar em menos de 15 vídeos, usar `--permitir-parcial` junto de `--locais` em `transcrever.py roteiros` para transcrever os MP4 já conferidos. Se faltarem vídeos para preencher o lote, informar quantos faltam e quais candidatos falharam. Antes de qualquer nova consulta paga, apresentar tentativas já feitas, estimativa, saldo e teto proposto. Quando não houver autorização ou disponibilidade, entregar os roteiros conferidos e indicar quantos faltam para atingir 15.

Para materializar uma entrega abaixo da meta, usar `montar.py --permitir-parcial` na primeira criação ou `atualizar.py --adicionar-roteiros --painel --permitir-parcial` no arquivo existente. Esses modos incluem apenas os roteiros conferidos. O painel mostra a cobertura de ganchos como informação da pesquisa.

## Passo 3: planilha com painel obrigatório

Na primeira criação:

```bash
uv run --no-project --python 3.13 --with openpyxl --with pillow python montar.py --apelido <apelido> --concorrente "<Nome Sobrenome>" --saida "<pasta-do-concorrente>"
```

Salvar `Anuncios-Meta-<Nome>-<AAAA-MM-DD>.xlsx`, com a data da coleta, na pasta do concorrente. As abas são **Como ler**, **Grupos**, **Todos os Vídeos**, **Todos os Anúncios** e **Roteiros Validados**. A primeira abre no painel; o guia de leitura fica abaixo dele. Manter endereços de destino completos e clicáveis.

O painel é parte da primeira entrega e sempre inclui:

1. Anúncios ativos no momento da consulta.
2. Total de anúncios únicos da coleta, incluindo pausados.
3. Vídeos diferentes identificados, sem duplicatas visuais.
4. Grupos de gancho com vídeo e cobertura em roteiros, como `20 de 20`.
5. Anúncios iniciados nos últimos sete dias, incluindo a data da coleta e os seis dias anteriores.
6. Quantidade de cópias do grupo de gancho em vídeo mais repetido.
7. Maior tempo no ar entre anúncios ativos, com o maior histórico informado à parte.
8. Participação dos cinco maiores ganchos nas cópias de anúncios com vídeo identificável.

Incluir ranking dos cinco ganchos de vídeo com mais cópias, gráfico nativo, cópias, ativos e tempo histórico. Vincular MP4 e roteiro quando o gancho estiver representado no lote. Informar data e escopo da coleta, limitações dos alvos e denominador de percentuais. Os números representam os resultados coletados. Se a API retornar apenas capas ou omitir mídia, registrar essa limitação.

Roteiros Validados recebe transcrição integral, link local `Assistir vídeo` e print do próprio MP4. Outras abas mantêm o link da Biblioteca da Meta. O montador confere cobertura e reabre o XLSX; só declarar pronto com `CONFERÊNCIA OK` e revisão visual da primeira guia, das primeiras linhas e dos vínculos entre código, MP4, print e transcrição. Pendências não podem ficar escondidas pelo painel.

## Passo 3b: alterações na mesma planilha

Quando o usuário pedir correção, adição, painel, coluna ou mais roteiros, localizar o arquivo final em `ultima-planilha.json` ou no caminho já entregue. Se houver mais de um candidato, conferir qual foi a última entrega, sem escolher só pela data de modificação. Abrir o **arquivo existente**, alterar apenas o necessário e salvar no **mesmo caminho e nome**. Não chamar o montador para recriar as abas.

Para atualizar o painel ou acrescentar roteiros já conferidos, usar:

```bash
uv run --no-project --python 3.13 --with openpyxl --with pillow python atualizar.py --apelido <apelido> --arquivo "<xlsx-existente>" --painel
uv run --no-project --python 3.13 --with openpyxl --with pillow python atualizar.py --apelido <apelido> --arquivo "<xlsx-existente>" --adicionar-roteiros --painel
```

Para outras alterações, carregar o mesmo arquivo com `load_workbook` e editar somente as células ou objetos solicitados. Preservar todas as abas e conteúdos não afetados, inclusive anotações do usuário e códigos já entregues. Inserir novos roteiros na posição ditada pelo ranking global, mantendo conteúdo, print e links juntos quando uma linha mudar de posição. Conferir imagens, hiperlinks, filtros e estilos após salvar.

Usar arquivo temporário fora da pasta de entrega para salvar e conferir antes da substituição atômica; isso não é uma segunda versão entregue. Não criar cópias em Downloads ou variantes na pasta final por rotina. Outra pesquisa datada pode ter outro arquivo; pequenas alterações da mesma pesquisa continuam no arquivo original. Não apagar pesquisas históricas sem pedido específico.

## Fechamento

1. Informar os cinco grupos com mais cópias, seus ativos e tempo histórico, total de anúncios, vídeos, grupos de vídeo, cobertura dos roteiros, consultas gastas, saldo conhecido e caminho do XLSX. Declarar qualquer pendência ou limitação de amostra.
2. Depois de entregar os 15, perguntar com opções se o usuário quer **mais 5**, **mais 10** ou **outra quantidade**. Aguardar a resposta antes de baixar ou transcrever qualquer extra. Usar `--ate <total-acumulado-autorizado>` no download e na transcrição, por exemplo 20 para mais 5 ou 25 para mais 10. Atualizar o mesmo XLSX com `atualizar.py --adicionar-roteiros --painel`. Consultas pagas adicionais têm aprovação própria.
3. Oferecer CSV como opcional; gerar só se o usuário quiser, exportando do arquivo final existente com `atualizar.py --csv`. A escolha por XLSX não depende do CSV.

## Limites da leitura

- A biblioteca brasileira não mostra conversão, lucro ou gasto de anúncios comerciais. Cópias e dias são sinais indiretos. Posição por impressões é posição relativa na busca, não quantidade de impressões.
- A operação pode usar várias páginas; domínio e páginas confirmadas ajudam a localizar seus anúncios. Homônimos devem ser excluídos.
- Restrições de anúncio, conta ou página precisam ser sustentadas pelos campos retornados. Ausência de mídia, isoladamente, não comprova remoção nem decisão do anunciante. Mostrar a situação informada pela Meta em seu campo próprio.
- Correções evidentes de transcrição vão em `grupos.json`, após conferir a fonte, e são aplicadas ao texto sem reescrever a mensagem.
