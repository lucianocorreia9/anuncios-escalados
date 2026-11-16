# Anúncios Escalados

Descubra quais vídeos um concorrente mais repete na Biblioteca de Anúncios da Meta e reúna os criativos, as transcrições e os sinais de escala em uma planilha. Skill da Hapogeu Digital para Claude Code e Codex, com foco em anúncios no Brasil.

## O que você recebe

- Uma planilha Excel (`.xlsx`) por concorrente, com painel, grupos de ganchos e links para os anúncios originais.
- Até 15 vídeos visualmente distintos na primeira entrega, com MP4, imagem do vídeo e transcrição em português. O ranking prioriza cópias do próprio vídeo, dias no ar e anúncios ativos.
- Uma pasta `criativos/` ao lado da planilha. Preserve as duas juntas para abrir os vídeos a partir dela.

Cópias e dias no ar são sinais indiretos. A pesquisa depende do que a Biblioteca retorna e a Meta pode omitir mídias. Quando faltarem vídeos verificáveis, a planilha indica quantos ficaram pendentes.

## Instalação

### 1. Baixe a skill

```bash
git clone https://github.com/lucianocorreia9/anuncios-escalados.git
cd anuncios-escalados
```

Você também pode usar **Code → Download ZIP** no GitHub, extrair e abrir a pasta extraída no terminal.

### 2. Copie para o seu assistente

**Claude Code**

```bash
mkdir -p "$HOME/.claude/skills"
cp -R skills/anuncios-escalados "$HOME/.claude/skills/"
```

Abra uma nova sessão e digite `/anuncios-escalados`. [Guia do Claude Code](https://code.claude.com/docs/en/skills)

**Codex**

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/anuncios-escalados "$HOME/.agents/skills/"
```

Abra uma nova sessão e mencione `$anuncios-escalados`. Se a skill ainda não aparecer, reinicie o Codex. [Guia do Codex](https://learn.chatgpt.com/docs/build-skills)

Os comandos instalam a skill para todos os seus projetos. Para instalar em um projeto só, use `.claude/skills/` ou `.agents/skills/` na pasta desse projeto. Ao atualizar, mova a instalação anterior para fora da pasta de skills antes de copiar a nova.

### 3. Prepare o ambiente

Os comandos deste guia usam um terminal Bash ou Zsh em macOS ou Linux. No Windows, use o ambiente Linux do WSL com o assistente e as ferramentas instalados nele.

- Instale [uv](https://docs.astral.sh/uv/getting-started/installation/) para baixar o Python 3.13 e as bibliotecas usadas pela skill.
- Instale [FFmpeg](https://ffmpeg.org/download.html) para ler e conferir vídeos. Verifique no terminal com `ffmpeg -version`.
- Crie sua chave na [ScrapeCreators](https://scrapecreators.com/). A sondagem e a coleta usam créditos. A skill pede aprovação antes de cada rodada de consultas. [Documentação do serviço](https://docs.scrapecreators.com/v1/facebook/adlibrary/search/ads/)

Para usar a chave somente na sessão atual de terminal, cole os comandos abaixo e depois digite a chave no campo oculto. Inicie o Claude Code ou o Codex a partir desse terminal.

```bash
printf '%s' 'Chave da ScrapeCreators: '
IFS= read -r -s SCRAPECREATORS_API_KEY
printf '\n'
export SCRAPECREATORS_API_KEY
```

Se abrir o assistente pelo aplicativo, crie a configuração na sua pasta pessoal.

```bash
umask 077
mkdir -p "$HOME/.config/anuncios-escalados"
nano "$HOME/.config/anuncios-escalados/.env"
```

No arquivo, coloque `SCRAPECREATORS_API_KEY=SUA_CHAVE` e substitua `SUA_CHAVE` pela sua chave. Mantenha esse arquivo na pasta pessoal. A transcrição roda no computador com [faster-whisper](https://github.com/SYSTRAN/faster-whisper) e pode baixar o modelo de voz no primeiro uso.

## Primeira pesquisa

Abra o assistente na pasta em que você quer trabalhar. Troque `<site-do-concorrente>` pelo site real.

| Assistente | Mensagem |
| --- | --- |
| Claude Code | `/anuncios-escalados Pesquise <site-do-concorrente> e mostre o custo antes de usar créditos.` |
| Codex | `$anuncios-escalados Pesquise <site-do-concorrente> e mostre o custo antes de usar créditos.` |

Você também pode informar um perfil do Instagram, uma página do Facebook, um produto ou um nicho. Se informar só o nicho, a skill começa pela pesquisa de concorrentes e pede que você escolha quem entra na coleta. Por padrão, a entrega fica em `pesquisas-meta/` na pasta do projeto.

## Teste local sem créditos

Na pasta baixada do GitHub, com FFmpeg disponível, rode a verificação com vídeos e dados gerados para teste.

```bash
uv run --no-project --python 3.13 --with openpyxl --with pillow python -m unittest discover -s tests
```

As [instruções da skill](skills/anuncios-escalados/SKILL.md) descrevem o fluxo completo.
