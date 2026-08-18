#!/usr/bin/env python3
"""
Generador de sitio estático para Enfoque Mundial.

Convierte data/news.json en páginas HTML REALES (contenido presente en el
HTML, no insertado después por JavaScript), para que Google pueda rastrear
e indexar cada noticia, categoría y autor sin depender de que se ejecute JS.

Genera:
  /<categoria-slug>/<articulo-slug>/index.html   (artículo individual)
  /<categoria-slug>/index.html                    (listado de categoría)
  /autor/<autor-slug>/index.html                  (página de autor)
  /index.html                                     (portada, regenerada)
  /sitemap.xml                                    (con las URLs limpias)

Uso:
  python3 scripts/generate_site.py                 -> regenera TODO el sitio
  (se importa también desde auto_publish.py para regenerar solo lo afectado
   por una noticia nueva, sin tener que reconstruir todo cada vez)
"""

import json
import os
import re
import subprocess
import unicodedata
from datetime import datetime, timezone

SITE_URL = "https://enfoquemundial.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_PATH = os.path.join(ROOT, "data", "news.json")
GITHUB_OWNER = "enfoquemundial"
GITHUB_REPO = "enfoquemundial"

AUTHOR_BIOS = {
    "Esfrailin Quezada": "Redactor de Enfoque Mundial, cubre tecnología, economía y actualidad internacional.",
    "Irelsa Nuñez": "Redactora de Enfoque Mundial, especializada en política internacional y sociedad.",
    "Redacción": "Equipo editorial de Enfoque Mundial.",
}

# Umbral mínimo de artículos para que una página de categoría/autor se deje
# indexable. Por debajo de esto, se marca noindex y se excluye del sitemap
# (una página con 1 solo artículo se ve como contenido pobre para Google).
MIN_ARTICLES_CATEGORY_INDEXABLE = 3
MIN_ARTICLES_AUTHOR_INDEXABLE = 2

# Marcadores de contenido de plantilla / relleno que NUNCA deben llegar a publicarse
TEMPLATE_MARKERS = [
    "Título\n", "\nTítulo\n", "Categoría\n", "\nCategoría\n",
    "Desarrollo de la noticia", "no inventada",
    "Escribe aquí", "Lorem ipsum", "PLACEHOLDER", "[PLACEHOLDER]", "TODO:",
]

VALID_CATEGORIES = {"Mundo", "Politica", "Politica internacional", "Tecnología",
                     "Finanzas", "Deportes", "Cultura", "Videojuegos"}


class ArticleValidationError(Exception):
    pass


def validate_article(n):
    """Valida los requisitos mínimos antes de generar/publicar un artículo.
    Lanza ArticleValidationError con el motivo si algo no cumple — el llamador
    decide si eso significa abortar la publicación (auto_publish.py) o solo
    saltarse ese artículo al reconstruir todo el sitio (build_all)."""
    if not n.get("title", "").strip():
        raise ArticleValidationError(f"id={n.get('id')}: título vacío")
    if not n.get("content", "").strip():
        raise ArticleValidationError(f"id={n.get('id')}: contenido vacío")
    if len(n.get("content", "").split()) < 100:
        raise ArticleValidationError(f"id={n.get('id')}: contenido demasiado corto (<100 palabras)")
    if n.get("category") not in VALID_CATEGORIES:
        raise ArticleValidationError(f"id={n.get('id')}: categoría inválida '{n.get('category')}'")
    if not n.get("author", "").strip():
        raise ArticleValidationError(f"id={n.get('id')}: autor vacío")
    if not n.get("date"):
        raise ArticleValidationError(f"id={n.get('id')}: fecha vacía")
    try:
        datetime.fromisoformat(n["date"].replace("Z", "+00:00"))
    except Exception:
        raise ArticleValidationError(f"id={n.get('id')}: fecha inválida '{n.get('date')}'")
    images = n.get("images", [])
    if not images or not isinstance(images, list) or not images[0].strip():
        raise ArticleValidationError(f"id={n.get('id')}: sin imagen válida")
    if not str(n.get("id", "")).strip():
        raise ArticleValidationError("artículo sin id")
    for marker in TEMPLATE_MARKERS:
        if marker in n["title"] or marker in n["content"]:
            raise ArticleValidationError(
                f"id={n.get('id')}: contiene texto de plantilla ('{marker.strip()}') — no se publica"
            )
    return True


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text or "articulo"


def category_slug(category):
    return slugify(category)


def load_news():
    with open(NEWS_PATH, encoding="utf-8") as f:
        return json.load(f)


# --- Fragmentos de plantilla compartidos (mismo diseño/branding actual) ---

def head(title, description, canonical_url, og_type="website", og_image="", extra_ld="", noindex=False):
    og_image_tag = f'\n    <meta property="og:image" content="{og_image}">' if og_image else ""
    robots = "noindex, follow" if noindex else "index, follow"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="{rel(canonical_url)}logo/favicon.svg">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta name="robots" content="{robots}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="{og_type}">
    <meta property="og:locale" content="es_DO">
    <meta property="og:url" content="{canonical_url}">{og_image_tag}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{description}">
    <link rel="canonical" href="{canonical_url}">
    {extra_ld}
    <!-- Consentimiento de cookies: por defecto todo denegado hasta que el
         visitante elija — Google Consent Mode. Debe ir ANTES de cargar gtag. -->
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag("consent", "default", {{
            "ad_storage": "denied",
            "analytics_storage": "denied",
            "ad_user_data": "denied",
            "ad_personalization": "denied"
        }});
    </script>
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-JGGDQ7PN0E"></script>
    <script>
        gtag("js", new Date());
        gtag("config", "G-JGGDQ7PN0E");
    </script>

    <!-- Google AdSense — código de verificación y anuncios -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5715984507479482"
     crossorigin="anonymous"></script>

    <link rel="stylesheet" href="{rel(canonical_url)}css/tailwind.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest" defer></script>
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        .font-serif {{ font-family: 'Playfair Display', serif; }}
        .logo-nav img {{ height: 80px; width: auto; }}
    </style>
</head>
<body class="bg-white text-gray-900">
<div class="h-1 bg-black"></div>
"""


def rel(canonical_url):
    """Cuántos niveles hay que subir (../) según la profundidad de la URL, para enlazar bien css/logo."""
    path = canonical_url.replace(SITE_URL, "").strip("/")
    if not path:
        return ""
    depth = path.count("/") + 1
    return "../" * depth


CATEGORY_DISPLAY_NAMES = {
    "Mundo": "Mundo",
    "Politica": "Política",
    "Politica internacional": "Política Internacional",
    "Tecnología": "Tecnología",
    "Finanzas": "Finanzas",
    "Deportes": "Deportes",
    "Cultura": "Cultura",
    "Videojuegos": "Videojuegos",
}


def category_nav_bar(news, canonical_url):
    """Barra de categorías fija debajo del header, con scroll horizontal en
    móvil. Se muestran ordenadas por cuál tuvo publicación más reciente
    primero (las categorías "más activas" quedan al frente)."""
    if not news:
        return ""
    cats = sorted(set(a["category"] for a in news))
    last_date = {c: max(a["date"] for a in news if a["category"] == c) for c in cats}
    cats.sort(key=lambda c: last_date[c], reverse=True)
    links = "".join(
        f'<a href="{category_url(c)}" class="text-xs font-bold uppercase tracking-wide text-gray-600 hover:text-blue-600 whitespace-nowrap transition-colors">{esc(CATEGORY_DISPLAY_NAMES.get(c, c))}</a>'
        for c in cats
    )
    return f"""
<div class="bg-white border-b border-gray-100">
    <div class="max-w-7xl mx-auto px-4">
        <div class="flex items-center gap-6 overflow-x-auto py-3 no-scrollbar">
            {links}
        </div>
    </div>
</div>
"""


def nav(canonical_url, news=None):
    home = rel(canonical_url) + "index.html" if rel(canonical_url) else "index.html"
    login = rel(canonical_url) + "admin/login/index.html" if rel(canonical_url) else "admin/login/index.html"
    return f"""
<nav class="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-gray-100 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 h-28 grid grid-cols-3 items-center">
        <div class="flex justify-start">
            <div class="logo-nav cursor-pointer" onclick="location.href='{home}'">
                <img src="{rel(canonical_url)}logo/logo vectorizado.svg" alt="Enfoque Mundial">
            </div>
        </div>
        <div class="flex justify-center">
            <div class="relative group w-full max-w-xs">
                <input type="text" id="searchInput" onkeyup="if(event.key==='Enter')searchNews()" placeholder="Buscar..." class="bg-gray-50 rounded-full py-2 px-10 text-xs w-full transition-all outline-none border border-transparent focus:border-black text-center focus:bg-white shadow-sm">
                <i data-lucide="search" class="absolute left-4 top-2.5 w-4 h-4 text-gray-400 group-focus-within:text-black"></i>
            </div>
        </div>
        <div class="flex justify-end items-center gap-6">
            <span id="current-date" class="hidden lg:block text-[10px] font-bold uppercase tracking-widest text-gray-400 text-right"></span>
            <button onclick="location.href='{login}'" class="text-gray-400 hover:text-black transition-colors">
                <i data-lucide="user" class="w-6 h-6"></i>
            </button>
        </div>
    </div>
    {category_nav_bar(news, canonical_url)}
</nav>
<style>.no-scrollbar::-webkit-scrollbar {{ display: none; }} .no-scrollbar {{ -ms-overflow-style: none; scrollbar-width: none; }}</style>
"""


def breadcrumbs(items, canonical_url):
    """items: lista de (nombre, url_absoluta_o_None_si_actual)"""
    parts = []
    for name, url in items:
        if url:
            parts.append(f'<a href="{url}" class="hover:text-black">{esc(name)}</a>')
        else:
            parts.append(f'<span class="text-gray-800 font-medium">{esc(name)}</span>')
    html = " <span class='mx-1 text-gray-300'>/</span> ".join(parts)
    return f'<nav class="max-w-7xl mx-auto px-4 pt-6 text-xs text-gray-400">{html}</nav>'


def breadcrumb_ld(items):
    els = []
    for i, (name, url) in enumerate(items, start=1):
        item = {"@type": "ListItem", "position": i, "name": name}
        if url:
            item["item"] = url
        els.append(item)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": els}


def footer(canonical_url):
    r = rel(canonical_url)
    return f"""
<footer class="bg-gray-900 text-gray-300 mt-20">
    <div class="max-w-7xl mx-auto px-4 py-14">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-10 mb-10">
            <div>
                <img src="{r}logo/logo vectorizado.svg" class="h-10 mb-4 brightness-0 invert opacity-80" alt="Enfoque Mundial">
                <p class="text-sm text-gray-400 leading-relaxed">Periodismo global con perspectiva. Información verificada, análisis profundo y cobertura internacional.</p>
            </div>
            <div>
                <h4 class="text-white font-bold uppercase tracking-widest text-xs mb-4">El Medio</h4>
                <ul class="space-y-2 text-sm">
                    <li><a href="{r}sobre-nosotros.html" class="hover:text-white transition-colors">Sobre Nosotros</a></li>
                    <li><a href="{r}contacto.html" class="hover:text-white transition-colors">Contacto</a></li>
                    <li><a href="{r}index.html" class="hover:text-white transition-colors">Inicio</a></li>
                </ul>
            </div>
            <div>
                <h4 class="text-white font-bold uppercase tracking-widest text-xs mb-4">Legal</h4>
                <ul class="space-y-2 text-sm">
                    <li><a href="{r}privacidad.html" class="hover:text-white transition-colors">Política de Privacidad</a></li>
                    <li><a href="{r}terminos.html" class="hover:text-white transition-colors">Términos y Condiciones</a></li>
                </ul>
            </div>
        </div>
        <div class="border-t border-gray-700 pt-8 text-center text-xs text-gray-500">
            <p>&copy; <span id="copyright-year">2026</span> Enfoque Mundial &middot; Todos los derechos reservados &middot; <a href="{r}privacidad.html" class="hover:text-white">Privacidad</a> &middot; <a href="{r}terminos.html" class="hover:text-white">Términos</a></p>
        </div>
    </div>
</footer>

<div id="cookie-banner" class="fixed bottom-0 left-0 right-0 z-[100] bg-white border-t border-gray-200 shadow-[0_-4px_20px_rgba(0,0,0,0.1)] p-5 hidden">
    <div class="max-w-4xl mx-auto flex flex-col md:flex-row items-center gap-4">
        <p class="text-sm text-gray-600 flex-1">
            Usamos cookies propias y de terceros (como Google Analytics) para analizar el uso del sitio. Puedes aceptarlas o rechazarlas — las esenciales para que el sitio funcione se mantienen siempre activas.
            <a href="{r}privacidad.html" class="text-blue-600 hover:underline">Más información</a>
        </p>
        <div class="flex gap-2 flex-shrink-0">
            <button onclick="rejectCookies()" class="px-4 py-2 text-sm font-semibold text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Rechazar</button>
            <button onclick="acceptCookies()" class="px-4 py-2 text-sm font-semibold text-white bg-black rounded-lg hover:bg-gray-800 transition-colors">Aceptar</button>
        </div>
    </div>
</div>
<script src="{r}js/app.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    lucide.createIcons();
    document.getElementById('current-date').innerText = new Date().toLocaleDateString('es-ES', {{ weekday: 'long', day: 'numeric', month: 'long' }});
    document.getElementById("copyright-year").textContent = new Date().getFullYear();
    initCookieBanner();
}});
function searchNews() {{
    const q = document.getElementById('searchInput').value.trim();
    if (!q) return;
    location.href = '{r}buscar/index.html?q=' + encodeURIComponent(q);
}}

// --- Consentimiento de cookies ---
function initCookieBanner() {{
    const saved = localStorage.getItem('cookie_consent');
    if (saved === 'accepted') {{
        applyConsent(true);
    }} else if (saved === 'rejected') {{
        applyConsent(false);
    }} else {{
        const banner = document.getElementById('cookie-banner');
        if (banner) banner.classList.remove('hidden');
    }}
}}
function applyConsent(granted) {{
    if (typeof gtag !== 'function') return;
    gtag('consent', 'update', {{
        'ad_storage': granted ? 'granted' : 'denied',
        'analytics_storage': granted ? 'granted' : 'denied',
        'ad_user_data': granted ? 'granted' : 'denied',
        'ad_personalization': granted ? 'granted' : 'denied'
    }});
}}
function acceptCookies() {{
    localStorage.setItem('cookie_consent', 'accepted');
    applyConsent(true);
    document.getElementById('cookie-banner').classList.add('hidden');
}}
function rejectCookies() {{
    localStorage.setItem('cookie_consent', 'rejected');
    applyConsent(false);
    document.getElementById('cookie-banner').classList.add('hidden');
}}
</script>
</body>
</html>
"""


def esc(s):
    return (str(s) or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def article_card(n, cat_url):
    url = article_url(n)
    return f"""
<article class="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
    <a href="{url}">
        <img src="{n['images'][0]}" class="w-full h-44 object-cover" alt="{esc(n['title'])}" loading="lazy">
        <div class="p-4">
            <span class="text-blue-600 font-bold text-[9px] uppercase">{esc(n['category'])}</span>
            <h3 class="font-bold my-2 line-clamp-2 text-gray-800">{esc(n['title'])}</h3>
            <p class="text-gray-400 text-[10px]">{fmt_date(n['date'])}</p>
        </div>
    </a>
</article>"""


def fmt_date(iso_date):
    try:
        d = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return f"{d.day} de {meses[d.month-1]} de {d.year}"
    except Exception:
        return iso_date[:10]


def article_url(n):
    return f"{SITE_URL}/{category_slug(n['category'])}/{slugify(n['title'])}-{n['id']}/"


def article_dir_path(n):
    """Ruta relativa en disco (sin SITE_URL) de la carpeta de un artículo."""
    return f"{category_slug(n['category'])}/{slugify(n['title'])}-{n['id']}/"


def category_url(cat):
    return f"{SITE_URL}/{category_slug(cat)}/"


def author_url(author):
    return f"{SITE_URL}/autor/{slugify(author)}/"


# --- Generadores de páginas ---

def write(path, content):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def generate_article_page(n, news):
    url = article_url(n)
    cat_url = category_url(n["category"])
    auth_url = author_url(n["author"])
    description = (n["content"][:157] + "...") if len(n["content"]) > 160 else n["content"]
    description = re.sub(r"\s+", " ", description).strip()
    image = n["images"][0] if n.get("images") else ""

    ld_article = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": n["title"],
        "description": description,
        "image": [image] if image else [],
        "datePublished": n["date"],
        "dateModified": n["date"],
        "author": {"@type": "Person", "name": n["author"]},
        "publisher": {
            "@type": "Organization",
            "name": "Enfoque Mundial",
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/logo/logo%20vectorizado.svg"},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "articleSection": n["category"],
    }
    crumbs = [("Inicio", f"{SITE_URL}/"), (n["category"], cat_url), (n["title"], None)]
    ld_breadcrumb = breadcrumb_ld(crumbs)
    extra_ld = (
        f'<script type="application/ld+json">{json.dumps(ld_article, ensure_ascii=False)}</script>\n'
        f'    <script type="application/ld+json">{json.dumps(ld_breadcrumb, ensure_ascii=False)}</script>'
    )

    related = [a for a in news if a["category"] == n["category"] and a["id"] != n["id"]][:3]
    related_html = "".join(article_card(a, cat_url) for a in related) or ""

    paragraphs = "".join(f"<p class='mb-5 leading-relaxed text-gray-700'>{esc(p)}</p>"
                          for p in n["content"].split("\n") if p.strip())

    title_esc = esc(n["title"])
    hero_image_html = "".join(
        f'<div class="mb-10"><img src="{img}" alt="{title_esc}" class="w-full rounded-2xl shadow-lg" loading="lazy"></div>'
        for img in n.get("images", [])[:1]
    )
    source_html = ""
    if n.get("source_name", "").strip():
        source_html = f'<p class="text-xs text-gray-400 mt-1">Basado en información de <span class="font-medium text-gray-500">{esc(n["source_name"])}</span></p>'

    body = f"""
{nav(url, news)}
{breadcrumbs(crumbs, url)}
<main class="max-w-3xl mx-auto px-4 py-10">
    <article>
        <a href="{cat_url}" class="text-blue-600 font-bold text-xs uppercase tracking-widest">{esc(n['category'])}</a>
        <h1 class="text-3xl md:text-5xl font-serif font-bold mt-4 mb-6 leading-tight">{esc(n['title'])}</h1>
        <div class="flex items-center gap-4 text-gray-500 text-sm border-y border-gray-100 py-4 mb-8">
            <div class="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center"><i data-lucide="user" class="w-5 h-5"></i></div>
            <div>
                <a href="{auth_url}" class="font-bold text-black hover:underline">{esc(n['author'])}</a>
                <p class="text-xs text-gray-400">Publicado: {fmt_date(n['date'])}</p>
                {source_html}
            </div>
        </div>
        {hero_image_html}
        <div class="prose prose-lg max-w-none">
            {paragraphs}
        </div>
    </article>

    {"<h2 class='text-xl font-serif font-bold mt-16 mb-6'>Noticias relacionadas</h2><div class='grid grid-cols-1 md:grid-cols-3 gap-6'>" + related_html + "</div>" if related else ""}
</main>
{footer(url)}
"""
    html = head(f"{n['title']} | Enfoque Mundial", description, url, og_type="article", og_image=image, extra_ld=extra_ld) + body
    rel_path = f"{category_slug(n['category'])}/{slugify(n['title'])}-{n['id']}/index.html"
    write(rel_path, html)
    return url


def generate_category_page(category, news):
    url = category_url(category)
    articles = [a for a in news if a["category"] == category]
    articles.sort(key=lambda a: a["date"], reverse=True)
    description = f"Últimas noticias de {category} en Enfoque Mundial. Periodismo verificado con perspectiva global."
    crumbs = [("Inicio", f"{SITE_URL}/"), (category, None)]
    cards = "".join(article_card(a, url) for a in articles)
    noindex = len(articles) < MIN_ARTICLES_CATEGORY_INDEXABLE
    body = f"""
{nav(url, news)}
{breadcrumbs(crumbs, url)}
<main class="max-w-7xl mx-auto px-4 py-10">
    <h1 class="text-3xl font-serif font-bold mb-10">{esc(category)}</h1>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        {cards if articles else '<p class="text-gray-400 col-span-3 py-10 text-center">Todavía no hay noticias en esta categoría.</p>'}
    </div>
</main>
{footer(url)}
"""
    html = head(f"{category} | Enfoque Mundial", description, url, noindex=noindex) + body
    write(f"{category_slug(category)}/index.html", html)
    return url, noindex


def generate_author_page(author, news):
    url = author_url(author)
    articles = [a for a in news if a["author"] == author]
    articles.sort(key=lambda a: a["date"], reverse=True)
    bio = AUTHOR_BIOS.get(author, f"Redactor/a de Enfoque Mundial.")
    description = f"Artículos de {author} en Enfoque Mundial. {bio}"
    crumbs = [("Inicio", f"{SITE_URL}/"), ("Autores", None), (author, None)]
    cards = "".join(article_card(a, url) for a in articles)
    noindex = len(articles) < MIN_ARTICLES_AUTHOR_INDEXABLE
    body = f"""
{nav(url, news)}
{breadcrumbs(crumbs, url)}
<main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-10">
        <div class="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center mb-4"><i data-lucide="user" class="w-8 h-8"></i></div>
        <h1 class="text-3xl font-serif font-bold mb-2">{esc(author)}</h1>
        <p class="text-gray-500 max-w-2xl">{esc(bio)}</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        {cards if articles else '<p class="text-gray-400 col-span-3 py-10 text-center">Sin artículos publicados todavía.</p>'}
    </div>
</main>
{footer(url)}
"""
    html = head(f"{author} | Enfoque Mundial", description, url, noindex=noindex) + body
    write(f"autor/{slugify(author)}/index.html", html)
    return url, noindex


def generate_homepage(news):
    url = f"{SITE_URL}/"
    news_sorted = sorted(news, key=lambda a: a["date"], reverse=True)
    hero = news_sorted[0] if news_sorted else None
    latest = news_sorted[1:13]
    trending = news_sorted[:5]

    categories = sorted(set(a["category"] for a in news))

    hero_html = ""
    if hero:
        hero_html = f"""
        <a href="{article_url(hero)}" class="grid md:grid-cols-2 gap-8 items-center group">
            <img src="{hero['images'][0]}" class="w-full h-80 object-cover rounded-3xl" alt="{esc(hero['title'])}" loading="lazy">
            <div>
                <span class="text-blue-600 font-bold text-xs uppercase tracking-widest">{esc(hero['category'])}</span>
                <h2 class="text-3xl font-serif font-bold my-4 group-hover:underline">{esc(hero['title'])}</h2>
                <p class="text-gray-500 line-clamp-3">{esc(hero['content'][:220])}...</p>
                <p class="text-gray-400 text-xs mt-4">{esc(hero['author'])} &middot; {fmt_date(hero['date'])}</p>
            </div>
        </a>"""

    latest_cards = "".join(article_card(a, url) for a in latest)
    trending_html = "".join(
        f"""<a href="{article_url(a)}" class="flex gap-3 group">
            <img src="{a['images'][0]}" class="w-16 h-16 object-cover rounded-xl flex-shrink-0" alt="{esc(a['title'])}" loading="lazy">
            <div><h4 class="text-sm font-bold group-hover:underline line-clamp-2">{esc(a['title'])}</h4>
            <p class="text-[10px] text-gray-400 mt-1">{esc(a['category'])}</p></div>
        </a>""" for a in trending
    )

    category_sections = ""
    for cat in categories:
        cat_articles = [a for a in news_sorted if a["category"] == cat][:3]
        if not cat_articles:
            continue
        cards = "".join(article_card(a, category_url(cat)) for a in cat_articles)
        category_sections += f"""
        <section class="mb-16">
            <div class="flex items-center justify-between mb-8">
                <h2 class="text-2xl font-serif font-bold">{esc(cat)}</h2>
                <a href="{category_slug(cat)}/index.html" class="text-xs font-bold text-blue-600 hover:underline">Ver todas &rarr;</a>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">{cards}</div>
        </section>"""

    ld_org = {
        "@context": "https://schema.org",
        "@type": "NewsMediaOrganization",
        "name": "Enfoque Mundial",
        "url": url,
        "logo": f"{SITE_URL}/logo/logo%20vectorizado.svg",
        "description": "Enfoque Mundial: noticias internacionales, análisis político, economía y más. Periodismo verificado con perspectiva global en español.",
    }
    extra_ld = f'<script type="application/ld+json">{json.dumps(ld_org, ensure_ascii=False)}</script>'

    body = f"""
{nav(url, news)}
<main class="max-w-7xl mx-auto px-4 py-10">
    <section class="mb-16">{hero_html}</section>
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-12">
        <div class="lg:col-span-8">
            <h2 class="text-3xl font-serif font-bold mb-10">Lo Último</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">{latest_cards}</div>
        </div>
        <aside class="lg:col-span-4">
            <div class="bg-gray-50 p-8 rounded-[2rem] sticky top-32">
                <h3 class="text-lg font-bold mb-8 flex items-center gap-3">
                    <i data-lucide="trending-up" class="text-blue-600 w-5 h-5"></i> Tendencias
                </h3>
                <div class="space-y-6 mb-10">{trending_html}</div>
            </div>
        </aside>
    </div>
    {category_sections}
</main>
{footer(url)}
"""
    html = head("Enfoque Mundial | Periodismo Global",
                 "Enfoque Mundial: noticias internacionales, análisis político, economía y más. Periodismo verificado con perspectiva global en español.",
                 url, extra_ld=extra_ld) + body
    write("index.html", html)


def generate_sitemap(news):
    static_pages = [
        (f"{SITE_URL}/", "daily", "1.0"),
        (f"{SITE_URL}/sobre-nosotros.html", "monthly", "0.8"),
        (f"{SITE_URL}/contacto.html", "monthly", "0.8"),
        (f"{SITE_URL}/privacidad.html", "yearly", "0.5"),
        (f"{SITE_URL}/terminos.html", "yearly", "0.5"),
    ]
    categories = sorted(set(a["category"] for a in news))
    authors = sorted(set(a["author"] for a in news))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, pri in static_pages:
        parts.append(f"\n  <url>\n    <loc>{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>")
    for cat in categories:
        count = sum(1 for a in news if a["category"] == cat)
        if count < MIN_ARTICLES_CATEGORY_INDEXABLE:
            continue  # página delgada, marcada noindex — no la metemos en el sitemap
        parts.append(f"\n  <url>\n    <loc>{category_url(cat)}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.8</priority>\n  </url>")
    for author in authors:
        count = sum(1 for a in news if a["author"] == author)
        if count < MIN_ARTICLES_AUTHOR_INDEXABLE:
            continue
        parts.append(f"\n  <url>\n    <loc>{author_url(author)}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.5</priority>\n  </url>")
    for n in news:
        lastmod = n.get("date", "")[:10]
        parts.append(f"\n  <url>\n    <loc>{article_url(n)}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    parts.append("\n</urlset>\n")
    write("sitemap.xml", "".join(parts))


PROTECTED_TOP_LEVEL = {
    "admin", "css", "js", "images", "logo", "data", ".github", "scripts",
    "buscar", ".git", "build",
}


def clean_generated_dirs():
    """Borra carpetas de categorías/autores generadas en corridas anteriores
    (por ejemplo, si una noticia cambió de título y el slug ya no coincide,
    la carpeta vieja quedaría huérfana con contenido desactualizado)."""
    import shutil
    for entry in os.listdir(ROOT):
        full = os.path.join(ROOT, entry)
        if not os.path.isdir(full) or entry in PROTECTED_TOP_LEVEL or entry.startswith("."):
            continue
        shutil.rmtree(full)


def build_all(news=None):
    clean_generated_dirs()
    news = news or load_news()
    valid_news = []
    for n in news:
        try:
            validate_article(n)
            valid_news.append(n)
        except ArticleValidationError as e:
            print(f"⚠️  Saltando artículo inválido: {e}")
    for n in valid_news:
        generate_article_page(n, valid_news)
    for cat in sorted(set(a["category"] for a in valid_news)):
        generate_category_page(cat, valid_news)
    for author in sorted(set(a["author"] for a in valid_news)):
        generate_author_page(author, valid_news)
    generate_homepage(valid_news)
    generate_redirects(valid_news)
    generate_sitemap(valid_news)
    return valid_news


def build_incremental(new_article, news):
    """Regenera solo lo afectado por una noticia nueva (usado por auto_publish.py
    y por publish_new). Lanza ArticleValidationError si la noticia no cumple el
    mínimo — el llamador debe abortar la publicación en ese caso."""
    validate_article(new_article)
    generate_article_page(new_article, news)
    generate_category_page(new_article["category"], news)
    generate_author_page(new_article["author"], news)
    generate_homepage(news)
    generate_sitemap(news)


# ============================================================
# Redirecciones (para cuando cambia el slug de un artículo editado)
# ============================================================

REDIRECTS_PATH = os.path.join(ROOT, "data", "redirects.json")


def load_redirects():
    if not os.path.exists(REDIRECTS_PATH):
        return []
    with open(REDIRECTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_redirects(redirects):
    with open(REDIRECTS_PATH, "w", encoding="utf-8") as f:
        json.dump(redirects, f, ensure_ascii=False, indent=2)


def add_redirect(old_path, new_url):
    """Registra old_path -> new_url. Si ya existía alguna redirección que
    apuntaba hacia old_path, la reescribe para que apunte directo a new_url
    — así nunca se encadenan dos saltos, siempre queda uno solo."""
    redirects = load_redirects()
    old_path_url = f"{SITE_URL}/{old_path}"
    for r in redirects:
        if r["to"] == old_path_url:
            r["to"] = new_url
    redirects = [r for r in redirects if r["from"] != old_path]
    redirects.append({"from": old_path, "to": new_url})
    save_redirects(redirects)


def generate_redirects(news):
    """Genera una página de redirección (meta-refresh + canonical + JS) en cada
    ruta vieja registrada en data/redirects.json. Un solo salto: si la URL
    nueva también cambió después, se actualiza el registro, no se encadenan.
    Se salta cualquier ruta que hoy coincida con un artículo real (evita
    pisar contenido válido por error)."""
    redirects = load_redirects()
    live_paths = {article_dir_path(n) for n in news}
    for r in redirects:
        if r["from"] in live_paths:
            continue  # esa ruta ya la ocupa un artículo real, no se toca
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={r['to']}">
<link rel="canonical" href="{r['to']}">
<meta name="robots" content="noindex, follow">
<title>Redirigiendo... | Enfoque Mundial</title>
<script>window.location.replace("{r['to']}");</script>
</head>
<body>
<p>Esta noticia se movió. <a href="{r['to']}">Haz clic aquí si no eres redirigido automáticamente</a>.</p>
</body>
</html>
"""
        write(r["from"] + "index.html" if not r["from"].endswith("index.html") else r["from"], html)


# ============================================================
# Git compartido (usado por auto_publish.py y manual_publish.py)
# ============================================================

def git(*args, gh_token, owner, repo):
    remote_url = f"https://x-access-token:{gh_token}@github.com/{owner}/{repo}.git"
    if args and args[0] == "push":
        subprocess.run(["git", "push", remote_url, "HEAD:main"], cwd=ROOT, check=True)
    else:
        subprocess.run(["git", *args], cwd=ROOT, check=True)


def commit_and_push(message, gh_token, owner=GITHUB_OWNER, repo=GITHUB_REPO):
    subprocess.run(["git", "config", "user.name", "Enfoque Mundial Bot"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if result.returncode == 0:
        print("Sin cambios que publicar.")
        return False
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    git("push", gh_token=gh_token, owner=owner, repo=repo)
    return True


# ============================================================
# API de alto nivel: ÚNICA lógica de publicar/editar/borrar.
# La usan por igual auto_publish.py (automático) y manual_publish.py (panel).
# ============================================================

def publish_new(entry, news):
    """Valida y agrega un artículo nuevo. Lanza ArticleValidationError si no
    cumple el mínimo — en ese caso NO se debe escribir nada a disco."""
    validate_article(entry)
    updated_news = [entry] + news
    with open(NEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_news, f, ensure_ascii=False, indent=2)
    build_incremental(entry, updated_news)
    return updated_news


def apply_edit(article_id, changes, news):
    """Edita un artículo existente. `changes` es un dict con los campos a
    actualizar (title/content/category/author/images). La fecha original NUNCA
    se toca automáticamente (no se falsean fechas de publicación)."""
    old_entry = next((n for n in news if n["id"] == article_id), None)
    if old_entry is None:
        raise ArticleValidationError(f"No existe ninguna noticia con id={article_id}")

    old_path = article_dir_path(old_entry)
    old_category = old_entry["category"]
    old_author = old_entry["author"]

    updated_entry = dict(old_entry)
    for key in ("title", "content", "category", "author", "images"):
        if key in changes and changes[key] not in (None, ""):
            updated_entry[key] = changes[key]

    validate_article(updated_entry)  # si falla, no se escribe nada

    updated_news = [updated_entry if n["id"] == article_id else n for n in news]
    with open(NEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_news, f, ensure_ascii=False, indent=2)

    new_path = article_dir_path(updated_entry)
    if new_path != old_path:
        # El slug cambió: borrar la carpeta vieja y dejar una redirección
        # de un solo salto hacia la URL nueva.
        old_full = os.path.join(ROOT, old_path)
        if os.path.isdir(old_full):
            import shutil
            shutil.rmtree(old_full)
        add_redirect(old_path, article_url(updated_entry))

    affected_categories = {old_category, updated_entry["category"]}
    affected_authors = {old_author, updated_entry["author"]}
    for cat in affected_categories:
        generate_category_page(cat, updated_news)
    for author in affected_authors:
        generate_author_page(author, updated_news)
    generate_article_page(updated_entry, updated_news)
    generate_homepage(updated_news)
    generate_redirects(updated_news)
    generate_sitemap(updated_news)
    return updated_news


def apply_delete(article_id, news):
    """Elimina un artículo por completo: de news.json, su carpeta HTML, de
    todas las páginas que lo listaban, y de cualquier redirección que
    apuntara hacia él (para no dejar redirecciones huérfanas apuntando a
    una página que ya no existe)."""
    entry = next((n for n in news if n["id"] == article_id), None)
    if entry is None:
        raise ArticleValidationError(f"No existe ninguna noticia con id={article_id}")

    path = article_dir_path(entry)
    updated_news = [n for n in news if n["id"] != article_id]
    with open(NEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_news, f, ensure_ascii=False, indent=2)

    full_path = os.path.join(ROOT, path)
    if os.path.isdir(full_path):
        import shutil
        shutil.rmtree(full_path)

    article_url_str = article_url(entry)
    redirects = load_redirects()
    orphaned = [r for r in redirects if r["to"] == article_url_str]
    remaining = [r for r in redirects if r["to"] != article_url_str]
    save_redirects(remaining)
    for r in orphaned:
        stub_path = os.path.join(ROOT, r["from"])
        if os.path.isdir(stub_path):
            import shutil
            shutil.rmtree(stub_path)

    generate_category_page(entry["category"], updated_news)
    generate_author_page(entry["author"], updated_news)
    generate_homepage(updated_news)
    generate_sitemap(updated_news)
    return updated_news


if __name__ == "__main__":
    build_all()
    print("Sitio estático generado correctamente.")

