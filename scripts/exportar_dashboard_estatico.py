#!/usr/bin/env python3
"""Gera um snapshot ESTATICO e FIEL do dashboard: o mesmo HTML/CSS/JS do Flask,
com as respostas de API embutidas e um interceptador de fetch(). Abre offline, em
qualquer navegador, sem servidor e sem banco.

Privacidade / escopo:
  - A aba Indicadores (operacional) e REMOVIDA: botao, painel e chamadas do init.
    Os endpoints /api/dashboard, /api/meses e /api/interacoes-categorias NAO sao
    embutidos, entao esses dados nunca entram no HTML.
  - A aba Historico (dados por chamado) recebe payload vazio e uma nota.
  - A simulacao ao vivo (Azure OpenAI) fica indisponivel.
  - So agregados publicaveis sao embutidos.
Fontes carregam do Google Fonts quando online (igual ao Flask), com fallback do
sistema offline.

Uso (a partir da pasta do projeto):
    python scripts/exportar_dashboard_estatico.py
Saida:
    resultados_publicaveis/RESULTADO_DASHBOARD.html
"""
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard"
STATIC = DASH / "static"
sys.path.insert(0, str(DASH))
sys.path.insert(0, str(ROOT / "scripts"))
import app as dash  # noqa: E402

# Somente agregados usados pelas abas que ficam (Tipos Sugeridos, Previa do Portal
# e os cards de grupos do Historico). Endpoints operacionais da aba Indicadores
# (/api/dashboard, /api/meses, /api/interacoes-categorias) NAO entram.
AGREGADOS = [
    "/api/mapeamento-detalhado",
    "/api/analise-resumo",
    "/api/analise-clusters",
]

# Chamadas de init que pertencem a aba Indicadores (removidas do script congelado).
INIT_INDICADORES = ("initFiltroMes", "loadDash", "loadInteracoes")

NOTA_HISTORICO = (
    '<div style="background:rgba(253,219,81,.14);border:1px solid rgba(253,219,81,.5);'
    'border-radius:8px;padding:.7rem 1rem;font-size:.83rem;color:#0a2540;margin:.5rem 0 1rem;">'
    'Registro estático: a lista de chamados individuais foi omitida por conter dados por '
    'chamado. O catálogo e os grupos (agregados, sem dados pessoais) estão completos '
    'nas demais abas.</div>'
)

SHIM_JS = r'''(function(){
var BAKED=__BAKED__;
function R(o,ok){ok=ok!==false;return Promise.resolve({ok:ok,status:ok?200:404,json:function(){return Promise.resolve(o);},text:function(){return Promise.resolve(JSON.stringify(o));}});}
window.fetch=function(url,opts){try{
var u=String(url);var path=u.split('?')[0].replace(/^https?:\/\/[^/]+/,'');
if(path==='/api/historico'){return R({total:0,page:1,limit:50,tickets:[],tem_dados_pipeline:true,fonte:'snapshot'});}
if(path==='/api/simular-openai'){return R({erro:'Simulacao ao vivo indisponivel neste registro estatico (requer Azure OpenAI).'});}
if(Object.prototype.hasOwnProperty.call(BAKED,path)){return R(BAKED[path]);}
return R({},false);
}catch(e){return R({},false);}};
})();'''


def _safe_json(obj) -> str:
    # JSON e JS valido; escapa </ para nao fechar o <script> por engano.
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build() -> str:
    with dash.app.test_client() as c:
        shell = c.get("/").get_data(as_text=True)
        baked = {ep: c.get(ep).get_json() for ep in AGREGADOS}
        baked["/api/openai-status"] = {"disponivel": False, "modelo": None}

    css = (STATIC / "style.css").read_text(encoding="utf-8")
    vendor = (STATIC / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")
    scriptjs = (STATIC / "script.js").read_text(encoding="utf-8")
    # Remove as chamadas de init da aba Indicadores (a aba nao existe no snapshot).
    for chamada in INIT_INDICADORES:
        scriptjs = re.sub(r"(?m)^\s*" + chamada + r"\(\);\s*$", "", scriptjs)
    logo_b64 = base64.b64encode((STATIC / "img" / "fgv-logo.png").read_bytes()).decode()

    shim = "<script>\n" + SHIM_JS.replace("__BAKED__", _safe_json(baked)) + "\n</script>"

    html = shell
    html = re.sub(
        r'<link rel="stylesheet" href="/static/style\.css[^"]*">',
        lambda _: "<style>\n" + css + "\n</style>",
        html, count=1,
    )
    html = re.sub(
        r'src="/static/img/fgv-logo\.png[^"]*"',
        lambda _: 'src="data:image/png;base64,' + logo_b64 + '"',
        html, count=1,
    )
    html = re.sub(
        r'<script src="/static/vendor/chart\.umd\.min\.js[^"]*"></script>',
        lambda _: "<script>\n" + vendor + "\n</script>",
        html, count=1,
    )
    html = re.sub(
        r'<script src="/static/script\.js[^"]*"></script>',
        lambda _: shim + "\n<script>\n" + scriptjs + "\n</script>",
        html, count=1,
    )
    # Remove a aba Indicadores (operacional): botao de navegacao e painel inteiro.
    html = re.sub(
        r"\s*<button class=\"nav-btn\" onclick=\"switchTab\('dashboard',this\)\">Indicadores</button>",
        "", html, count=1,
    )
    html = re.sub(
        r'<section id="dashboard" class="tab-content">.*?</section>',
        "", html, count=1, flags=re.DOTALL,
    )
    # Nota de privacidade no Historico.
    html = html.replace(
        "<h2>Histórico de Chamados</h2>",
        "<h2>Histórico de Chamados</h2>\n" + NOTA_HISTORICO,
        1,
    )
    # Mantém o artefato compatível com `git diff --check`, inclusive depois de
    # remover seções inteiras por regex.
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"


def main() -> int:
    html = build()
    out = ROOT / "resultados_publicaveis" / "RESULTADO_DASHBOARD.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("[OK] snapshot fiel gerado:", out)
    print("     tamanho:", f"{len(html):,}", "chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
