const STORAGE_KEY = 'enfoque_mundial_news';
// --- CONFIGURACIÓN PARA TODOS LOS USUARIOS ---
const GITHUB_USER = 'enfoquemundial'; // <--- Pon aquí tu usuario exacto de GitHub
const GITHUB_REPO = 'enfoquemundial'; // <--- Pon aquí el nombre de tu repositorio
const DATA_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/news.json`;

const ITEMS_PER_PAGE = 10;
let currentPage = 1;
let cachedNews = null;

async function fetchNews() {
    if (cachedNews) return cachedNews;
    try {
        const response = await fetch(DATA_URL + '?t=' + Date.now());
        if (response.ok) {
            const news = await response.json();
            localStorage.setItem(STORAGE_KEY, JSON.stringify(news));
            cachedNews = news;
            return news;
        }
    } catch (e) {
        console.warn("Cargando desde copia local por falta de internet");
    }
    cachedNews = JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    return cachedNews;
}

async function renderHome(page = 1) {
    currentPage = page;
    const allNews = await fetchNews();
    const sortedNews = [...allNews].sort((a, b) => new Date(b.date) - new Date(a.date));
    const container = document.getElementById('news-container');
    const hero = document.getElementById('hero-section');
    const paginationEl = document.getElementById('pagination');

    if (!container) return;

    // Hero: solo en página 1, con la noticia más reciente
    if (hero) {
        if (sortedNews.length > 0 && page === 1) {
            const h = sortedNews[0];
            hero.innerHTML = `
                <div class="relative h-[450px] rounded-3xl overflow-hidden cursor-pointer group shadow-2xl mb-4" onclick="location.href='article.html?id=${h.id}'">
                    <img src="${h.images[0]}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" alt="${h.title}">
                    <div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent p-8 flex flex-col justify-end">
                        <span class="bg-blue-600 text-white px-3 py-1 rounded-full text-[10px] font-bold w-fit mb-3 uppercase">${h.category}</span>
                        <h1 class="text-white text-3xl md:text-5xl font-bold leading-tight">${h.title}</h1>
                    </div>
                </div>`;
        } else {
            hero.innerHTML = '';
        }
    }

    // En página 1 quitamos el hero del listado; en otras páginas mostramos todas
    const listNews = (page === 1) ? sortedNews.slice(1) : sortedNews;
    const totalPages = Math.ceil(listNews.length / ITEMS_PER_PAGE);
    const start = (page - 1) * ITEMS_PER_PAGE;
    const paginated = listNews.slice(start, start + ITEMS_PER_PAGE);

    container.innerHTML = paginated.map(n => `
        <article class="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer" onclick="location.href='article.html?id=${n.id}'">
            <img src="${n.images[0]}" class="w-full h-44 object-cover" alt="${n.title}" loading="lazy">
            <div class="p-4">
                <span class="text-blue-600 font-bold text-[9px] uppercase">${n.category}</span>
                <h3 class="font-bold my-2 line-clamp-2 text-gray-800">${n.title}</h3>
                <p class="text-gray-400 text-[10px]">${new Date(n.date).toLocaleDateString('es-ES')}</p>
            </div>
        </article>
    `).join('');

    // Renderizar trending (top 5 más vistos)
    const trendingEl = document.getElementById('trending-container');
    if (trendingEl) {
        const top5 = [...sortedNews]
            .sort((a, b) => (b.views || 0) - (a.views || 0))
            .slice(0, 5);
        trendingEl.innerHTML = top5.map((n, i) => `
            <div class="flex gap-3 cursor-pointer group" onclick="location.href='article.html?id=${n.id}'">
                <span class="text-3xl font-black text-gray-100 leading-none group-hover:text-blue-100 transition-colors">${i + 1}</span>
                <div>
                    <p class="text-xs font-bold text-blue-600 uppercase mb-1">${n.category}</p>
                    <p class="text-sm font-semibold text-gray-800 leading-snug group-hover:text-blue-600 transition-colors line-clamp-2">${n.title}</p>
                </div>
            </div>
        `).join('');
    }

    // Paginación numérica
    if (paginationEl && totalPages > 1) {
        renderPagination(paginationEl, currentPage, totalPages);
    } else if (paginationEl) {
        paginationEl.innerHTML = '';
    }
}

function renderPagination(el, current, total) {
    const btnBase = 'w-10 h-10 rounded-full text-sm font-bold transition-all flex items-center justify-center';
    const btnActive = 'bg-black text-white';
    const btnInactive = 'bg-gray-100 text-gray-600 hover:bg-gray-200';
    const btnDisabled = 'bg-gray-50 text-gray-300 cursor-not-allowed';

    // Calcular rango de páginas visibles (máx 5 alrededor de la actual)
    let pages = [];
    const delta = 2;
    for (let i = Math.max(1, current - delta); i <= Math.min(total, current + delta); i++) {
        pages.push(i);
    }

    let html = '';

    // Botón anterior
    if (current > 1) {
        html += `<button onclick="goToPage(${current - 1})" class="${btnBase} ${btnInactive}" aria-label="Página anterior">‹</button>`;
    } else {
        html += `<button disabled class="${btnBase} ${btnDisabled}" aria-label="Página anterior">‹</button>`;
    }

    // Primera página + ellipsis
    if (pages[0] > 1) {
        html += `<button onclick="goToPage(1)" class="${btnBase} ${btnInactive}">1</button>`;
        if (pages[0] > 2) html += `<span class="w-10 h-10 flex items-center justify-center text-gray-300 text-sm">…</span>`;
    }

    // Páginas centrales
    pages.forEach(p => {
        html += `<button onclick="goToPage(${p})" class="${btnBase} ${p === current ? btnActive : btnInactive}" aria-current="${p === current ? 'page' : 'false'}">${p}</button>`;
    });

    // Última página + ellipsis
    if (pages[pages.length - 1] < total) {
        if (pages[pages.length - 1] < total - 1) html += `<span class="w-10 h-10 flex items-center justify-center text-gray-300 text-sm">…</span>`;
        html += `<button onclick="goToPage(${total})" class="${btnBase} ${btnInactive}">${total}</button>`;
    }

    // Botón siguiente
    if (current < total) {
        html += `<button onclick="goToPage(${current + 1})" class="${btnBase} ${btnInactive}" aria-label="Página siguiente">›</button>`;
    } else {
        html += `<button disabled class="${btnBase} ${btnDisabled}" aria-label="Página siguiente">›</button>`;
    }

    el.innerHTML = html;
}

function goToPage(page) {
    renderHome(page);
    // Scroll suave al inicio del listado de noticias
    const newsSection = document.getElementById('news-container');
    if (newsSection) {
        newsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

window.onload = () => renderHome(1);
