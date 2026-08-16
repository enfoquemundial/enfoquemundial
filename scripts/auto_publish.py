#!/usr/bin/env python3
"""
Auto-publicación de noticias para Enfoque Mundial.

Flujo:
 1. Trae noticias REALES y recientes desde GNews API.
 2. Le pide a Claude que redacte un artículo original en español,
    basado SOLO en esos hechos reales (reglas estrictas contra inventar
    datos o citas falsas atribuidas a personas reales).
 3. Busca una foto libre de derechos relacionada (Unsplash).
 4. Publica el artículo en data/news.json y regenera sitemap.xml,
    directo en el repo de GitHub, vía la API de contenidos.

Se ejecuta automáticamente por GitHub Actions (ver .github/workflows/auto-publish.yml),
pero también se puede correr a mano con:  python3 scripts/auto_publish.py
"""

import os
import sys
import json
import base64
import random
import time
from datetime import datetime, timezone

import requests

# --- Configuración ---
GITHUB_OWNER = "enfoquemundial"
GITHUB_REPO = "enfoquemundial"
NEWS_PATH = "data/news.json"
SITEMAP_PATH = "sitemap.xml"
SITE_URL = "https://enfoquemundial.com"

CATEGORIES = ["Mundo", "Politica", "Politica internacional", "Tecnología", "Finanzas", "Deportes", "Cultura"]
AUTHORS = ["Esfrailin Quezada", "Irelsa Nuñez", "Redacción"]

GH_TOKEN = os.environ["GH_TOKEN"].strip()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"].strip()
GNEWS_API_KEY = os.environ["GNEWS_API_KEY"].strip()
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()

GH_HEADERS = {"Authorization": f"token {GH_TOKEN}"}


# --- GitHub: leer/escribir archivos del repo ---
def gh_get_file(path):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=GH_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def gh_put_file(path, text, sha, message):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    content_b64 = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    body = {"message": message, "content": content_b64, "sha": sha, "branch": "main"}
    r = requests.put(url, headers=GH_HEADERS, json=body, timeout=30)
    r.raise_for_status()


# --- Fuente de noticias reales ---
def fetch_real_news():
    url = "https://gnews.io/api/v4/top-headlines"
    params = {"lang": "es", "max": 10, "token": GNEWS_API_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    articles = r.json().get("articles", [])
    # Solo noticias con suficiente info real y sustancial para escribir un artículo decente
    # (evita basar el artículo en una fuente tan corta que la IA termine escribiendo puro relleno vago)
    MIN_SOURCE_CHARS = 300
    return [
        a for a in articles
        if a.get("title") and a.get("description")
        and len(a.get("description", "") + a.get("content", "")) >= MIN_SOURCE_CHARS
    ]


# --- Generación con IA, anclada a hechos reales ---
def generate_article(source):
    categories_list = ", ".join(CATEGORIES)
    prompt = f"""Eres redactor del medio digital "Enfoque Mundial". Te doy información real de una noticia reciente; tu trabajo es escribir un artículo periodístico ORIGINAL en español, de 400 a 600 palabras, basado ÚNICAMENTE en estos hechos:

Título original: {source.get('title')}
Resumen/contenido: {source.get('description', '')} {source.get('content', '')}
Fuente: {source.get('source', {}).get('name', 'medio internacional')}

REGLAS ESTRICTAS (no negociables):
- No inventes datos, cifras, fechas ni hechos que no estén en la información de arriba.
- No inventes citas textuales atribuidas a personas reales. Si mencionas declaraciones, parafrasea de forma general, nunca uses comillas con palabras que no puedas confirmar que dijeron.
- Si la información es insuficiente para 400 palabras factuales, escribe un artículo más corto — nunca rellenes con invenciones.
- Tono periodístico neutral y profesional, en español de Latinoamérica.
- No copies frases textuales del resumen original; redacta todo con tus propias palabras.

Además:
- Elige la categoría que MEJOR describe el tema real de esta noticia, solo entre estas opciones: {categories_list}
- Genera una frase corta EN INGLÉS (2-4 palabras) que describa la escena general del tema, para buscar una foto de stock genérica y segura relacionada — NO uses nombres propios, lugares específicos, ni términos que puedan confundirse con armas, violencia o conflicto. Ejemplos válidos: "government meeting building", "stock market finance", "technology data center", "sports stadium crowd".

Devuelve SOLO un objeto JSON válido, sin texto adicional, sin markdown, con este formato exacto:
{{"title": "un titular propio, no el original", "content": "el cuerpo completo del artículo", "category": "una de las categorías de la lista", "image_query": "frase corta en inglés para buscar la foto"}}
"""
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    text = "".join(b["text"] for b in data["content"] if b.get("type") == "text").strip()
    # por si el modelo envuelve la respuesta en ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


# --- Imagen libre de derechos relacionada al tema ---
def fetch_image(query):
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=20,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return results[0]["urls"]["regular"]
    except Exception as e:
        print(f"Aviso: no se pudo obtener imagen de Unsplash ({e})")
    return None


# --- Sitemap ---
def build_sitemap(news):
    static_pages = [
        (f"{SITE_URL}/", "daily", "1.0"),
        (f"{SITE_URL}/sobre-nosotros.html", "monthly", "0.8"),
        (f"{SITE_URL}/contacto.html", "monthly", "0.8"),
        (f"{SITE_URL}/privacidad.html", "yearly", "0.5"),
        (f"{SITE_URL}/terminos.html", "yearly", "0.5"),
    ]

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, pri in static_pages:
        parts.append(f"\n  <url>\n    <loc>{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>")
    for n in news:
        lastmod = n.get("date", "")[:10]
        loc = esc(f"{SITE_URL}/article.html?id={n['id']}")
        parts.append(f"\n  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    parts.append("\n</urlset>\n")
    return "".join(parts)


def main():
    print("Buscando noticias reales recientes...")
    real_articles = fetch_real_news()
    if not real_articles:
        print("No se encontraron noticias reales en esta corrida. Abortando sin publicar (mejor no publicar que inventar).")
        sys.exit(0)

    source = random.choice(real_articles)
    print(f"Base real elegida: {source['title']}")

    print("Redactando artículo original con IA...")
    generated = generate_article(source)

    # Validar que la categoría que devolvió la IA sea una de las permitidas;
    # si no, usar "Mundo" como categoría segura por defecto en vez de una al azar.
    category = generated.get("category", "").strip()
    if category not in CATEGORIES:
        print(f"Aviso: categoría '{category}' no reconocida, usando 'Mundo' por defecto.")
        category = "Mundo"

    print("Buscando imagen libre de derechos...")
    image_query = generated.get("image_query", "").strip() or category
    image_url = fetch_image(image_query) or "https://images.unsplash.com/photo-1495020689067-958852a7765e?w=1200"

    news_text, news_sha = gh_get_file(NEWS_PATH)
    news = json.loads(news_text)

    new_entry = {
        "id": int(time.time() * 1000),
        "title": generated["title"],
        "content": generated["content"],
        "category": category,
        "author": random.choice(AUTHORS),
        "date": datetime.now(timezone.utc).isoformat(),
        "images": [image_url],
        "views": 0,
    }
    updated_news = [new_entry] + news

    print("Publicando en GitHub...")
    gh_put_file(NEWS_PATH, json.dumps(updated_news, ensure_ascii=False, indent=2), news_sha,
                f"Auto-publish: {new_entry['title'][:70]}")

    sitemap_text, sitemap_sha = gh_get_file(SITEMAP_PATH)
    new_sitemap = build_sitemap(updated_news)
    gh_put_file(SITEMAP_PATH, new_sitemap, sitemap_sha, "Update sitemap.xml (auto-publish)")

    url = f"{SITE_URL}/article.html?id={new_entry['id']}"
    print(f"✅ Publicado: {url}")


if __name__ == "__main__":
    main()
