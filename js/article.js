const GITHUB_USER = 'enfoquemundial';
const GITHUB_REPO = 'enfoquemundial';
const SITE_URL = 'https://enfoquemundial.com';
const DATA_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/news.json`;

async function fetchSingleNews() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');

    if (!id) {
        showError();
        return;
    }

    try {
        const response = await fetch(DATA_URL + '?t=' + Date.now());
        if (!response.ok) throw new Error('Respuesta no válida de la fuente de datos');
        const news = await response.json();
        const article = news.find(n => n.id == id);

        if (article) {
            renderArticle(article);
        } else {
            showError();
        }
    } catch (e) {
        console.error("Error cargando noticia:", e);
        showError();
    }
}

function showError() {
    const container = document.getElementById('article-content');
    if (!container) return;
    container.innerHTML = `
        <div style="text-align:center;padding:80px 0;">
            <h1 style="font-size:1.5rem;font-weight:700;margin-bottom:12px;">Noticia no encontrada</h1>
            <p style="color:#6b7280;margin-bottom:24px;">Es posible que el enlace esté roto o la noticia ya no esté disponible.</p>
            <a href="index.html" style="color:#2563eb;font-weight:600;text-decoration:underline;">Volver al inicio</a>
        </div>`;
}

function slugify(text) {
    return (text || '')
        .toString()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '') || 'articulo';
}

function newCleanUrl(n) {
    return `${SITE_URL}/${slugify(n.category)}/${slugify(n.title)}-${n.id}/`;
}

function renderArticle(n) {
    // Esta página (article.html?id=...) es la versión antigua. Si la noticia
    // ya tiene su página nueva y permanente, redirige ahí para consolidar
    // todo en una sola URL (mejor para SEO y para no duplicar contenido).
    const cleanUrl = newCleanUrl(n);
    if (window.location.href.indexOf('article.html') !== -1) {
        window.location.replace(cleanUrl);
        return;
    }

    const url = cleanUrl;
    const description = buildDescription(n.content);
    const image = (n.images && n.images[0]) ? n.images[0] : '';

    // Metadatos reales por artículo (title, description, canonical, Open Graph)
    document.title = `${n.title} | Enfoque Mundial`;
    setMeta('meta-title', 'text', `${n.title} | Enfoque Mundial`);
    setMeta('meta-description', 'content', description);
    setMeta('meta-canonical', 'href', url);
    setMeta('meta-og-title', 'content', n.title);
    setMeta('meta-og-description', 'content', description);
    setMeta('meta-og-url', 'content', url);
    if (image) setMeta('meta-og-image', 'content', image);

    // Datos estructurados NewsArticle
    const ldJson = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": n.title,
        "description": description,
        "datePublished": n.date,
        "dateModified": n.date,
        "author": { "@type": "Person", "name": n.author || "Redacción" },
        "publisher": {
            "@type": "Organization",
            "name": "Enfoque Mundial",
            "logo": { "@type": "ImageObject", "url": `${SITE_URL}/logo/logo%20vectorizado.svg` }
        },
        "mainEntityOfPage": { "@type": "WebPage", "@id": url }
    };
    if (image) ldJson.image = [image];
    const ldScript = document.getElementById('ld-json');
    if (ldScript) ldScript.textContent = JSON.stringify(ldJson);

    // Contenido visible (mismo diseño original, ahora con datos reales)
    const container = document.getElementById('article-content');
    if (!container) return;

    const images = Array.isArray(n.images) ? n.images : [];
    const dateFormatted = n.date
        ? new Date(n.date).toLocaleString('es-ES', { dateStyle: 'long', timeStyle: 'short' })
        : '';

    container.innerHTML = `
        <div class="mb-8">
            <span class="text-blue-600 font-bold text-xs uppercase tracking-widest">${escapeHtml(n.category || '')}</span>
            <h1 class="text-3xl md:text-5xl font-serif font-bold mt-4 mb-6 leading-tight">${escapeHtml(n.title || '')}</h1>
            <div class="flex items-center gap-4 text-gray-500 text-sm border-y border-gray-100 py-4">
                <div class="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center"><i data-lucide="user" class="w-5 h-5"></i></div>
                <div>
                    <p class="font-bold text-black">${escapeHtml(n.author || 'Redacción')}</p>
                    <p class="text-xs text-gray-400">${dateFormatted}</p>
                </div>
            </div>
        </div>

        <div class="mb-10 space-y-4">
            ${images.map(img => `
                <div class="rounded-2xl overflow-hidden shadow-lg">
                    <img src="${img}" alt="${escapeHtml(n.title || '')}" class="w-full object-cover" loading="lazy">
                </div>
            `).join('')}
        </div>

        <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap">${escapeHtml(n.content || '')}</div>
    `;

    if (window.lucide) lucide.createIcons();
}

function buildDescription(content) {
    if (!content) return 'Lee las últimas noticias internacionales en Enfoque Mundial. Periodismo verificado con perspectiva global.';
    const clean = content.replace(/\s+/g, ' ').trim();
    return clean.length > 160 ? clean.slice(0, 157) + '...' : clean;
}

function setMeta(id, attr, value) {
    const el = document.getElementById(id);
    if (!el) return;
    if (attr === 'text') el.textContent = value;
    else el.setAttribute(attr, value);
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

window.onload = fetchSingleNews;
