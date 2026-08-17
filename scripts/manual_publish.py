#!/usr/bin/env python3
"""
Procesa UNA acción pendiente desde el panel de administración
(crear, editar o borrar una noticia), usando exactamente la misma
lógica que usa la automatización (generate_site.publish_new / apply_edit /
apply_delete) — una única fuente de verdad para generar el sitio.

Flujo:
  1. El panel (js/admin.js) sube data/_pending_publish.json al repo
     y dispara este workflow (manual-publish.yml).
  2. Este script lee ese archivo, valida y aplica la acción.
  3. Si algo falla, NO se hace commit de nada — el repo queda exactamente
     igual que antes, y el job de GitHub Actions termina en rojo para que
     el panel se entere de que falló.
  4. Si todo sale bien, se hace commit+push de: news.json actualizado,
     las páginas HTML regeneradas, y se borra el archivo pendiente.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_site  # noqa: E402

ROOT = generate_site.ROOT
NEWS_PATH = generate_site.NEWS_PATH
PENDING_PATH = os.path.join(ROOT, "data", "_pending_publish.json")

GH_TOKEN = os.environ["GH_TOKEN"].strip()


def main():
    if not os.path.exists(PENDING_PATH):
        print("❌ No hay ninguna acción pendiente (data/_pending_publish.json no existe).")
        sys.exit(1)

    with open(PENDING_PATH, encoding="utf-8") as f:
        pending = json.load(f)

    action = pending.get("action")
    with open(NEWS_PATH, encoding="utf-8") as f:
        news = json.load(f)

    try:
        if action == "create":
            entry = {
                "id": pending["id"],
                "title": pending.get("title", ""),
                "content": pending.get("content", ""),
                "category": pending.get("category", ""),
                "author": pending.get("author", ""),
                "date": pending.get("date"),
                "images": pending.get("images", []),
                "views": 0,
            }
            print(f"Creando noticia: {entry['title']}")
            generate_site.publish_new(entry, news)

        elif action == "edit":
            article_id = pending["id"]
            changes = {k: pending[k] for k in ("title", "content", "category", "author", "images") if k in pending}
            print(f"Editando noticia id={article_id}: {changes.get('title', '(sin cambio de título)')}")
            generate_site.apply_edit(article_id, changes, news)

        elif action == "delete":
            article_id = pending["id"]
            print(f"Borrando noticia id={article_id}")
            generate_site.apply_delete(article_id, news)

        else:
            print(f"❌ Acción desconocida: '{action}'")
            sys.exit(1)

    except generate_site.ArticleValidationError as e:
        print(f"❌ Validación fallida, no se publica nada: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado, no se publica nada: {e}")
        sys.exit(1)

    # Todo salió bien: eliminar el archivo pendiente antes de hacer commit,
    # para que quede como parte del mismo commit y no se acumule basura.
    if os.path.exists(PENDING_PATH):
        os.remove(PENDING_PATH)

    ok = generate_site.commit_and_push(f"Panel admin: {action} noticia", gh_token=GH_TOKEN)
    if ok:
        print("✅ Publicado correctamente desde el panel.")
    else:
        print("⚠️  No hubo cambios que publicar.")


if __name__ == "__main__":
    main()
