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
// Estas son EXACTAMENTE las mismas categorías que acepta el generador
// (VALID_CATEGORIES en scripts/generate_site.py) — no se puede agregar
// ninguna otra porque el servidor la rechazaría de todos modos.
const VALID_CATEGORIES = ['Mundo', 'Politica', 'Politica internacional', 'Tecnología', 'Finanzas', 'Deportes', 'Cultura', 'Videojuegos'];

function getCategories() {
    return VALID_CATEGORIES;
}
function renderCategories() {
    const cats = getCategories();
    const select = document.getElementById('category');
    if (select) select.innerHTML = cats.map(c => `<option value="${c}">${c}</option>`).join('');
}
function addNewCategory() {
    alert('Las categorías están fijas para que coincidan con las que acepta el generador del sitio. Si necesitas una categoría nueva, avísale al desarrollador para agregarla en ambos lugares a la vez (panel y generador).');
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

// --- PUBLICACIÓN (delega TODO en el generador vía GitHub Actions —
// el panel nunca escribe HTML directamente, solo describe la acción) ---
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

            const id = document.getElementById('edit-id').value;
            const payload = {
                action: id ? 'edit' : 'create',
                id: id ? parseInt(id) : Date.now(),
                title: document.getElementById('title').value,
                content: document.getElementById('content').value,
                category: document.getElementById('category').value,
                author: document.getElementById('author').value || 'Redacción',
            };
            if (currentImages.length > 0) payload.images = currentImages;
            if (!id) payload.date = new Date().toISOString();

            // Validación local rápida, para no hacer esperar al usuario si algo
            // obvio falta — pero la validación que de verdad manda es la del
            // generador del lado del servidor (misma lógica, una sola fuente
            // de verdad); esto es solo para feedback instantáneo.
            const localError = quickValidate(payload);
            if (localError) { alert('⚠️ ' + localError); return; }

            submitBtn.disabled = true;
            submitBtn.innerText = 'Publicando...';

            try {
                await dispatchPublish(payload, config, submitBtn);
            } catch (err) {
                alert('❌ ' + err.message);
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerText = 'Publicar Noticia';
            }
        };
    }
});

// Validación ligera en el navegador (mismas reglas mínimas que el generador,
// para feedback instantáneo — la autoridad final es siempre el servidor).
function quickValidate(payload) {
    const templateMarkers = ['Título\n', 'Categoría\n', 'Desarrollo de la noticia', 'no inventada', 'Lorem ipsum', 'PLACEHOLDER'];
    if (!payload.title || !payload.title.trim()) return 'El título no puede estar vacío.';
    if (!payload.content || payload.content.trim().split(/\s+/).length < 100) return 'El contenido debe tener al menos 100 palabras.';
    if (!payload.category || !VALID_CATEGORIES.includes(payload.category)) return 'Debes elegir una categoría válida de la lista.';
    if (!payload.author || !payload.author.trim()) return 'El autor no puede estar vacío.';
    for (const m of templateMarkers) {
        if (payload.title.includes(m) || payload.content.includes(m)) {
            return `El contenido parece tener texto de plantilla sin borrar ("${m.trim()}").`;
        }
    }
    return null;
}

// Sube data/_pending_publish.json y dispara el workflow "Publicación manual
// (panel admin)", que corre scripts/manual_publish.py — el MISMO generador
// que usa la automatización. Luego espera (polling) a que termine y confirma
// éxito o error real, sin adivinar.
async function dispatchPublish(payload, config, submitBtn) {
    const pendingUrl = `https://api.github.com/repos/${config.owner}/${config.repo}/contents/data/_pending_publish.json`;
    let sha = '';
    try {
        const res = await fetch(pendingUrl, { headers: { 'Authorization': `token ${config.token}` } });
        if (res.ok) { const d = await res.json(); sha = d.sha; }
    } catch (e) {}

    const content = btoa(unescape(encodeURIComponent(JSON.stringify(payload, null, 2))));
    const putBody = { message: `Panel: solicitud de ${payload.action}`, content };
    if (sha) putBody.sha = sha;
    const putRes = await fetch(pendingUrl, {
        method: 'PUT',
        headers: { 'Authorization': `token ${config.token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(putBody),
    });
    if (!putRes.ok) throw new Error('No se pudo subir la solicitud a GitHub. Revisa tu Token.');

    const dispatchUrl = `https://api.github.com/repos/${config.owner}/${config.repo}/actions/workflows/manual-publish.yml/dispatches`;
    const dispatchTime = new Date();
    const dispatchRes = await fetch(dispatchUrl, {
        method: 'POST',
        headers: { 'Authorization': `token ${config.token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ref: 'main' }),
    });
    if (!dispatchRes.ok) throw new Error('No se pudo iniciar la publicación. Revisa tu Token (necesita permiso "repo").');

    submitBtn.innerText = 'Generando páginas del sitio...';
    const result = await pollWorkflowRun(config, dispatchTime, submitBtn);

    if (result === 'success') {
        alert('✅ ¡Publicado correctamente! El sitio ya se actualizó.');
        location.reload();
    } else if (result === 'failure') {
        throw new Error('El generador rechazó la publicación (revisa la pestaña "Actions" en GitHub para ver el motivo exacto). No se publicó nada.');
    } else {
        throw new Error('La publicación está tardando más de lo normal. Revisa la pestaña "Actions" en GitHub para ver el resultado.');
    }
}

// Espera a que aparezca y termine la ejecución del workflow disparada recién,
// revisando cada 3 segundos, hasta 90 segundos en total.
async function pollWorkflowRun(config, dispatchTime, submitBtn) {
    const runsUrl = `https://api.github.com/repos/${config.owner}/${config.repo}/actions/workflows/manual-publish.yml/runs?event=workflow_dispatch&per_page=5`;
    const maxWaitMs = 90000;
    const start = Date.now();

    let runId = null;
    while (Date.now() - start < maxWaitMs) {
        await new Promise(r => setTimeout(r, 3000));
        try {
            const res = await fetch(runsUrl, { headers: { 'Authorization': `token ${config.token}` } });
            if (res.ok) {
                const data = await res.json();
                const candidate = (data.workflow_runs || []).find(run => new Date(run.created_at) >= dispatchTime);
                if (candidate) {
                    runId = candidate.id;
                    if (candidate.status === 'completed') {
                        return candidate.conclusion === 'success' ? 'success' : 'failure';
                    }
                    submitBtn.innerText = 'Publicando... (' + candidate.status + ')';
                }
            }
        } catch (e) {}
    }
    return 'timeout';
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
// --- Fuente de datos real: siempre se lee news.json en vivo desde GitHub,
// nunca de localStorage (localStorage puede quedar desactualizado apenas
// otra persona, o la automatización, publican algo). ---
let currentNewsList = [];

function slugifyJs(text) {
    return (text || '').toString()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '') || 'articulo';
}
function articleUrlJs(n) {
    return `https://enfoquemundial.com/${slugifyJs(n.category)}/${slugifyJs(n.title)}-${n.id}/`;
}

async function fetchLiveNews(config) {
    const url = `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.dataPath}`;
    const res = await fetch(url, { headers: { 'Authorization': `token ${config.token}` } });
    if (!res.ok) throw new Error('No se pudo leer el estado actual del sitio desde GitHub.');
    const data = await res.json();
    const text = decodeURIComponent(escape(atob(data.content)));
    return JSON.parse(text);
}

function copyArticleLink(id) {
    const n = currentNewsList.find(a => a.id == id);
    const url = n ? articleUrlJs(n) : '';
    if (!url) return;
    const btn = document.getElementById(`copy-btn-${id}`);
    const showCopied = () => {
        if (!btn) return;
        const original = btn.innerText;
        btn.innerText = '¡Copiado!';
        setTimeout(() => { btn.innerText = original; }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(showCopied).catch(() => prompt('Copia el enlace:', url));
    } else {
        prompt('Copia el enlace:', url);
    }
}

async function renderAdminList() {
    const container = document.getElementById('admin-news-list');
    if (!container) return;
    const config = getGitHubConfig();
    if (!config) {
        container.innerHTML = `<div class="p-10 text-center text-gray-400 italic">Configura tu GitHub primero.</div>`;
        return;
    }
    container.innerHTML = `<div class="p-10 text-center text-gray-400 italic">Cargando noticias...</div>`;
    try {
        currentNewsList = await fetchLiveNews(config);
    } catch (e) {
        container.innerHTML = `<div class="p-10 text-center text-red-500 italic">${e.message}</div>`;
        return;
    }
    if (currentNewsList.length === 0) {
        container.innerHTML = `<div class="p-10 text-center text-gray-400 italic">No hay noticias.</div>`;
        return;
    }
    container.innerHTML = currentNewsList.map(n => `
        <div class="bg-white p-4 rounded-2xl flex justify-between items-center shadow-sm border mb-2">
            <div class="flex items-center gap-4">
                <img src="${n.images[0]}" class="w-12 h-12 rounded-lg object-cover">
                <div><h4 class="font-bold text-sm text-gray-800 line-clamp-1">${n.title}</h4><span class="text-[9px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full uppercase font-bold">${n.category}</span></div>
            </div>
            <div class="flex gap-2">
                <button onclick="copyArticleLink(${n.id})" id="copy-btn-${n.id}" class="p-2 text-green-600 bg-green-50 rounded-lg text-xs font-bold">Copiar enlace</button>
                <button onclick="editNews(${n.id})" class="p-2 text-blue-500 bg-blue-50 rounded-lg text-xs">Editar</button>
                <button onclick="deleteNews(${n.id})" class="p-2 text-red-500 bg-red-50 rounded-lg text-xs">Borrar</button>
            </div>
        </div>
    `).join('');
    if (window.lucide) lucide.createIcons();
}

function editNews(id) {
    const news = currentNewsList.find(n => n.id == id);
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

async function deleteNews(id) {
    if (!confirm('¿Eliminar esta noticia? Esto la borra del sitio de verdad, no solo de la lista.')) return;
    const config = getGitHubConfig();
    if (!config) { alert('Configura tu GitHub primero.'); return; }

    const btn = document.getElementById(`copy-btn-${id}`)?.parentElement?.querySelector('button:last-child') || null;
    if (btn) { btn.disabled = true; btn.innerText = 'Borrando...'; }

    try {
        await dispatchPublish({ action: 'delete', id: id }, config, btn || { innerText: '' });
    } catch (err) {
        alert('❌ ' + err.message);
        if (btn) { btn.disabled = false; btn.innerText = 'Borrar'; }
    }
}

function logout() { localStorage.removeItem('enfoque_mundial_logged'); window.location.href = 'index.html'; }
