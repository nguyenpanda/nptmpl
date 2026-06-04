/**
 * nptmpl Registry UI - Main JavaScript
 */

// Icon Configuration
const iconMap = {
    'py': { color: '#3776ab', icon: 'M14.25 18l.9-2m0 0l.9 2m-2.7-2.1l-.9 2m1.8-2l-.9-2m-5.4 5V6a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V19a2 2 0 01-2 2H7a2 2 0 01-2-2z' },
    'cpp': { color: '#00599c', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
    'hpp': { color: '#00599c', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
    'c': { color: '#a8b9cc', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
    'h': { color: '#a8b9cc', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
    'cu': { color: '#76b900', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    'cuh': { color: '#76b900', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    'md': { color: '#083fa1', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z' },
    'txt': { color: '#888', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
    'git': { color: '#f05032', icon: 'M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.341-3.369-1.341-.454-1.152-1.11-1.459-1.11-1.459-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.441 1.087 3.035.831.092-.646.333-1.087.602-1.337-2.22-.251-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12c0-5.523-4.477-10-10-10z' },
    'license': { color: '#fbc02d', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 5.04 12.038 12.038 0 00-3.326 7.92c0 6.623 4.512 12.242 10.73 13.791a1 1 0 002.43 0c6.218-1.55 10.73-7.168 10.73-13.791 0-2.83-.984-5.43-2.644-7.472z' },
    'lock': { color: '#666666', icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z' }
};

function getFileIconSVG(path, isDirectory) {
    if (isDirectory) {
        return `<svg class="w-4 h-4 text-zinc-500" fill="currentColor" viewBox="0 0 20 20"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"></path></svg>`;
    }
    
    const filename = path.split('/').pop().toLowerCase();
    const ext = filename.split('.').pop();
    
    let config = iconMap[ext];
    if (filename.includes('git')) config = iconMap['git'];
    if (filename.includes('license')) config = iconMap['license'];
    if (filename.endsWith('.lock')) config = iconMap['lock'];
    if (filename === 'makefile' || filename === 'cmakelists.txt') config = iconMap['h'];
    
    if (!config) {
        return `<svg class="w-4 h-4 text-zinc-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>`;
    }
    
    return `<svg class="w-4 h-4" style="color: ${config.color}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${config.icon}"></path></svg>`;
}

// Density and Grid Controls
function setViewDensity(mode) {
    const body = document.getElementById('mainBody');
    const btnGrid = document.getElementById('btn-grid');
    const btnSpark = document.getElementById('btn-spark');
    const colSelector = document.getElementById('colSelector');
    
    if (!body) return;

    localStorage.setItem('nptmpl_view_density', mode);
    
    if (mode === 'spark') {
        body.classList.add('view-mode-spark');
        if (colSelector) {
            colSelector.style.opacity = '0.1';
            colSelector.style.pointerEvents = 'none';
        }
        if (btnSpark) btnSpark.classList.add('neon-bg', 'text-black');
        if (btnGrid) btnGrid.classList.remove('neon-bg', 'text-black');
    } else {
        body.classList.remove('view-mode-spark');
        if (colSelector) {
            colSelector.style.opacity = '1';
            colSelector.style.pointerEvents = 'auto';
        }
        if (btnGrid) btnGrid.classList.add('neon-bg', 'text-black');
        if (btnSpark) btnSpark.classList.remove('neon-bg', 'text-black');
    }
}

function setGridColumns(n) {
    const container = document.getElementById('templateContainer');
    if (!container) return;

    localStorage.setItem('nptmpl_grid_cols', n);
    
    // Remove all possible col classes
    container.classList.remove('md:grid-cols-2', 'md:grid-cols-3', 'md:grid-cols-4', 'md:grid-cols-6');
    container.classList.add(`md:grid-cols-${n}`);

    // Update UI
    [2, 3, 4, 6].forEach(num => {
        const btn = document.getElementById(`btn-col-${num}`);
        if (btn) {
            if (num === n) {
                btn.classList.add('neon-bg', 'text-black', 'neon-border');
                btn.classList.remove('text-zinc-500');
            } else {
                btn.classList.remove('neon-bg', 'text-black', 'neon-border');
                btn.classList.add('text-zinc-500');
            }
        }
    });
}

// Toast Notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const isError = type === 'error';
    
    toast.className = `toast-enter flex items-center p-5 w-full max-w-xs text-white bg-zinc-950 rounded-2xl shadow-2xl border-2 ${isError ? 'border-red-500/50' : 'neon-border'}`;
    toast.innerHTML = `
        <div class="inline-flex items-center justify-center shrink-0 w-10 h-10 rounded-xl ${isError ? 'bg-red-900/40 text-red-500' : 'bg-emerald-500/20 text-white'}">
            ${isError 
                ? '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"></path></svg>'
                : '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg>'
            }
        </div>
        <div class="ml-4 text-xs font-black uppercase tracking-widest">${message}</div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.replace('toast-enter', 'toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 6000);
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    // Restore display settings
    const savedDensity = localStorage.getItem('nptmpl_view_density') || 'grid';
    const savedCols = parseInt(localStorage.getItem('nptmpl_grid_cols')) || 3;
    
    setViewDensity(savedDensity);
    setGridColumns(savedCols);
});
