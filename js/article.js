const GITHUB_USER = 'enfoquemundial';
const GITHUB_REPO = 'enfoquemundial';
const DATA_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/main/data/news.json`;

async function fetchSingleNews() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');

    try {
        const response = await fetch(DATA_URL + '?t=' + Date.now());
        const news = await response.json();
        const article = news.find(n => n.id == id);

        if (article) {
            renderArticle(article);
        } else {
            document.body.innerHTML = "<h1>Noticia no encontrada</h1>";
        }
    } catch (e) {
        console.error("Error cargando noticia:", e);
    }
}

function renderArticle(n) {
    document.title = n.title;
    document.getElementById('art-category').innerText = n.category;
    document.getElementById('art-title').innerText = n.title;
    document.getElementById('art-author').innerText = n.author;
    document.getElementById('art-date').innerText = new Date(n.date).toLocaleDateString();
    document.getElementById('art-content').innerText = n.content;

    const imgContainer = document.getElementById('art-images');
    if (imgContainer) {
        imgContainer.innerHTML = n.images.map(img => `
            <img src="${img}" class="w-full rounded-3xl mb-4 shadow-lg">
        `).join('');
    }
}

window.onload = fetchSingleNews;
