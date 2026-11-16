# Como agrupar os criativos por gancho

## Materiais

Ler `para-agrupar.md`, `criativos.json`, `aberturas.json`, `medidas.json`, as capas em `capas/` e os quadros em `frames/`. A ordem é por cópias, com tempo histórico e ativos como desempate.

Códigos `V` identificam vídeos, `I` imagens e `T` texto sem mídia. O número no código é a duração medida na identificação original; sufixos distinguem vídeos com a mesma duração. Preservar códigos já entregues ao atualizar a pesquisa.

## Antes de agrupar: conferir vídeos diferentes

Duração e capa isoladas não comprovam igualdade nem diferença. O medidor extrai cinco quadros: até dois, oito e quatorze segundos, ajustados para vídeos curtos, e pontos no meio e perto do final. Assim, comparar também o corpo, pois dois vídeos podem abrir igual e seguir com conteúdos diferentes. A máquina sugere igualdade; o agente confere os prints, o movimento e a abertura.

Comparar também candidatos com duração próxima, outra capa, enquadramento diferente ou recompressão. Se os quadros forem genéricos, iguais ou insuficientes, assistir a outros pontos do vídeo antes de decidir. Arquivos diferentes do mesmo conteúdo somam cópias do mesmo criativo; outra encenação ou edição relevante pode ser outro criativo dentro do mesmo gancho.

Registrar revisões em `revisao-visual.json`, com evidência e códigos. Para juntar duplicatas antes da primeira entrega, o medidor aceita:

```json
{
  "mesclar": [
    {
      "manter": "V60.00",
      "duplicado": "V60.04",
      "evidencia": "Mesma fala, encenação e sequência de quadros em três momentos; só mudou a compressão."
    }
  ]
}
```

Depois de rever os candidatos, aplicar a fusão antes de concluir `grupos.json`, recontando os anúncios sem duplicar IDs. Atualizar pré-grupos e aberturas correspondentes. Depois que um código já foi entregue, conciliar a revisão pontualmente na mesma planilha, preservando a identidade dos códigos antigos; não rodar uma reidentificação que os troque silenciosamente.

## O que é um gancho

Um grupo corresponde à **ideia dos primeiros 16 segundos**, sem exigir texto idêntico. “Tenho 50 mil guardados, onde invisto?” e “Estou com 30 mil na poupança, o que faço?” podem ser o mesmo gancho. Um terceiro apresentando o especialista pode ser outro grupo.

Os pré-grupos por palavras são sugestões: juntar os que têm a mesma ideia e separar quando misturam ganchos. Referência direta ao código do criativo prevalece sobre o pré-grupo.

Nomear pelo que é dito ou mostrado, como `“Quanto rende X mil?”`, e usar um tipo curto, como Pergunta do seguidor, Prova de terceiro, História, Tutorial, Inimigo, Mecanismo, Medo de perder, Notícia, Autoridade ou Oferta direta. Não inventar intenção que o vídeo não sustenta.

Vídeos diferentes podem compartilhar gancho. Quantidade de vídeos diferentes e quantidade de ganchos são métricas distintas. Imagens e carrosséis sem vídeo ficam em grupos próprios, como `Imagem: convite para aula`. Vídeos sem fala exigem assistir aos quadros e ler o texto na tela; uma capa isolada não basta.

## Gravação e conferência

Gravar `grupos.json`:

```json
{
  "correcoes": [["constorias", "consultorias"]],
  "grupos": [
    {
      "nome": "Quanto rende X mil?",
      "tipo": "Pergunta do seguidor",
      "itens": ["P2", "P9", "V33.10"]
    }
  ]
}
```

As correções precisam ser sustentadas pelo áudio ou pelas legendas e específicas o bastante para não alterar palavras indevidas. São aplicadas às aberturas e aos roteiros.

Rodar `uv run --no-project --python 3.13 python agrupar.py conferir --apelido <apelido>` até `CONFERÊNCIA OK`: cada criativo em exatamente um grupo, todos com nome e tipo, sem nomes repetidos. A ordem do JSON não define o ranking: mais cópias vêm primeiro, com tempo histórico, ativos e posição da busca como desempate.

Concluído o agrupamento, selecionar os 15 vídeos distintos do ranking geral, por cópias, tempo no ar e ativos. A mesma fala ou gancho pode aparecer em várias linhas quando cenário, roupa, gravação ou imagens da edição comprovarem vídeos diferentes. Sem quadros suficientes para distinguir um candidato, verificar mais pontos antes de validar. Grupos só de imagem ou texto ficam fora dos roteiros em vídeo. Nova coleta paga para preencher o lote depende de aprovação prévia de créditos.

Se houver ajudante autorizado, devolver o caminho do JSON, a quantidade de grupos e os cinco com mais cópias, com seus ativos e tempo histórico.
