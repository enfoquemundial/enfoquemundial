#!/usr/bin/env python3
"""
Auto-publicación de noticias para Enfoque Mundial.

Flujo:
 1. Trae noticias REALES y recientes desde GNews API.
 2. Le pide a Claude que redacte un artículo original en español,
    basado SOLO en esos hechos reales (reglas estrictas contra inventar
    datos o citas falsas atribuidas a personas reales), y que elija la
    categoría real y una frase de búsqueda de imagen segura.
 3. Busca una foto libre de derechos relacionada (Unsplash).
 4. Actualiza data/news.json y genera las páginas HTML reales
    (artículo, categoría, autor, portada, sitemap.xml) con generate_site.py.
 5. Hace commit y push directo con git (el repo ya está clonado por
    actions/checkout en el workflow).

Se ejecuta automáticamente por GitHub Actions (ver .github/workflows/auto-publish.yml),
pero también se puede correr a mano con:  python3 scripts/auto_publish.py
"""

import os
import re
import sys
import json
import random
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_site  # noqa: E402

ROOT = generate_site.ROOT
NEWS_PATH = generate_site.NEWS_PATH
SITE_URL = generate_site.SITE_URL

CATEGORIES = ["Mundo", "Politica", "Politica internacional", "Tecnología", "Finanzas", "Deportes", "Cultura"]
AUTHORS = ["Esfrailin Quezada", "Irelsa Nuñez", "Redacción"]

GH_TOKEN = os.environ["GH_TOKEN"].strip()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"].strip()
GNEWS_API_KEY = os.environ["GNEWS_API_KEY"].strip()
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()


# --- Fuente de noticias reales ---
def fetch_real_news():
    url = "https://gnews.io/api/v4/top-headlines"
    params = {"lang": "es", "max": 10, "token": GNEWS_API_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    articles = r.json().get("articles", [])
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
- NUNCA incluyas encabezados de plantilla como "Título:", "Categoría:", "Desarrollo de la noticia:" dentro del campo content — solo el texto del artículo en sí, listo para publicar tal cual.

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
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


# --- Imagen libre de derechos relacionada al tema ---
STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "en",
    "y", "a", "que", "por", "con", "para", "su", "sus", "es", "se", "al",
    "lo", "como", "más", "sobre", "entre", "tras", "ante", "nuevo", "nueva",
    "nuevos", "nuevas",
}


def significant_words(title):
    words = re.findall(r"[a-záéíóúñ]+", title.lower())
    return {w for w in words if w not in STOPWORDS_ES and len(w) > 2}


def word_overlap(a, b):
    wa, wb = significant_words(a), significant_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def is_duplicate_title(new_title, existing_titles, char_threshold=0.5, word_threshold=0.35):
    """Compara el título nuevo contra todos los ya publicados con DOS métodos
    combinados — similitud de caracteres y solapamiento de palabras clave —
    para detectar reescrituras del mismo evento, no solo copias exactas.
    Calibrado con casos reales del sitio; no es perfecto (un parafraseo muy
    libre del mismo evento puede no detectarse), pero evita falsos positivos
    bloqueando noticias genuinamente distintas."""
    new_norm = new_title.lower().strip()
    for existing in existing_titles:
        char_ratio = SequenceMatcher(None, new_norm, existing.lower().strip()).ratio()
        word_ratio = word_overlap(new_title, existing)
        if char_ratio >= char_threshold or word_ratio >= word_threshold:
            return True, existing, max(char_ratio, word_ratio)
    return False, None, 0.0


def fetch_image(query, used_images=None):
    """Busca una foto en Unsplash. Pide varios resultados y elige el primero
    que NO se haya usado ya en el sitio, para evitar repetir la misma imagen
    en dos noticias distintas cuando la búsqueda coincide (ej. dos noticias
    de "tecnología" devolviendo la misma foto top del buscador)."""
    if not UNSPLASH_ACCESS_KEY:
        return None
    used_images = used_images or set()
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 10, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=20,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        for photo in results:
            url = photo["urls"]["regular"]
            if url not in used_images:
                return url
        # Si las 10 primeras ya están usadas (poco probable), devuelve la primera igual
        if results:
            return results[0]["urls"]["regular"]
    except Exception as e:
        print(f"Aviso: no se pudo obtener imagen de Unsplash ({e})")
    return None


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

    category = generated.get("category", "").strip()
    if category not in CATEGORIES:
        print(f"Aviso: categoría '{category}' no reconocida, usando 'Mundo' por defecto.")
        category = "Mundo"

    with open(NEWS_PATH, encoding="utf-8") as f:
        news = json.load(f)

    print("Verificando que no sea una noticia repetida...")
    existing_titles = [n["title"] for n in news]
    is_dup, matched_title, ratio = is_duplicate_title(generated["title"], existing_titles)
    if is_dup:
        print(f"Se detectó una noticia muy similar ya publicada (similitud {ratio:.0%}):")
        print(f"  Nueva:      {generated['title']}")
        print(f"  Ya publicada: {matched_title}")
        print("Abortando esta corrida sin publicar (mejor no repetir que duplicar).")
        sys.exit(0)

    print("Buscando imagen libre de derechos...")
    used_images = {img for n in news for img in n.get("images", [])}
    image_query = generated.get("image_query", "").strip() or category
    image_url = fetch_image(image_query, used_images) or "https://images.unsplash.com/photo-1495020689067-958852a7765e?w=1200"

    new_entry = {
        "id": int(time.time() * 1000),
        "title": generated["title"],
        "content": generated["content"],
        "category": category,
        "author": random.choice(AUTHORS),
        "date": datetime.now(timezone.utc).isoformat(),
        "images": [image_url],
        "views": 0,
        "source_name": source.get("source", {}).get("name", "").strip(),
    }

    print("Validando y generando páginas HTML reales (misma lógica que usa el panel)...")
    try:
        generate_site.publish_new(new_entry, news)
    except generate_site.ArticleValidationError as e:
        print(f"❌ La noticia generada no pasó la validación mínima: {e}")
        print("No se publica nada en esta corrida (nada quedó escrito en disco).")
        sys.exit(1)

    print("Publicando en GitHub...")
    generate_site.commit_and_push(f"Auto-publish: {new_entry['title'][:70]}", gh_token=GH_TOKEN)

    url = generate_site.article_url(new_entry)
    print(f"✅ Publicado: {url}")


if __name__ == "__main__":
    main()
