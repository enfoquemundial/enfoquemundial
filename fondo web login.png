// --- GESTIÓN DE CONFIGURACIÓN DE GITHUB ---
const GITHUB_KEY = 'enfoque_mundial_github_config';
const STORAGE_KEY = 'enfoque_mundial_news';
const CATEGORIES_KEY = 'enfoque_mundial_categories';

function getGitHubConfig() {
    const config = localStorage.getItem(GITHUB_KEY);
    return (config && config !== "null") ? JSON.parse(config) : null;
}

function setGitHubConfig() {
    const token = prompt("1. Pega tu Personal Access Token (ghp_...):");
    if (!token) return null;
    const owner = prompt("2. Tu usuario de GitHub (ej: enfoquemundial):");
    if (!owner) return null;
    const repo = prompt("3. Nombre del repositorio (ej: noticia-web):");
    if (!repo) return null;

    const config = {
        token: token.trim(),
        owner: owner.trim(),
        repo: repo.trim(),
        branch: 'main',
        imagesPath: 'images/uploads',
        dataPath: 'data/news.json'
    };
    localStorage.setItem(GITHUB_KEY, JSON.stringify(config));
    alert("✅ Configuración guardada. Ahora puedes publicar.");
    return config;
}

function resetGitHubConfig() {
    if(confirm("¿Quieres cambiar el Token o la cuenta de GitHub?")) {
        localStorage.removeItem(GITHUB_KEY);
        setGitHubConfig();
        location.reload();
    }
}

let currentImages = [];

// --- NAVEGACIÓN ---
function showSection(section) {
    const dash = document.getElementById('section-dashboard');
    const create = document.getElementById('section-create');
    if (!dash || !create) return;
    if (section === 'dashboard') {
        dash.classList.remove('hidden');
        create.classList.add('hidden');
        renderAdminList();
    } else {
        dash.classList.add('hidden');
        create.classList.remove('hidden');
        renderCategories();
        if (!document.getElementById('edit-id').value) {
            document.getElementById('news-form')?.reset();
            currentImages = [];
            renderImagePreview();
        }
    }
    if (window.lucide) lucide.createIcons();
}

// --- CATEGORÍAS ---
function getCategories() {
    const data = localStorage.getItem(CATEGORIES_KEY);
    return data ? JSON.parse(data) : ['Tecnología', 'Mundo', 'Negocios', 'Deportes', 'Cultura'];
}
function renderCategories() {
    const cats = getCategories();
    const select = document.getElementById('category');
    if (select) select.innerHTML = cats.map(c => `<option value="${c}">${c}</option>`).join('');
}
function addNewCategory() {
    const newCat = prompt('Nombre de la nueva categoría:');
    if (newCat) {
        let cats = getCategories();
        if (!cats.includes(newCat.trim())) {
            cats.push(newCat.trim());
            localStorage.setItem(CATEGORIES_KEY, JSON.stringify(cats));
            renderCategories();
        }
    }
}

// --- IMÁGENES ---
async function handleFileUpload(input) {
    let config = getGitHubConfig();
    if (!config) config = setGitHubConfig();
    if (!config) return;

    const files = input.files;
    if (!files || files.length === 0) return;

    const btn = input.parentElement;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = "<span class='text-blue-600 animate-pulse font-bold'>Subiendo a GitHub...</span>";

    for (const file of Array.from(files)) {
        try {
            const base64 = await toBase64(file);
            const url = await uploadToGitHub(base64, file.name, config);
            currentImages.push(url);
            renderImagePreview();
        } catch (err) {
            alert("Error: " + err.message);
        }
    }
    btn.innerHTML = originalHTML;
}

function toBase64(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = Math.min(img.width, 1000);
                canvas.height = (canvas.width / img.width) * img.height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                resolve(canvas.toDataURL('image/jpeg', 0.8));
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

async function uploadToGitHub(base64Data, fileName, config) {
    const cleanBase64 = base64Data.split(',')[1];
    const finalFileName = `${Date.now()}_${fileName.replace(/\s+/g, '_')}`;
    const url = `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.imagesPath}/${finalFileName}`;
    const response = await fetch(url, {
        method: 'PUT',
        headers: { 'Authorization': `token ${config.token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Subida de foto`, content: cleanBase64 })
    });
    if (response.ok) {
        const data = await response.json();
        return data.content.download_url;
    }
    throw new Error('Error al subir imagen. Verifica el Token.');
}

// --- PUBLICACIÓN ---
window.addEventListener('DOMContentLoaded', () => {
    renderAdminList();
    const form = document.getElementById('news-form');
    if (form) {
        form.onsubmit = async (e) => {
            e.preventDefault();
            let config = getGitHubConfig();
            if (!config) config = setGitHubConfig();
            if (!config) return;

            const submitBtn = document.getElementById('submit-btn');
            submitBtn.disabled = true;
            submitBtn.innerText = "Sincronizando con GitHub...";

            const id = document.getElementById('edit-id').value;
            const news = JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
            const newsData = {
                id: id ? parseInt(id) : Date.now(),
                title: document.getElementById('title').value,
                content: document.getElementById('content').value,
                category: document.getElementById('category').value,
                author: document.getElementById('author').value || 'Redacción',
                date: id ? news.find(n => n.id == id).date : new Date().toISOString(),
                images: currentImages.length > 0 ? currentImages : ['https://via.placeholder.com/800'],
                views: id ? (news.find(n => n.id == id).views || 0) : 0
            };
            const updatedNews = id ? news.map(n => n.id == id ? newsData : n) : [newsData, ...news];

            try {
                const ok = await syncNewsToGitHub(updatedNews, config);
                if (ok) {
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedNews));
                    alert("✅ ¡PUBLICADO EN GITHUB CORRECTAMENTE!");
                    location.reload();
                }
            } catch (err) {
                alert("Error de sincronización: " + err.message);
                submitBtn.disabled = false;
                submitBtn.innerText = "Publicar Noticia";
            }
        };
    }
});

async function syncNewsToGitHub(newsArray, config) {
    const url = `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.dataPath}`;
    let sha = "";
    try {
        const res = await fetch(url, { headers: { 'Authorization': `token ${config.token}` } });
        if (res.ok) { const data = await res.json(); sha = data.sha; }
    } catch (e) {}
    const content = btoa(unescape(encodeURIComponent(JSON.stringify(newsArray, null, 2))));
    const response = await fetch(url, {
        method: 'PUT',
        headers: { 'Authorization': `token ${config.token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: "Update news", content: content, sha: sha })
    });
    return response.ok;
}

function renderImagePreview() {
    const container = document.getElementById('image-preview-container');
    if (container) {
        container.innerHTML = currentImages.map((img, idx) => `
            <div class="relative h-20 w-20 flex-shrink-0">
                <img src="${img}" class="w-full h-full object-cover rounded-xl border">
                <button type="button" onclick="removeImg(${idx})" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-[10px]">×</button>
            </div>
        `).join('');
    }
}
function removeImg(idx) { currentImages.splice(idx, 1); renderImagePreview(); }
function addImage() {
    const url = document.getElementById('image-url').value.trim();
    if (url) { currentImages.push(url); document.getElementById('image-url').value = ''; renderImagePreview(); }
}
function renderAdminList() {
    const news = JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    const container = document.getElementById('admin-news-list');
    if (!container) return;
    if (news.length === 0) {
        container.innerHTML = `<div class="p-10 text-center text-gray-400 italic">No hay noticias.</div>`;
        return;
    }
    container.innerHTML = news.map(n => `
        <div class="bg-white p-4 rounded-2xl flex justify-between items-center shadow-sm border mb-2">
            <div class="flex items-center gap-4">
                <img src="${n.images[0]}" class="w-12 h-12 rounded-lg object-cover">
                <div><h4 class="font-bold text-sm text-gray-800 line-clamp-1">${n.title}</h4><span class="text-[9px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full uppercase font-bold">${n.category}</span></div>
            </div>
            <div class="flex gap-2">
                <button onclick="editNews(${n.id})" class="p-2 text-blue-500 bg-blue-50 rounded-lg text-xs">Editar</button>
                <button onclick="deleteNews(${n.id})" class="p-2 text-red-500 bg-red-50 rounded-lg text-xs">Borrar</button>
            </div>
        </div>
    `).join('');
    if (window.lucide) lucide.createIcons();
}
function editNews(id) {
    const news = (JSON.parse(localStorage.getItem(STORAGE_KEY)) || []).find(n => n.id == id);
    if (!news) return;
    document.getElementById('edit-id').value = news.id;
    document.getElementById('title').value = news.title;
    document.getElementById('content').value = news.content;
    renderCategories();
    document.getElementById('category').value = news.category;
    document.getElementById('author').value = news.author;
    currentImages = [...(news.images || [])];
    showSection('create');
    renderImagePreview();
}
function deleteNews(id) {
    if (confirm('¿Eliminar noticia?')) {
        const updated = (JSON.parse(localStorage.getItem(STORAGE_KEY)) || []).filter(n => n.id != id);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        const config = getGitHubConfig();
        if (config) syncNewsToGitHub(updated, config);
        renderAdminList();
    }
}
function logout() { localStorage.removeItem('enfoque_mundial_logged'); window.location.href = 'index.html'; }
