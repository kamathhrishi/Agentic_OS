// OS State
let windowIdCounter = 0;
const windows = new Map();
let draggedWindow = null;
let dragOffset = { x: 0, y: 0 };

// App templates
const appTemplates = {
    file_manager: {
        title: 'File Manager',
        icon: 'fa-folder',
        color: 'text-blue-400',
        content: `
            <div class="file-manager-container h-full flex flex-col">
                <div class="file-manager-toolbar mb-4 flex items-center gap-2">
                    <button class="toolbar-btn" onclick="fileManagerRefresh()" title="Refresh">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                    <button class="toolbar-btn" onclick="fileManagerNewFolder()" title="New Folder">
                        <i class="fas fa-folder-plus"></i>
                    </button>
                    <button class="toolbar-btn" onclick="fileManagerNewFile()" title="New File">
                        <i class="fas fa-file-plus"></i>
                    </button>
                    <div class="flex-1"></div>
                    <div class="current-path text-sm text-text-secondary" id="current-path">/</div>
                </div>
                <div id="file-manager-content" class="flex-1 overflow-auto">
                    <div class="file-manager-grid" id="file-list">
                        <div class="text-center text-text-secondary">Loading...</div>
                    </div>
                </div>
            </div>
        `
    },
    terminal: {
        title: 'Terminal',
        icon: 'fa-terminal',
        color: 'text-green-400',
        content: `
            <div class="terminal-content h-full">
                <div class="terminal-output">
                    <span class="terminal-prompt">$</span> Welcome to Agentic OS Terminal
                </div>
                <div class="terminal-output">
                    <span class="terminal-prompt">$</span> Type commands to interact with your OS
                </div>
                <div class="terminal-output">
                    <span class="terminal-prompt">$</span> Use the chat assistant for AI-powered control
                </div>
                <div class="terminal-output mt-4">
                    <span class="terminal-prompt">$</span> <span id="terminal-cursor">_</span>
                </div>
            </div>
        `
    },
    calculator: {
        title: 'Calculator',
        icon: 'fa-calculator',
        color: 'text-purple-400',
        content: `
            <div class="h-full flex flex-col">
                <div class="calculator-display text-white" id="calc-display">0</div>
                <div class="calculator-buttons">
                    <button class="calc-btn" onclick="calcInput('C')">C</button>
                    <button class="calc-btn" onclick="calcInput('±')">±</button>
                    <button class="calc-btn" onclick="calcInput('%')">%</button>
                    <button class="calc-btn operator" onclick="calcInput('/')">÷</button>
                    <button class="calc-btn" onclick="calcInput('7')">7</button>
                    <button class="calc-btn" onclick="calcInput('8')">8</button>
                    <button class="calc-btn" onclick="calcInput('9')">9</button>
                    <button class="calc-btn operator" onclick="calcInput('*')">×</button>
                    <button class="calc-btn" onclick="calcInput('4')">4</button>
                    <button class="calc-btn" onclick="calcInput('5')">5</button>
                    <button class="calc-btn" onclick="calcInput('6')">6</button>
                    <button class="calc-btn operator" onclick="calcInput('-')">-</button>
                    <button class="calc-btn" onclick="calcInput('1')">1</button>
                    <button class="calc-btn" onclick="calcInput('2')">2</button>
                    <button class="calc-btn" onclick="calcInput('3')">3</button>
                    <button class="calc-btn operator" onclick="calcInput('+')">+</button>
                    <button class="calc-btn" onclick="calcInput('0')" style="grid-column: span 2;">0</button>
                    <button class="calc-btn" onclick="calcInput('.')">.</button>
                    <button class="calc-btn operator" onclick="calcInput('=')">=</button>
                </div>
            </div>
        `
    },
    notepad: {
        title: 'Notepad',
        icon: 'fa-file-alt',
        color: 'text-yellow-400',
        content: `
            <div class="notepad-container h-full flex flex-col">
                <div class="notepad-toolbar mb-2 flex items-center gap-2">
                    <button class="toolbar-btn" onclick="notepadOpen()" title="Open File">
                        <i class="fas fa-folder-open"></i> Open
                    </button>
                    <button class="toolbar-btn" onclick="notepadSave()" title="Save File">
                        <i class="fas fa-save"></i> Save
                    </button>
                    <button class="toolbar-btn" onclick="notepadSaveAs()" title="Save As">
                        <i class="fas fa-save"></i> Save As
                    </button>
                    <div class="flex-1"></div>
                    <input type="text" id="notepad-filename" placeholder="filename.txt" 
                        class="px-3 py-1 text-sm bg-input border border-border rounded-lg" 
                        style="min-width: 200px;">
                </div>
                <textarea id="notepad-editor" class="notepad-editor flex-1" placeholder="Start typing...">Welcome to Notepad!

This is a simple text editor in your Agentic OS.

You can type anything here...</textarea>
            </div>
        `
    },
    settings: {
        title: 'Settings',
        icon: 'fa-cog',
        color: 'text-slate-400',
        content: `
            <div class="space-y-4">
                <div class="bg-slate-700/50 p-4 rounded-lg">
                    <h4 class="text-white font-semibold mb-2">Appearance</h4>
                    <p class="text-slate-300 text-sm">Theme settings coming soon...</p>
                </div>
                <div class="bg-slate-700/50 p-4 rounded-lg">
                    <h4 class="text-white font-semibold mb-2">System</h4>
                    <p class="text-slate-300 text-sm">System preferences coming soon...</p>
                </div>
            </div>
        `
    },
    default: {
        title: 'Application',
        icon: 'fa-window-maximize',
        color: 'text-slate-400',
        content: `
            <div class="flex items-center justify-center h-full text-slate-400">
                <div class="text-center">
                    <i class="fas fa-window-maximize text-6xl mb-4"></i>
                    <p>Application Window</p>
                </div>
            </div>
        `
    }
};

// Calculator state
let calcState = {
    display: '0',
    operand1: null,
    operand2: null,
    operator: null,
    waitingForOperand: false
};

function calcInput(value) {
    const display = document.getElementById('calc-display');
    
    if (value === 'C') {
        calcState = { display: '0', operand1: null, operand2: null, operator: null, waitingForOperand: false };
        display.textContent = '0';
        return;
    }
    
    if (value === '±') {
        calcState.display = (parseFloat(calcState.display) * -1).toString();
        display.textContent = calcState.display;
        return;
    }
    
    if (['+', '-', '*', '/', '%'].includes(value)) {
        if (calcState.operand1 === null) {
            calcState.operand1 = parseFloat(calcState.display);
        } else if (calcState.operator) {
            calcState.operand2 = parseFloat(calcState.display);
            calcState.operand1 = calculate();
            display.textContent = calcState.operand1.toString();
            calcState.operand2 = null;
        }
        calcState.operator = value;
        calcState.waitingForOperand = true;
        return;
    }
    
    if (value === '=') {
        if (calcState.operator && calcState.operand1 !== null) {
            calcState.operand2 = parseFloat(calcState.display);
            calcState.operand1 = calculate();
            display.textContent = calcState.operand1.toString();
            calcState.operator = null;
            calcState.operand2 = null;
            calcState.waitingForOperand = true;
        }
        return;
    }
    
    if (calcState.waitingForOperand) {
        calcState.display = value;
        calcState.waitingForOperand = false;
    } else {
        calcState.display = calcState.display === '0' ? value : calcState.display + value;
    }
    
    display.textContent = calcState.display;
}

function calculate() {
    const { operand1, operand2, operator } = calcState;
    switch (operator) {
        case '+': return operand1 + operand2;
        case '-': return operand1 - operand2;
        case '*': return operand1 * operand2;
        case '/': return operand2 !== 0 ? operand1 / operand2 : 0;
        case '%': return operand1 % operand2;
        default: return operand2 || operand1;
    }
}

// Set sidebar width CSS variable
function updateSidebarWidth() {
    const sidebar = document.getElementById('chat-sidebar');
    const width = sidebar.classList.contains('collapsed') ? 60 : 380;
    document.documentElement.style.setProperty('--sidebar-width', `${width}px`);
}

// Window Management
function createWindow(appName = 'default', title = null, position = null) {
    const app = appTemplates[appName] || appTemplates.default;
    const windowId = `window-${windowIdCounter++}`;
    
    const window = document.createElement('div');
    window.id = windowId;
    window.className = 'window';
    
    // Position - account for sidebar
    if (!position) {
        const sidebarWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')) || 380;
        position = {
            top: 100 + (windowIdCounter % 3) * 50,
            left: 100 + (windowIdCounter % 3) * 50
        };
        // Ensure window doesn't overlap with sidebar and account for menu bar
        const menuBarHeight = 28;
        position.top += menuBarHeight;
        if (position.left + 600 > window.innerWidth - sidebarWidth) {
            position.left = Math.max(50, window.innerWidth - sidebarWidth - 650);
        }
    }
    window.style.top = `${position.top}px`;
    window.style.left = `${position.left}px`;
    window.style.width = '600px';
    window.style.height = '450px';
    
    // Window content with macOS traffic lights
    window.innerHTML = `
        <div class="window-header">
            <div class="window-title-area">
                <div class="macos-traffic-lights">
                    <div class="traffic-light close" title="Close"></div>
                    <div class="traffic-light minimize" title="Minimize"></div>
                    <div class="traffic-light maximize" title="Maximize"></div>
                </div>
                <div class="window-title">
                    <i class="fas ${app.icon} ${app.color}"></i>
                    <span>${title || app.title}</span>
                </div>
            </div>
        </div>
        <div class="window-content">${app.content}</div>
    `;
    
    // Window controls
    const header = window.querySelector('.window-header');
    const minimizeBtn = window.querySelector('.traffic-light.minimize');
    const maximizeBtn = window.querySelector('.traffic-light.maximize');
    const closeBtn = window.querySelector('.traffic-light.close');
    
    // Dragging (excluding traffic lights)
    header.addEventListener('mousedown', (e) => {
        if (e.target.closest('.macos-traffic-lights')) return;
        draggedWindow = window;
        const rect = window.getBoundingClientRect();
        dragOffset.x = e.clientX - rect.left;
        dragOffset.y = e.clientY - rect.top;
        bringToFront(window);
        updateDock();
    });
    
    minimizeBtn.addEventListener('click', () => minimizeWindow(windowId));
    maximizeBtn.addEventListener('click', () => maximizeWindow(windowId));
    closeBtn.addEventListener('click', () => closeWindow(windowId));
    
    document.getElementById('windows-container').appendChild(window);
    windows.set(windowId, { element: window, app: appName, minimized: false, maximized: false });
    
    bringToFront(window);
    updateDock();
    
    // Initialize file manager if needed
    if (appName === 'file_manager') {
        setTimeout(() => {
            if (typeof fileManagerRefresh === 'function') {
                fileManagerRefresh();
            }
        }, 100);
    }
    
    return windowId;
}

function bringToFront(window) {
    Array.from(document.querySelectorAll('.window')).forEach(w => {
        w.style.zIndex = '10';
    });
    window.style.zIndex = '100';
}

function minimizeWindow(windowId) {
    const win = windows.get(windowId);
    if (!win) return;
    
    win.minimized = !win.minimized;
    win.element.classList.toggle('minimized', win.minimized);
    updateDock();
}

function maximizeWindow(windowId) {
    const win = windows.get(windowId);
    if (!win) return;
    
    win.maximized = !win.maximized;
    win.element.classList.toggle('maximized', win.maximized);
    // If not maximized, restore original dimensions
    if (!win.maximized) {
        win.element.style.width = '';
        win.element.style.height = '';
    }
    updateDock();
}

function closeWindow(windowId) {
    const win = windows.get(windowId);
    if (!win) return;
    
    win.element.remove();
    windows.delete(windowId);
    updateDock();
}

function closeAllWindows() {
    windows.forEach((win, id) => closeWindow(id));
}

function updateDock() {
    const dockItems = document.getElementById('dock-items');
    dockItems.innerHTML = '';
    
    // Add apps to dock
    const dockApps = ['file_manager', 'terminal', 'calculator', 'notepad'];
    dockApps.forEach(appName => {
        const app = appTemplates[appName];
        if (!app) return;
        
        const dockItem = document.createElement('div');
        dockItem.className = 'dock-item';
        dockItem.dataset.app = appName;
        dockItem.innerHTML = `
            <div class="dock-icon-wrapper">
                <i class="fas ${app.icon} ${app.color} text-3xl"></i>
            </div>
        `;
        
        dockItem.addEventListener('click', () => {
            createWindow(appName);
        });
        
        dockItems.appendChild(dockItem);
    });
    
    // Add open windows to dock
    windows.forEach((win, id) => {
        const app = appTemplates[win.app];
        if (!app) return;
        
        const dockItem = document.createElement('div');
        dockItem.className = `dock-item ${win.minimized ? '' : 'active'}`;
        dockItem.dataset.windowId = id;
        dockItem.innerHTML = `
            <div class="dock-icon-wrapper">
                <i class="fas ${app.icon} ${app.color} text-3xl"></i>
            </div>
        `;
        
        dockItem.addEventListener('click', () => {
            if (win.minimized) {
                minimizeWindow(id);
            } else {
                bringToFront(win.element);
            }
            updateDock();
        });
        
        dockItems.appendChild(dockItem);
    });
}

// Mouse events for dragging
document.addEventListener('mousemove', (e) => {
    if (draggedWindow && !draggedWindow.classList.contains('maximized')) {
        const sidebarWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')) || 380;
        const menuBarHeight = 28;
        const dockHeight = 80;
        const maxLeft = window.innerWidth - sidebarWidth - draggedWindow.offsetWidth;
        const maxTop = window.innerHeight - dockHeight - draggedWindow.offsetHeight;
        const newLeft = Math.max(0, Math.min(e.clientX - dragOffset.x, maxLeft));
        const newTop = Math.max(menuBarHeight, Math.min(e.clientY - dragOffset.y, maxTop));
        draggedWindow.style.left = `${newLeft}px`;
        draggedWindow.style.top = `${newTop}px`;
    }
});

document.addEventListener('mouseup', () => {
    draggedWindow = null;
});

// Desktop app icons
document.querySelectorAll('#desktop-app-icons .desktop-icon').forEach(icon => {
    icon.addEventListener('dblclick', () => {
        const app = icon.dataset.app;
        createWindow(app);
    });
});

// Desktop right-click context menu
const desktop = document.getElementById('desktop');
const desktopFiles = document.getElementById('desktop-files');
const contextMenu = document.getElementById('desktop-context-menu');

desktop.addEventListener('contextmenu', (e) => {
    // Don't show context menu if clicking on an icon
    if (e.target.closest('.desktop-icon, .desktop-file-icon')) {
        return;
    }
    e.preventDefault();
    contextMenu.style.left = `${e.clientX}px`;
    contextMenu.style.top = `${e.clientY}px`;
    contextMenu.classList.remove('hidden');
});

document.addEventListener('click', (e) => {
    if (!contextMenu.contains(e.target)) {
        contextMenu.classList.add('hidden');
    }
});

// Load desktop files on startup
refreshDesktop();

// macOS doesn't use start menu - apps are launched from Dock or desktop icons

// Sidebar toggle
const sidebar = document.getElementById('chat-sidebar');
const toggleSidebarBtn = document.getElementById('toggle-sidebar');

function toggleSidebar() {
    sidebar.classList.toggle('collapsed');
    updateSidebarWidth();
    // CSS will handle the resize automatically via calc()
}

function openChatSidebar() {
    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        updateSidebarWidth();
    }
}

toggleSidebarBtn.addEventListener('click', toggleSidebar);

// Initialize sidebar width
updateSidebarWidth();

// Chat functionality
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    
    // Add user message
    addChatMessage(message, 'user');
    chatInput.value = '';
    
    // Send to backend
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        
        const data = await response.json();
        
        // Add assistant message
        addChatMessage(data.response, 'assistant');
        
        // Handle actions
        if (data.action === 'open_app') {
            createWindow(data.data.app, data.data.title);
        } else if (data.action === 'close_all') {
            closeAllWindows();
        } else if (data.action === 'close_window') {
            // Close topmost window
            const topWindow = Array.from(document.querySelectorAll('.window'))
                .sort((a, b) => parseInt(b.style.zIndex) - parseInt(a.style.zIndex))[0];
            if (topWindow) {
                const id = topWindow.id;
                closeWindow(id);
            }
        } else if (data.action === 'minimize_window') {
            const topWindow = Array.from(document.querySelectorAll('.window'))
                .sort((a, b) => parseInt(b.style.zIndex) - parseInt(a.style.zIndex))[0];
            if (topWindow) {
                const id = topWindow.id;
                minimizeWindow(id);
            }
        } else if (data.action === 'maximize_window') {
            const topWindow = Array.from(document.querySelectorAll('.window'))
                .sort((a, b) => parseInt(b.style.zIndex) - parseInt(a.style.zIndex))[0];
            if (topWindow) {
                const id = topWindow.id;
                maximizeWindow(id);
            }
        }
    } catch (error) {
        addChatMessage('Error: Could not connect to OS assistant.', 'assistant');
        console.error(error);
    }
});

function addChatMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = text;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Menu Bar Clock
function updateClock() {
    const clock = document.getElementById('menu-bar-clock');
    if (!clock) return;
    const now = new Date();
    clock.textContent = now.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true 
    });
}

setInterval(updateClock, 1000);
updateClock();

// Initialize Dock
updateDock();

// Terminal cursor blink
setInterval(() => {
    const cursor = document.getElementById('terminal-cursor');
    if (cursor) {
        cursor.style.opacity = cursor.style.opacity === '0' ? '1' : '0';
    }
}, 500);

// Quick command buttons
document.querySelectorAll('.quick-cmd-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const cmd = btn.dataset.cmd;
        chatInput.value = cmd;
        chatForm.dispatchEvent(new Event('submit'));
    });
});

// Welcome message
setTimeout(() => {
    addChatMessage('Hello! I\'m your OS assistant. You can control your OS using natural language. Try commands like "open calculator", "close all", or type "help" for more options.', 'assistant');
}, 500);

// File Manager Functions
let currentFileManagerPath = '';

async function fileManagerRefresh() {
    const fileList = document.getElementById('file-list');
    const currentPath = document.getElementById('current-path');
    
    fileList.innerHTML = '<div class="text-center text-text-secondary">Loading...</div>';
    
    try {
        const response = await fetch(`/api/files/list?path=${encodeURIComponent(currentFileManagerPath)}`);
        const data = await response.json();
        
        currentPath.textContent = data.path || '/';
        fileList.innerHTML = '';
        
        if (data.items.length === 0) {
            fileList.innerHTML = '<div class="text-center text-text-secondary col-span-full">No files or folders</div>';
        } else {
            data.items.forEach(item => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.dataset.path = item.path;
                fileItem.dataset.type = item.type;
                
                const icon = item.type === 'folder' ? 'fa-folder' : 'fa-file';
                const iconColor = item.type === 'folder' ? 'text-blue-400' : 'text-slate-400';
                
                fileItem.innerHTML = `
                    <i class="fas ${icon} ${iconColor} text-4xl mb-2"></i>
                    <span class="text-xs text-text-secondary">${item.name}</span>
                `;
                
                fileItem.addEventListener('dblclick', () => {
                    if (item.type === 'folder') {
                        currentFileManagerPath = item.path;
                        fileManagerRefresh();
                    } else {
                        notepadOpenFile(item.path);
                    }
                });
                
                fileItem.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    // Delete option could go here
                });
                
                fileList.appendChild(fileItem);
            });
        }
    } catch (error) {
        fileList.innerHTML = '<div class="text-center text-red-500">Error loading files</div>';
        console.error(error);
    }
}

async function fileManagerNewFolder() {
    const name = prompt('Enter folder name:');
    if (!name) return;
    
    try {
        const path = currentFileManagerPath ? `${currentFileManagerPath}/${name}` : name;
        const response = await fetch('/api/files/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        
        if (response.ok) {
            fileManagerRefresh();
            refreshDesktop();
        } else {
            alert('Error creating folder');
        }
    } catch (error) {
        alert('Error creating folder');
        console.error(error);
    }
}

async function fileManagerNewFile() {
    const name = prompt('Enter file name:');
    if (!name) return;
    
    try {
        const path = currentFileManagerPath ? `${currentFileManagerPath}/${name}` : name;
        const response = await fetch('/api/files/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, content: '' })
        });
        
        if (response.ok) {
            fileManagerRefresh();
            refreshDesktop();
        } else {
            alert('Error creating file');
        }
    } catch (error) {
        alert('Error creating file');
        console.error(error);
    }
}

// Desktop Functions
async function refreshDesktop() {
    desktopFiles.innerHTML = '';
    
    try {
        const response = await fetch('/api/files/list?path=Desktop');
        const data = await response.json();
        
        if (data.items && data.items.length > 0) {
            const appIconsContainer = document.getElementById('desktop-app-icons');
            const appIconsWidth = appIconsContainer.offsetWidth || 120;
            
            let row = 0;
            let col = 0;
            const iconsPerRow = Math.floor((window.innerWidth - appIconsWidth - 100) / 100);
            
            data.items.forEach((item, index) => {
                const fileIcon = document.createElement('div');
                fileIcon.className = 'desktop-file-icon';
                fileIcon.dataset.path = item.path;
                fileIcon.dataset.type = item.type;
                fileIcon.dataset.name = item.name;
                
                // Position icons in a grid starting after app icons
                const left = appIconsWidth + 50 + (col % iconsPerRow) * 100;
                const top = 50 + Math.floor(col / iconsPerRow) * 100;
                
                fileIcon.style.left = `${left}px`;
                fileIcon.style.top = `${top}px`;
                
                const icon = item.type === 'folder' ? 'fa-folder' : 'fa-file';
                const iconColor = item.type === 'folder' ? 'text-blue-400' : 'text-slate-400';
                
                fileIcon.innerHTML = `
                    <div class="icon-wrapper">
                        <i class="fas ${icon} ${iconColor} text-5xl"></i>
                    </div>
                    <span class="icon-label">${item.name}</span>
                `;
                
                // Double-click to open
                fileIcon.addEventListener('dblclick', () => {
                    if (item.type === 'folder') {
                        // Open folder in file manager
                        createWindow('file_manager');
                        setTimeout(() => {
                            currentFileManagerPath = item.path;
                            fileManagerRefresh();
                        }, 200);
                    } else {
                        // Open file in notepad
                        createWindow('notepad');
                        setTimeout(() => {
                            notepadOpenFile(item.path);
                        }, 200);
                    }
                });
                
                // Right-click for context menu
                fileIcon.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    showFileContextMenu(e, item);
                });
                
                desktopFiles.appendChild(fileIcon);
                col++;
            });
        }
    } catch (error) {
        console.error('Error loading desktop files:', error);
    }
}

function showFileContextMenu(e, item) {
    // Hide desktop context menu
    contextMenu.classList.add('hidden');
    
    // Could add file-specific context menu here
    // For now, just use the desktop menu
}

async function desktopCreateFile() {
    contextMenu.classList.add('hidden');
    const name = prompt('Enter file name:');
    if (!name) return;
    
    try {
        const response = await fetch('/api/files/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: name, content: '' })
        });
        
        if (response.ok) {
            refreshDesktop();
        } else {
            alert('Error creating file');
        }
    } catch (error) {
        alert('Error creating file');
        console.error(error);
    }
}

async function desktopCreateFolder() {
    contextMenu.classList.add('hidden');
    const name = prompt('Enter folder name:');
    if (!name) return;
    
    try {
        const response = await fetch('/api/files/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: name })
        });
        
        if (response.ok) {
            refreshDesktop();
        } else {
            alert('Error creating folder');
        }
    } catch (error) {
        alert('Error creating folder');
        console.error(error);
    }
}

// Notepad Functions
let currentNotepadFile = '';

async function notepadOpen() {
    const filename = prompt('Enter file path (relative to root):');
    if (!filename) return;
    await notepadOpenFile(filename);
}

async function notepadOpenFile(path) {
    try {
        const response = await fetch(`/api/files/read?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        
        document.getElementById('notepad-editor').value = data.content;
        document.getElementById('notepad-filename').value = path;
        currentNotepadFile = path;
    } catch (error) {
        alert('Error opening file');
        console.error(error);
    }
}

async function notepadSave() {
    if (!currentNotepadFile) {
        notepadSaveAs();
        return;
    }
    
    try {
        const content = document.getElementById('notepad-editor').value;
        const response = await fetch('/api/files/write', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentNotepadFile, content })
        });
        
        if (response.ok) {
            alert('File saved!');
        } else {
            alert('Error saving file');
        }
    } catch (error) {
        alert('Error saving file');
        console.error(error);
    }
}

async function notepadSaveAs() {
    const filename = document.getElementById('notepad-filename').value || prompt('Enter file name:');
    if (!filename) return;
    
    try {
        const content = document.getElementById('notepad-editor').value;
        // Ensure file is created in Desktop if no path specified
        const filepath = filename.includes('/') ? filename : filename;
        const response = await fetch('/api/files/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filepath, content })
        });
        
        if (response.ok) {
            const data = await response.json();
            currentNotepadFile = data.path;
            document.getElementById('notepad-filename').value = data.path;
            refreshDesktop();
            alert('File saved!');
        } else {
            alert('Error saving file');
        }
    } catch (error) {
        alert('Error saving file');
        console.error(error);
    }
}

// Initialize file manager when window is created
document.addEventListener('DOMContentLoaded', () => {
    // File manager will refresh when window is opened
});

// Load file manager on window creation
const originalCreateWindow = createWindow;
function createWindowWithInit(appName, title, position) {
    const windowId = originalCreateWindow(appName, title, position);
    setTimeout(() => {
        if (appName === 'file_manager') {
            fileManagerRefresh();
        }
    }, 100);
    return windowId;
}

