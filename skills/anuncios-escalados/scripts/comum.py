"""
comum.py: peças compartilhadas pelos programas da skill anuncios-escalados.

Só usa a biblioteca padrão e roda do Python 3.9 em diante, porque o transcrever.py roda no
Python do faster-whisper (o 3.9 da Apple) e importa este arquivo.

Pasta de trabalho de cada concorrente: ~/.cache/anuncios-escalados/<apelido>/
  meta.json         quem é o concorrente, como foi buscado, quando, quanto gastou
  bruto.json        tudo o que a biblioteca devolveu (sem repetição)
  anuncios.json     o que ficou depois do filtro (é o que vai para a planilha)
  fora.json         o que foi separado pelo filtro, com o motivo
  consultas.jsonl   uma linha por consulta paga feita à ScrapeCreators
  medidas.json      duração, capa e chave de criativo de cada anúncio
  criativos.json    cada criativo diferente (vídeo, imagem ou só texto) e seus anúncios
  aberturas.json    transcrição dos 16 s iniciais de cada vídeo
  roteiros.json     transcrição completa dos vídeos escolhidos
  grupos.json       os grupos de gancho (escrito pelo agente)
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.scrapecreators.com/v1/facebook/adLibrary/"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or "~/.cache").expanduser() / "anuncios-escalados"

NIVEIS = [
    "1. Campeão (ativo há 90+ dias)",
    "2. Escalando (ativo há 30 a 89 dias)",
    "3. Em teste (ativo há menos de 30 dias)",
    "4. Já foi campeão (pausado, rodou 90+ dias)",
    "5. Rodou e parou (pausado, 30 a 89 dias)",
    "6. Descartado cedo (pausado, menos de 30 dias)",
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def ffmpeg() -> str:
    executavel = shutil.which("ffmpeg")
    if not executavel:
        sys.exit("FFmpeg não encontrado. Instale o FFmpeg e confira com ffmpeg -version.")
    return executavel


# ---------------------------------------------------------------- pasta de trabalho
def pasta(apelido: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", apelido):
        sys.exit("Use apenas letras minúsculas sem acento, números e hífens no apelido.")
    p = os.path.join(CACHE, apelido)
    os.makedirs(p, exist_ok=True)
    return p


def ler(p: str, arquivo: str, padrao=None):
    f = os.path.join(p, arquivo)
    if not os.path.exists(f):
        return padrao
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def gravar(p: str, arquivo: str, obj) -> None:
    f = os.path.join(p, arquivo)
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    os.replace(tmp, f)


# ---------------------------------------------------------------- ScrapeCreators
def chave() -> str:
    k = os.environ.get("SCRAPECREATORS_API_KEY", "").strip()
    env = Path("~/.config/anuncios-escalados/.env").expanduser()
    if not k and env.is_file():
        for linha in env.read_text(encoding="utf-8").splitlines():
            nome, _, valor = linha.partition("=")
            if nome == "SCRAPECREATORS_API_KEY":
                k = valor.strip().strip("\"'")
                break
    if not k:
        sys.exit("Configure SCRAPECREATORS_API_KEY ou ~/.config/anuncios-escalados/.env.")
    return k


class ParadaNaAPI(Exception):
    """Falha em uma consulta que pode ter consumido créditos."""


def chamar(p: str, endpoint: str, params: dict) -> dict:
    """Envia uma única consulta paga e registra os créditos informados."""
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-api-key": chave()})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise ParadaNaAPI(f"ScrapeCreators retornou HTTP {e.code}. Confira o saldo antes de repetir.") from None
    except (OSError, ValueError) as e:
        raise ParadaNaAPI(f"Consulta sem resposta utilizável ({type(e).__name__}). Confira o saldo antes de repetir.") from None
    if not isinstance(d, dict):
        raise ParadaNaAPI("Resposta inesperada. Confira o saldo antes de repetir.")
    with open(os.path.join(p, "consultas.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "quando": dt.datetime.now().isoformat(timespec="seconds"),
            "endpoint": endpoint, "params": params,
            "cobrado": d.get("credits_charged"), "restantes": d.get("credits_remaining"),
        }, ensure_ascii=False) + "\n")
    if d.get("success") is False:
        raise ParadaNaAPI("ScrapeCreators informou falha. Confira o saldo antes de repetir.")
    return d


def consultas_gastas(p: str) -> tuple:
    """(quantas consultas este concorrente já gastou, saldo restante na última)"""
    f = os.path.join(p, "consultas.jsonl")
    if not os.path.exists(f):
        return 0, None
    n, resto = 0, None
    for linha in open(f, encoding="utf-8"):
        d = json.loads(linha)
        n += 1 if d.get("cobrado") is None else d["cobrado"]
        resto = d.get("restantes", resto)
    return n, resto


def estimar_consultas(total: int) -> int:
    """A busca devolve uns 30 anúncios na 1ª página e 10 nas seguintes."""
    if total <= 30:
        return 1
    return 1 + -(-(total - 30) // 10)


# ---------------------------------------------------------------- datas e escala
def data(ts) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc)


def momento_coleta(p: str) -> dt.datetime:
    m = ler(p, "meta.json", {})
    return dt.datetime.fromisoformat(m["coleta"]) if m.get("coleta") else dt.datetime.now(dt.timezone.utc)


def fim(r: dict, T: dt.datetime) -> dt.datetime:
    if r.get("is_active") or not r.get("end_date"):
        return T
    return data(r["end_date"])


def dias_no_ar(r: dict, T: dt.datetime) -> int:
    return (fim(r, T) - data(r["start_date"])).days + 1


def nivel(dias_ativo: int, tem_ativo: bool, maior: int) -> str:
    if tem_ativo:
        return NIVEIS[0] if dias_ativo >= 90 else NIVEIS[1] if dias_ativo >= 30 else NIVEIS[2]
    return NIVEIS[3] if maior >= 90 else NIVEIS[4] if maior >= 30 else NIVEIS[5]


def resumir(rs: list, T: dt.datetime) -> dict:
    """Números de escala de um conjunto de anúncios (um vídeo, um grupo)."""
    ativos = [r for r in rs if r.get("is_active")]
    d_ativo = max((dias_no_ar(r, T) for r in ativos), default=0)
    maior = max(dias_no_ar(r, T) for r in rs)
    primeiro = min(data(r["start_date"]) for r in rs)
    ultimo = max(fim(r, T) for r in rs)
    melhor = min(rs, key=lambda r: r.get("_rank", 10**9))
    nv = nivel(d_ativo, bool(ativos), maior)
    return {
        "nivel": nv, "ni": NIVEIS.index(nv), "ativos": len(ativos), "dias_ativo": d_ativo,
        "maior": maior, "uso": (ultimo - primeiro).days + 1, "n": len(rs),
        "rank": melhor.get("_rank"), "melhor": melhor, "primeiro": primeiro,
        "ultimo": "no ar hoje" if ativos else ultimo.strftime("%d/%m/%Y"),
        "paginas": len({r["snapshot"].get("page_name") for r in rs}),
    }


def ordem_escala(a: dict) -> tuple:
    """Mais cópias primeiro; histórico, ativos e posição da busca desempatam."""
    return (-a["n"], -a["maior"], -a["ativos"], a["rank"] or 10**9)


def ordem_roteiros(a: dict) -> tuple:
    """Ordem global dos vídeos por cópias, tempo no ar e anúncios ativos."""
    return (-a["n"], -a["maior"], -a["ativos"])


# ---------------------------------------------------------------- anúncio
def midia(r: dict) -> dict:
    """Vídeo, capa e formato do anúncio (olha também o 1º cartão de carrossel)."""
    s = r["snapshot"]
    v = (s.get("videos") or [{}])[0] or {}
    cards = s.get("cards") or []
    c = cards[0] if cards else {}
    video = v.get("video_sd_url") or v.get("video_hd_url") or c.get("video_sd_url") or c.get("video_hd_url")
    capa = v.get("video_preview_image_url") or c.get("video_preview_image_url")
    if not capa:
        imgs = s.get("images") or []
        if imgs:
            capa = imgs[0].get("original_image_url") or imgs[0].get("resized_image_url")
        elif c:
            capa = c.get("original_image_url") or c.get("resized_image_url")
    fmt = {"VIDEO": "Vídeo", "IMAGE": "Imagem", "CAROUSEL": "Carrossel", "DCO": "Dinâmico"}.get(s.get("display_format") or "", "Outro")
    if video and fmt in ("Outro", "Dinâmico"):
        fmt = "Vídeo"
    if not video and not capa and r.get("gated_type") == "TAKEN_DOWN":
        fmt = "Retirado pela Meta"
    return {"video": video, "capa": capa, "formato": fmt}


SITUACAO_META = {
    "ELIGIBLE": "Normal",
    "TAKEN_DOWN": "Derrubado pela Meta",
    "AD_ACCOUNT_DISABLED": "Conta de anúncios desativada",
    "PAGE_DISABLED": "Página desativada",
}


def situacao_meta(r: dict) -> str:
    g = r.get("gated_type")
    return SITUACAO_META.get(g, g or "Normal")


def bloqueado(r: dict) -> bool:
    """Saiu do ar por ação da Meta (anúncio, conta ou página), não por decisão do anunciante."""
    return situacao_meta(r) != "Normal"


def texto(r: dict) -> str:
    s = r["snapshot"]
    t = (s.get("body") or {}).get("text") or ""
    if not t and s.get("cards"):
        t = s["cards"][0].get("body") or ""
    return " ".join(t.split())


RASTREIO = {"fbclid", "gclid", "ttclid", "xcod", "sck", "src", "ref", "_hsenc", "_hsmi", "mc_cid", "mc_eid"}


def destino(r: dict) -> str:
    """Endereço completo da página de destino, sem os códigos de rastreio (utm, fbclid...).
    O resto fica: no WhatsApp, por exemplo, o número do telefone está depois do '?'."""
    s = r["snapshot"]
    u = (s.get("link_url") or "").strip()
    if not u and s.get("cards"):
        u = (s["cards"][0].get("link_url") or "").strip()
    if not u:
        return ""
    if not u.startswith("http"):
        u = "https://" + u.lstrip("/")
    sp = urllib.parse.urlsplit(u.split("#")[0])
    q = [(k, v) for k, v in urllib.parse.parse_qsl(sp.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in RASTREIO]
    if "whatsapp" in sp.netloc or "wa.me" in sp.netloc:
        q = [(k, v) for k, v in q if k == "phone"]  # a mensagem pronta é longa e não identifica o destino
    caminho = sp.path.rstrip("/") if sp.path.count("/") > 1 else sp.path
    return urllib.parse.urlunsplit((sp.scheme, sp.netloc, caminho, urllib.parse.urlencode(q), ""))
