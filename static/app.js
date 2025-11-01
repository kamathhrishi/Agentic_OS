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
    mailbox: {
        title: 'Mailbox',
        icon: 'fa-envelope',
        color: 'text-blue-400',
        content: `
            <div class="mailbox-container h-full flex flex-col">
                <div class="mailbox-toolbar mb-4 flex items-center gap-2">
                    <button class="toolbar-btn" onclick="mailboxRefresh()" title="Refresh">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                    <button class="toolbar-btn" onclick="mailboxCompose()" title="Compose">
                        <i class="fas fa-pen"></i> Compose
                    </button>
                    <div class="flex-1"></div>
                    <div class="text-sm text-text-secondary" id="mailbox-status">Loading...</div>
                </div>
                <div class="mailbox-tabs">
                    <button class="mailbox-tab active" onclick="switchMailboxTab('inbox')" data-tab="inbox">
                        📧 Inbox
                    </button>
                    <button class="mailbox-tab" onclick="switchMailboxTab('notifications')" data-tab="notifications">
                        🔔 Notifications<span class="tab-badge" id="notifications-badge" style="display: none;">0</span>
                    </button>
                </div>
                <div class="mailbox-content flex-1 overflow-auto" id="mailbox-content">
                    <div id="mailbox-inbox-view" class="mailbox-view">
                        <div class="text-center text-text-secondary">Loading inbox...</div>
                    </div>
                    <div id="mailbox-pagination" class="hidden mt-4 pb-4 flex items-center justify-center gap-2 border-t border-border pt-4">
                        <button id="mailbox-prev" class="toolbar-btn" onclick="mailboxPreviousPage()" disabled>
                            <i class="fas fa-chevron-left"></i> Previous
                        </button>
                        <span id="mailbox-page-info" class="text-sm text-text-secondary px-4"></span>
                        <button id="mailbox-next" class="toolbar-btn" onclick="mailboxNextPage()" disabled>
                            Next <i class="fas fa-chevron-right"></i>
                        </button>
                    </div>
                    <div id="mailbox-notifications-view" class="mailbox-view hidden">
                        <div class="text-center text-text-secondary mb-4">All email notifications</div>
                        <div id="notifications-list"></div>
                    </div>
                    <div id="mailbox-compose-view" class="mailbox-view hidden">
                        <div class="mailbox-compose-form space-y-4">
                            <div>
                                <label class="block text-sm font-medium mb-2 text-text-secondary">Instructions for AI</label>
                                <textarea id="compose-instructions"
                                    class="w-full bg-input text-black px-4 py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-sm placeholder-text-secondary min-h-[120px]"
                                    placeholder="Describe the email you want to send. For example: 'Email Alex Johnson at zoebex01@gmail.com about the launch. Mention the roadmap deck and ask for feedback by Friday.'"></textarea>
                            </div>
                            <div class="flex gap-2">
                                <button onclick="mailboxSendEmail()" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition text-sm font-medium">
                                    <i class="fas fa-paper-plane mr-2"></i>Send Email
                                </button>
                                <button onclick="mailboxBackToInbox()" class="px-4 py-2 bg-input border border-border rounded-lg text-text-secondary hover:text-white transition text-sm">
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    browser: {
        title: 'Browser',
        icon: 'fa-globe',
        color: 'text-green-400',
        content: `
            <div class="browser-container h-full flex flex-col">
                <div class="browser-toolbar mb-2 flex items-center gap-2">
                    <button class="toolbar-btn" onclick="browserBack()" title="Back" id="browser-back">
                        <i class="fas fa-arrow-left"></i>
                    </button>
                    <button class="toolbar-btn" onclick="browserForward()" title="Forward" id="browser-forward">
                        <i class="fas fa-arrow-right"></i>
                    </button>
                    <button class="toolbar-btn" onclick="browserReload()" title="Reload">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                    <div class="flex-1"></div>
                    <input type="text" id="browser-url" 
                        class="flex-1 bg-input text-black px-4 py-2 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-sm"
                        placeholder="Enter URL or search..."
                        onkeypress="if(event.key==='Enter') browserNavigate()">
                    <button class="toolbar-btn" onclick="browserNavigate()" title="Go">
                        <i class="fas fa-arrow-right"></i> Go
                    </button>
                </div>
                <div class="browser-content flex-1 overflow-auto relative bg-white" id="browser-content">
                    <div id="browser-placeholder" class="absolute inset-0 flex items-center justify-center">
                        <div class="text-center text-text-secondary">
                            <i class="fas fa-globe text-6xl mb-4 opacity-50"></i>
                            <p>Enter a URL to start browsing</p>
                        </div>
                    </div>
                    <iframe id="browser-iframe" 
                        class="w-full h-full border-0" 
                        style="display: none;"
                        sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
                        allow="camera; microphone; geolocation">
                    </iframe>
                </div>
            </div>
        `
    },
    slideshow: {
        title: 'Slideshow',
        icon: 'fa-images',
        color: 'text-pink-400',
        content: `
            <div class="slideshow-container h-full flex flex-col">
                <div class="slideshow-toolbar mb-2 flex items-center gap-2">
                    <button class="toolbar-btn" onclick="slideshowCreate()" title="Create New Slideshow">
                        <i class="fas fa-plus"></i> Create
                    </button>
                    <button class="toolbar-btn" onclick="slideshowLoad()" title="Load Slideshow">
                        <i class="fas fa-folder-open"></i> Load
                    </button>
                    <button class="toolbar-btn" onclick="slideshowSave()" title="Save Slideshow">
                        <i class="fas fa-save"></i> Save
                    </button>
                    <div class="flex-1"></div>
                    <div class="text-sm text-text-secondary" id="slideshow-status">Ready</div>
                </div>
                <div class="slideshow-content flex-1 flex flex-col">
                    <div id="slideshow-creator-view" class="slideshow-view h-full flex flex-col">
                        <div class="mb-4">
                            <label class="block text-sm font-medium mb-2 text-text-secondary">Generate Slideshow</label>
                            <textarea id="slideshow-prompt" 
                                class="w-full bg-input text-black px-4 py-3 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-pink-500/50 text-sm placeholder-text-secondary min-h-[100px]"
                                placeholder="Describe the slideshow you want to create. For example: 'Create a 5-slide presentation about Q4 financial results with charts and key metrics'"></textarea>
                        </div>
                        <button onclick="slideshowGenerate()" class="bg-pink-600 hover:bg-pink-500 text-white px-4 py-2 rounded-lg transition text-sm font-medium">
                            <i class="fas fa-magic mr-2"></i>Generate Slideshow
                        </button>
                        <div id="slideshow-preview" class="mt-4 flex-1 overflow-auto bg-white rounded-lg border border-border" style="display: none;">
                            <iframe id="slideshow-iframe" class="w-full h-full border-0" style="min-height: 400px;"></iframe>
                        </div>
                    </div>
                    <div id="slideshow-player-view" class="slideshow-view hidden h-full">
                        <div class="relative h-full">
                            <button class="absolute top-4 left-4 z-10 bg-black/50 hover:bg-black/70 text-white px-4 py-2 rounded-lg" onclick="slideshowBackToCreator()">
                                <i class="fas fa-arrow-left mr-2"></i>Back
                            </button>
                            <button class="absolute top-4 right-16 z-10 bg-black/50 hover:bg-black/70 text-white px-4 py-2 rounded-lg" onclick="slideshowPrev()">
                                <i class="fas fa-chevron-left"></i>
                            </button>
                            <button class="absolute top-4 right-4 z-10 bg-black/50 hover:bg-black/70 text-white px-4 py-2 rounded-lg" onclick="slideshowNext()">
                                <i class="fas fa-chevron-right"></i>
                            </button>
                            <iframe id="slideshow-player-iframe" class="w-full h-full border-0"></iframe>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    sync: {
        title: 'Sync',
        icon: 'fa-sync',
        color: 'text-cyan-400',
        content: `
            <div class="sync-container h-full flex flex-col">
                <div class="sync-header mb-4 pb-4 border-b border-border">
                    <h2 class="text-xl font-semibold text-white mb-2">Data Sync</h2>
                    <p class="text-sm text-text-secondary">Connect your accounts to sync data across platforms</p>
                </div>

                <div class="sync-content flex-1 overflow-auto">
                    <div id="sync-loading" class="text-center text-text-secondary py-8">
                        <i class="fas fa-spinner fa-spin text-3xl mb-3"></i>
                        <p>Loading integrations...</p>
                    </div>

                    <div id="sync-integrations" class="hidden">
                        <div class="mb-6">
                            <h3 class="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">Available Integrations</h3>
                            <div id="integrations-grid" class="grid grid-cols-2 gap-3"></div>
                        </div>

                        <div class="mt-6 pt-6 border-t border-border">
                            <h3 class="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3">Connected</h3>
                            <div id="connected-integrations" class="space-y-2">
                                <p class="text-sm text-text-secondary">No integrations connected yet</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    },
    scheduled_processes: {
        title: 'Scheduled Processes',
        icon: 'fa-tasks',
        color: 'text-purple-400',
        content: `
            <div class="scheduled-processes-container h-full flex flex-col">
                <div class="scheduled-processes-header mb-4 pb-4 border-b border-border">
                    <h2 class="text-xl font-semibold text-white mb-2">⚙️ Scheduled Processes</h2>
                    <p class="text-sm text-text-secondary">Commands from COMMAND: JARVIS emails</p>
                </div>
                <div class="scheduled-processes-tabs mb-4 flex gap-2 border-b border-border">
                    <button class="scheduled-processes-tab active" data-tab="active" onclick="switchScheduledProcessesTab('active')">
                        Active
                    </button>
                    <button class="scheduled-processes-tab" data-tab="completed" onclick="switchScheduledProcessesTab('completed')">
                        Completed History
                    </button>
                </div>
                <div class="scheduled-processes-toolbar mb-4 flex items-center gap-2">
                    <button class="toolbar-btn" onclick="refreshScheduledProcesses()" title="Refresh">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                    <div class="flex-1"></div>
                    <div class="text-sm text-text-secondary" id="scheduled-processes-status">Loading...</div>
                </div>
                <div class="scheduled-processes-content flex-1 overflow-auto" id="scheduled-processes-content">
                    <div id="scheduled-processes-list" class="space-y-4">
                        <div class="text-center text-text-secondary py-8">
                            <i class="fas fa-spinner fa-spin text-3xl mb-3"></i>
                            <p>Loading scheduled processes...</p>
                        </div>
                    </div>
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
    
    // Initialize file manager or mailbox if needed
    if (appName === 'file_manager') {
        setTimeout(() => {
            if (typeof fileManagerRefresh === 'function') {
                fileManagerRefresh();
            }
        }, 100);
    } else if (appName === 'mailbox') {
        setTimeout(() => {
            if (typeof mailboxRefresh === 'function') {
                mailboxRefresh();
            }
        }, 100);
    } else if (appName === 'browser') {
        // Generate unique session ID for this browser window
        const sessionId = `browser_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        browserWindowSessions.set(windowId, sessionId);

        // Store session ID in window element for easy access
        const windowElement = windows.get(windowId)?.element;
        if (windowElement) {
            windowElement.dataset.browserSession = sessionId;
        }

        setTimeout(() => {
            // Browser will be ready when user navigates
        }, 100);
    } else if (appName === 'sync') {
        // Initialize sync app
        setTimeout(() => {
            if (typeof syncLoadIntegrations === 'function') {
                syncLoadIntegrations();
            }
        }, 100);
    } else if (appName === 'scheduled_processes') {
        // Initialize scheduled processes app
        setTimeout(async () => {
            await refreshScheduledProcesses();
            // Also load archived processes initially
            await loadArchivedProcesses();
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
    
    // Clean up browser session if it's a browser window
    if (win.app === 'browser') {
        browserWindowSessions.delete(windowId);
    }
    
    win.element.remove();
    windows.delete(windowId);
    updateDock();
}

function closeAllWindows() {
    windows.forEach((win, id) => closeWindow(id));
}

// Dock removed - using desktop icons instead
function updateDock() {
    // Dock functionality removed - desktop icons are used instead
}

// Mouse events for dragging
document.addEventListener('mousemove', (e) => {
    if (draggedWindow && !draggedWindow.classList.contains('maximized')) {
        const sidebarWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')) || 380;
        const menuBarHeight = 28;
        const maxLeft = window.innerWidth - sidebarWidth - draggedWindow.offsetWidth;
        const maxTop = window.innerHeight - draggedWindow.offsetHeight;
        const newLeft = Math.max(0, Math.min(e.clientX - dragOffset.x, maxLeft));
        const newTop = Math.max(menuBarHeight, Math.min(e.clientY - dragOffset.y, maxTop));
        draggedWindow.style.left = `${newLeft}px`;
        draggedWindow.style.top = `${newTop}px`;
    }
});

document.addEventListener('mouseup', () => {
    draggedWindow = null;
});

// Initialize desktop icons distributed across the desktop
function initDesktopIcons() {
    const desktop = document.getElementById('desktop');
    const desktopFiles = document.getElementById('desktop-files');
    
    if (!desktop || !desktopFiles) {
        console.warn('Desktop or desktop-files container not found');
        return;
    }
    
    // Remove existing desktop app icons (but keep file icons)
    const existingIcons = desktopFiles.querySelectorAll('.desktop-icon[data-app]');
    existingIcons.forEach(icon => icon.remove());
    
    const appsToShow = ['file_manager', 'terminal', 'notepad', 'mailbox', 'browser', 'slideshow', 'sync', 'scheduled_processes'];
    
    // Calculate positions - distribute icons across desktop in a grid
    const iconSize = 90;
    const spacing = 100;
    const startX = 50;
    const startY = 50;
    const iconsPerRow = Math.floor((window.innerWidth - startX * 2) / spacing);
    
    appsToShow.forEach((appName, index) => {
        const app = appTemplates[appName];
        if (!app) return;
        
        const row = Math.floor(index / iconsPerRow);
        const col = index % iconsPerRow;
        const left = startX + col * spacing;
        const top = startY + row * spacing;
        
        const icon = document.createElement('div');
        icon.className = 'desktop-icon';
        icon.dataset.app = appName;
        icon.style.position = 'absolute';
        icon.style.left = `${left}px`;
        icon.style.top = `${top}px`;
        icon.style.width = `${iconSize}px`;
        icon.style.cursor = 'pointer';
        
        // Add notification badge for mailbox
        const badgeHtml = appName === 'mailbox' ? '<div class="desktop-icon-badge" id="mailbox-desktop-badge" style="display: none;">0</div>' : '';
        
        icon.innerHTML = `
            <div class="icon-wrapper">
                <i class="fas ${app.icon} ${app.color || 'text-slate-400'} text-5xl"></i>
                ${badgeHtml}
            </div>
            <span class="icon-label">${app.title}</span>
        `;
        
        // Double-click to open
        icon.addEventListener('dblclick', () => {
            createWindow(appName);
        });
        
        desktopFiles.appendChild(icon);
    });
}

// Initialize desktop icons when DOM is ready
function ensureDesktopIcons() {
    const desktop = document.getElementById('desktop');
    const desktopFiles = document.getElementById('desktop-files');
    
    if (!desktop || !desktopFiles) {
        // Retry after a short delay if DOM not ready
        setTimeout(ensureDesktopIcons, 100);
        return;
    }
    
    initDesktopIcons();
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureDesktopIcons);
} else {
    // DOM already ready
    ensureDesktopIcons();
}

// Re-initialize on window resize to reposition icons
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        ensureDesktopIcons();
        refreshDesktop(); // Also refresh desktop files to reposition them
    }, 250);
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
        
        // Check if response is streaming (text/event-stream)
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/event-stream')) {
            // Handle streaming response for compilation requests
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let assistantMessageId = null;
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const update = JSON.parse(line.slice(6));
                            console.log('Received update:', update); // Debug log
                            
                            if (update.type === 'progress') {
                                if (!assistantMessageId) {
                                    // Create assistant message for progress updates
                                    assistantMessageId = addChatMessage(update.message, 'assistant', true);
                                    console.log('Created message with ID:', assistantMessageId);
                                } else {
                                    // Update existing message
                                    updateChatMessage(assistantMessageId, update.message);
                                    console.log('Updated message:', update.message);
                                }
                            } else if (update.type === 'complete') {
                                if (assistantMessageId) {
                                    updateChatMessage(assistantMessageId, update.message);
                                } else {
                                    addChatMessage(update.message, 'assistant');
                                }
                                // Refresh desktop to show new file
                                refreshDesktop();
                            } else if (update.type === 'error') {
                                if (assistantMessageId) {
                                    updateChatMessage(assistantMessageId, '❌ Error: ' + update.message);
                                } else {
                                    addChatMessage('❌ Error: ' + update.message, 'assistant');
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e, 'Line:', line);
                        }
                    } else if (line.trim() === '') {
                        // Empty line - separator between events
                        continue;
                    } else {
                        console.log('Non-data line:', line);
                    }
                }
            }
            return;
        }
        
        // Regular JSON response
        const data = await response.json();
        
        // Add assistant message
        addChatMessage(data.response, 'assistant');
        
        // Handle actions
        if (data.action === 'open_app') {
            // Check if browser app with multiple URLs before creating first window
            if (data.data.app === 'browser' && data.data.navigate_to) {
                const urls = data.data.multiple_urls || (Array.isArray(data.data.navigate_to) ? data.data.navigate_to : [data.data.navigate_to]);
                
                if (Array.isArray(urls) && urls.length > 1) {
                    // Multiple URLs - open multiple browser windows (don't create the first one yet)
                    const searchTerms = data.data.search_terms || [];
                    const autoSearch = data.data.auto_search || false;
                    
                    // Use navigate-multiple endpoint to get all sessions with agent goals
                    const agentGoals = data.data.agent_goals || searchTerms;
                    
                    fetch('/api/browser/navigate-multiple', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            urls: urls,
                            agent_goals: agentGoals
                        })
                    }).then(async (response) => {
                        const navData = await response.json();
                        if (navData.success && navData.results) {
                            navData.results.forEach((result, index) => {
                                setTimeout(() => {
                                    // Extract better domain name for title
                                    let domain = result.url.replace(/^https?:\/\//, '').split('/')[0];
                                    if (domain.includes('.')) {
                                        const parts = domain.split('.');
                                        domain = parts.length > 2 ? parts.slice(-2).join('.') : domain;
                                    }
                                    
                                    // Create a new browser window for each URL
                                    const newWindowId = createWindow('browser', `Browser - ${domain}`);
                                    const newWindowElement = windows.get(newWindowId)?.element;
                                    
                                    if (newWindowElement) {
                                        // Set the session ID from the result
                                        newWindowElement.dataset.browserSession = result.session_id;
                                        browserWindowSessions.set(newWindowId, result.session_id);
                                        
                                        const urlInput = newWindowElement.querySelector('#browser-url');
                                        const iframe = newWindowElement.querySelector('#browser-iframe');
                                        const placeholder = newWindowElement.querySelector('#browser-placeholder');
                                        
                                        if (urlInput && result.proxy_url) {
                                            urlInput.value = result.url;
                                            
                                            // Load the proxied page
                                            if (iframe) {
                                                iframe.src = result.proxy_url;
                                                iframe.style.display = 'block';
                                                iframe.onload = () => {
                                                    if (placeholder) placeholder.style.display = 'none';
                                                };
                                            }
                                            
                                            // Add agent status panel if agent is active
                                            if (result.agent_goal) {
                                                addAgentStatusPanel(newWindowElement, result.session_id, result.agent_goal);
                                                // Start polling agent status
                                                pollAgentStatus(result.session_id, newWindowElement);
                                            }
                                        }
                                    }
                                }, index * 300 + 500); // Stagger window creation
                            });
                        }
                    }).catch(error => {
                        console.error('Error navigating multiple browsers:', error);
                    });
                } else {
                    // Single URL - create one window
                    const windowId = createWindow(data.data.app, data.data.title);
                    const singleUrl = Array.isArray(urls) ? urls[0] : urls;
                    const agentGoal = data.data.agent_goal; // Check if agent goal was provided
                    
                    setTimeout(() => {
                        // Find the browser window we just created
                        const windowElement = windows.get(windowId)?.element;
                        if (!windowElement) return;
                        
                        const sessionId = windowElement.dataset.browserSession || getBrowserSession();
                        const urlInput = windowElement.querySelector('#browser-url');
                        if (urlInput) {
                            urlInput.value = singleUrl;
                            // Navigate with the correct session ID and pass agent goal
                            browserNavigateWithSession(sessionId, singleUrl, windowElement, agentGoal);
                        }
                    }, 800);
                }
            } else if (data.action === 'open_slideshow') {
                // Open slideshow with pre-generated content
                const windowId = createWindow('slideshow', data.data.title || 'Slideshow');
                setTimeout(() => {
                    const windowElement = windows.get(windowId)?.element;
                    if (windowElement && data.data.html) {
                        // Set the slideshow HTML directly
                        currentSlideshowHtml = data.data.html;
                        totalSlides = data.data.slide_count || 1;
                        currentSlideIndex = 0;
                        
                        // Switch directly to player view
                        const creatorView = windowElement.querySelector('#slideshow-creator-view');
                        const playerView = windowElement.querySelector('#slideshow-player-view');
                        const playerIframe = windowElement.querySelector('#slideshow-player-iframe');
                        const status = windowElement.querySelector('#slideshow-status');
                        
                        if (creatorView) creatorView.classList.add('hidden');
                        if (playerView) {
                            playerView.classList.remove('hidden');
                            if (playerIframe) {
                                playerIframe.srcdoc = data.data.html;
                                playerIframe.onload = () => {
                                    showSlide(0);
                                };
                            }
                        }
                        if (status) status.textContent = `Loaded ${totalSlides} slides`;
                    }
                }, 300);
            } else if (data.data.app === 'slideshow' && data.data.generate_prompt) {
                // Slideshow app with auto-generation prompt
                const windowId = createWindow(data.data.app, data.data.title);
                setTimeout(() => {
                    const windowElement = windows.get(windowId)?.element;
                    if (windowElement) {
                        const promptTextarea = windowElement.querySelector('#slideshow-prompt');
                        if (promptTextarea) {
                            promptTextarea.value = data.data.generate_prompt;
                            // Optionally auto-generate if requested
                            if (data.data.auto_generate) {
                                setTimeout(() => {
                                    slideshowGenerate();
                                }, 500);
                            }
                        }
                    }
                }, 300);
            } else {
                // Not a browser app or no navigation needed
                createWindow(data.data.app, data.data.title);
            }
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
        } else if (data.action === 'create_file') {
            // Refresh desktop to show new file
            refreshDesktop();
            // If file manager is open, refresh it too
            const fileManagerWindow = Array.from(document.querySelectorAll('.window'))
                .find(w => w.querySelector('[data-app="file_manager"]') || w.innerHTML.includes('file-manager'));
            if (fileManagerWindow) {
                setTimeout(() => {
                    if (typeof fileManagerRefresh === 'function') {
                        fileManagerRefresh();
                    }
                }, 100);
            }
        } else if (data.action === 'find_file') {
            // Results are already in the response message
            // Could optionally highlight files in UI
            if (data.data && data.data.files && data.data.files.length > 0) {
                refreshDesktop();
            }
        } else if (data.action === 'delete_file') {
            // Refresh desktop to remove deleted file
            refreshDesktop();
            // If file manager is open, refresh it too
            const fileManagerWindow = Array.from(document.querySelectorAll('.window'))
                .find(w => w.querySelector('[data-app="file_manager"]') || w.innerHTML.includes('file-manager'));
            if (fileManagerWindow) {
                setTimeout(() => {
                    if (typeof fileManagerRefresh === 'function') {
                        fileManagerRefresh();
                    }
                }, 100);
            }
        } else if (data.action === 'list_files') {
            // Results are already in the response message
            // Could optionally update file manager if open
        } else if (data.action === 'compose_email') {
            // Email sent successfully - refresh mailbox if open
            const mailboxWindow = Array.from(document.querySelectorAll('.window'))
                .find(w => w.innerHTML.includes('mailbox-container'));
            if (mailboxWindow) {
                setTimeout(() => {
                    if (typeof mailboxRefresh === 'function') {
                        mailboxRefresh();
                    }
                }, 500);
            }
        } else if (data.action === 'navigate_browser') {
            // Open browser and navigate - handled via open_app with navigate_to
            // But if browser already exists, we can navigate in the existing one
            const existingBrowserWindows = Array.from(document.querySelectorAll('.window'))
                .filter(w => w.querySelector('#browser-url'));
            
            if (existingBrowserWindows.length > 0) {
                // Use the topmost browser window
                const topBrowser = existingBrowserWindows
                    .sort((a, b) => parseInt(b.style.zIndex || 0) - parseInt(a.style.zIndex || 0))[0];
                const sessionId = topBrowser.dataset.browserSession || getBrowserSession();
                const urlInput = topBrowser.querySelector('#browser-url');
                if (urlInput && data.data && data.data.url) {
                    urlInput.value = data.data.url;
                    browserNavigateWithSession(sessionId, data.data.url, topBrowser);
                }
            }
        } else if (data.action === 'control_browser') {
            // Browser control action completed - refresh the browser iframe
            if (data.data && data.data.proxy_url) {
                const existingBrowserWindows = Array.from(document.querySelectorAll('.window'))
                    .filter(w => w.querySelector('#browser-url'));
                
                if (existingBrowserWindows.length > 0) {
                    // Find the browser window (use the one that matches the session if possible)
                    const topBrowser = existingBrowserWindows
                        .sort((a, b) => parseInt(b.style.zIndex || 0) - parseInt(a.style.zIndex || 0))[0];
                    
                    const iframe = topBrowser.querySelector('#browser-iframe');
                    const urlInput = topBrowser.querySelector('#browser-url');
                    const placeholder = topBrowser.querySelector('#browser-placeholder');
                    
                    if (iframe && data.data.proxy_url) {
                        iframe.src = data.data.proxy_url;
                        iframe.style.display = 'block';
                        if (placeholder) placeholder.style.display = 'none';
                    }
                    
                    if (urlInput && data.data.url) {
                        urlInput.value = data.data.url;
                    }
                    
                    // Update window title
                    if (data.data.title) {
                        const titleSpan = topBrowser.querySelector('.window-title span');
                        if (titleSpan) {
                            titleSpan.textContent = data.data.title.length > 40 ? data.data.title.substring(0, 40) + '...' : data.data.title;
                        }
                    }
                }
            }
        }
    } catch (error) {
        addChatMessage('Error: Could not connect to OS assistant.', 'assistant');
        console.error(error);
    }
});

function addChatMessage(text, type, returnId = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    messageDiv.id = messageId;
    
    // Handle multi-line messages and preserve line breaks
    // Escape HTML to prevent XSS
    const escapeHtml = (unsafe) => {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };
    const formattedText = text.split('\n').map(line => {
        return escapeHtml(line) || ' '; // Preserve empty lines
    }).join('<br>');
    messageDiv.innerHTML = formattedText;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return returnId ? messageId : undefined;
}

function updateChatMessage(messageId, newText) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;
    
    const escapeHtml = (unsafe) => {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };
    const formattedText = newText.split('\n').map(line => {
        return escapeHtml(line) || ' '; // Preserve empty lines
    }).join('<br>');
    messageDiv.innerHTML = formattedText;
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
    addChatMessage('Hello! I\'m your OS assistant powered by AI. You can control your OS using natural language. Try commands like:\n- "Create a file called notes.txt with some content"\n- "Find files with .txt extension"\n- "Delete the file notes.txt"\n- "Open mailbox" or "Open terminal"\n- "Open google.com" or "Visit wikipedia.org"\n- "Open google.com and also open youtube.com" (multiple sites!)\n- "Click the search button" (when browser is open)\n- "Type hello in the search box" (when browser is open)\n- "Scroll down on the page"\n- "List all files"\n- "Email Alex Johnson at zoebex01@gmail.com about the launch"\n\nI can create files, find files, send emails, browse the web, control browsers using AI vision, and open apps - just ask me!', 'assistant');
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
                    } else if (item.name.endsWith('.html')) {
                        // Open HTML files in browser
                        openHtmlFile(item.path);
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
    // Only remove file icons, preserve app icons
    const existingFileIcons = desktopFiles.querySelectorAll('.desktop-file-icon');
    existingFileIcons.forEach(icon => icon.remove());
    
    // Ensure app icons are present
    ensureDesktopIcons();
    
    // Wait a tick to ensure app icons are created
    await new Promise(resolve => setTimeout(resolve, 0));
    
    try {
        const response = await fetch('/api/files/list?path=Desktop');
        const data = await response.json();
        
        if (data.items && data.items.length > 0) {
            // Calculate position based on app icons
            const appIcons = desktopFiles.querySelectorAll('.desktop-icon[data-app]');
            const iconSize = 90;
            const spacing = 100;
            const startX = 50;
            const startY = 50;
            
            // Find the rightmost app icon position
            let maxAppIconRight = startX;
            appIcons.forEach(icon => {
                const rect = icon.getBoundingClientRect();
                const left = parseInt(icon.style.left) || 0;
                maxAppIconRight = Math.max(maxAppIconRight, left + iconSize);
            });
            
            // Calculate how many app icons per row to determine file icon starting position
            const iconsPerRow = Math.floor((window.innerWidth - startX * 2) / spacing);
            const appIconRows = Math.ceil(appIcons.length / iconsPerRow);
            const fileStartX = startX;
            const fileStartY = startY + (appIconRows * spacing);
            
            // Position file icons below app icons
            data.items.forEach((item, index) => {
                const fileIcon = document.createElement('div');
                fileIcon.className = 'desktop-file-icon';
                fileIcon.dataset.path = item.path;
                fileIcon.dataset.type = item.type;
                fileIcon.dataset.name = item.name;
                
                const row = Math.floor(index / iconsPerRow);
                const col = index % iconsPerRow;
                const left = fileStartX + col * spacing;
                const top = fileStartY + row * spacing;
                
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
                    } else if (item.name.endsWith('.html')) {
                        // Open HTML files (presentations) in browser
                        openHtmlFile(item.path);
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

async function openHtmlFile(path) {
    try {
        // Open browser window
        const windowId = createWindow('browser', path.split('/').pop() || 'Presentation');
        
        setTimeout(() => {
            const windowElement = windows.get(windowId)?.element;
            if (!windowElement) return;
            
            const sessionId = windowElement.dataset.browserSession || getBrowserSession();
            const iframe = windowElement.querySelector('#browser-iframe');
            const placeholder = windowElement.querySelector('#browser-placeholder');
            const urlInput = windowElement.querySelector('#browser-url');
            
            // Load the HTML file content
            fetch(`/api/files/read?path=${encodeURIComponent(path)}`)
                .then(response => response.json())
                .then(data => {
                    if (iframe && data.content) {
                        iframe.srcdoc = data.content;
                        iframe.style.display = 'block';
                    }
                    if (placeholder) placeholder.style.display = 'none';
                    if (urlInput) urlInput.value = path;
                })
                .catch(error => {
                    console.error('Error loading HTML file:', error);
                    alert('Error opening presentation');
                });
        }, 300);
    } catch (error) {
        alert('Error opening presentation');
        console.error(error);
    }
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
// Email notification tracking
let allNotifications = [];
let shownNotifications = new Set();

// Tab switching function
function switchMailboxTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.mailbox-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.mailbox-tab[data-tab="${tabName}"]`)?.classList.add('active');

    // Update view visibility
    document.getElementById('mailbox-inbox-view')?.classList.toggle('hidden', tabName !== 'inbox');
    document.getElementById('mailbox-pagination')?.classList.toggle('hidden', tabName !== 'inbox');
    document.getElementById('mailbox-notifications-view')?.classList.toggle('hidden', tabName !== 'notifications');
    document.getElementById('mailbox-compose-view')?.classList.add('hidden');

    // Refresh the content based on tab
    if (tabName === 'notifications') {
        updateNotificationsView();
    }
}

// Update the mailbox notification badge
function updateMailboxBadge() {
    const unreadCount = allNotifications.filter(n => !n.read && n.type === 'email').length;
    
    // Update desktop icon badge - try to find it, or create it if missing
    let desktopBadge = document.getElementById('mailbox-desktop-badge');
    
    // If badge doesn't exist, try to find the mailbox icon and create badge
    if (!desktopBadge) {
        const mailboxIcon = document.querySelector('.desktop-icon[data-app="mailbox"] .icon-wrapper');
        if (mailboxIcon) {
            desktopBadge = document.createElement('div');
            desktopBadge.id = 'mailbox-desktop-badge';
            desktopBadge.className = 'desktop-icon-badge';
            desktopBadge.style.display = 'none';
            mailboxIcon.appendChild(desktopBadge);
        }
    }
    
    if (desktopBadge) {
        if (unreadCount > 0) {
            desktopBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
            desktopBadge.style.display = 'flex';
        } else {
            desktopBadge.style.display = 'none';
        }
    }

    // Note: Scheduled processes badge is now in the separate desktop app

    const notificationsBadge = document.getElementById('notifications-badge');
    if (notificationsBadge) {
        const totalUnread = allNotifications.filter(n => !n.read).length;
        if (totalUnread > 0) {
            notificationsBadge.textContent = totalUnread;
            notificationsBadge.style.display = 'inline-block';
        } else {
            notificationsBadge.style.display = 'none';
        }
    }
}

// Current tab for scheduled processes view
let currentScheduledProcessesTab = 'active';
let archivedProcesses = [];

// Tab switching for scheduled processes
function switchScheduledProcessesTab(tabName) {
    currentScheduledProcessesTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.scheduled-processes-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    
    // Refresh the view
    updateScheduledProcessesView();
}

// Update scheduled processes view (for the desktop app)
function updateScheduledProcessesView() {
    const tasksList = document.getElementById('scheduled-processes-list');
    const statusEl = document.getElementById('scheduled-processes-status');
    
    if (!tasksList) return;

    if (currentScheduledProcessesTab === 'active') {
        // Show active processes
        const commandNotifications = allNotifications.filter(n => n.type === 'command');
        
        if (statusEl) {
            const activeCount = commandNotifications.filter(n => n.status === 'scheduled' || n.status === 'processing').length;
            statusEl.textContent = `${commandNotifications.length} process${commandNotifications.length !== 1 ? 'es' : ''} (${activeCount} active)`;
        }

        if (commandNotifications.length === 0) {
            tasksList.innerHTML = '<div class="text-center text-text-secondary py-12"><p>No active processes</p><p class="text-xs mt-2">Emails starting with "COMMAND: JARVIS" will appear here</p></div>';
            return;
        }

        tasksList.innerHTML = commandNotifications.map(notification => {
            const statusEmoji = {
                'scheduled': '📋',
                'processing': '⚙️',
                'completed': '✅',
                'failed': '❌'
            };
            const emoji = statusEmoji[notification.status] || '🤖';

            return `
                <div class="task-item">
                    <div class="flex items-center justify-between mb-2">
                        <div class="font-semibold text-sm">${emoji} ${notification.subject}</div>
                        <span class="task-status ${notification.status}">${notification.status}</span>
                    </div>
                    <div class="text-xs text-text-secondary mb-1">From: ${notification.from}</div>
                    ${notification.command ? `<div class="text-xs text-text-secondary mb-2">Command: ${notification.command.substring(0, 80)}${notification.command.length > 80 ? '...' : ''}</div>` : ''}
                    ${notification.progress ? `<div class="text-xs mt-2 p-2 bg-blue-50 rounded border border-blue-200">📊 ${notification.progress}</div>` : ''}
                    ${notification.status === 'completed' && notification.response ? `<div class="text-xs mt-2 p-2 bg-green-50 rounded border border-green-200">✅ <strong>Result:</strong><br/>${notification.response.substring(0, 500)}${notification.response.length > 500 ? '...' : ''}</div>` : ''}
                    ${notification.status === 'failed' && notification.error ? `<div class="text-xs mt-2 p-2 bg-red-50 rounded border border-red-200">❌ <strong>Error:</strong> ${notification.error}</div>` : ''}
                    <div class="flex items-center justify-between mt-2">
                        <div class="text-xs text-text-secondary">${new Date(notification.timestamp).toLocaleString()}</div>
                        ${notification.status === 'completed' || notification.status === 'failed' ? `<button class="text-xs text-blue-500 hover:text-blue-700" onclick="archiveProcess('${notification.id}')" title="Archive">📦 Archive</button>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } else {
        // Show archived processes
        if (statusEl) {
            statusEl.textContent = `${archivedProcesses.length} archived process${archivedProcesses.length !== 1 ? 'es' : ''}`;
        }

        if (archivedProcesses.length === 0) {
            tasksList.innerHTML = '<div class="text-center text-text-secondary py-12"><p>No archived processes</p><p class="text-xs mt-2">Completed or failed processes will appear here after being archived</p></div>';
            return;
        }

        tasksList.innerHTML = archivedProcesses.map(process => {
            const statusEmoji = {
                'scheduled': '📋',
                'processing': '⚙️',
                'completed': '✅',
                'failed': '❌'
            };
            const emoji = statusEmoji[process.status] || '🤖';
            const archivedDate = process.archived_at || process.completed_at || process.failed_at || process.timestamp;

            return `
                <div class="task-item opacity-75">
                    <div class="flex items-center justify-between mb-2">
                        <div class="font-semibold text-sm">${emoji} ${process.subject}</div>
                        <span class="task-status ${process.status}">${process.status}</span>
                    </div>
                    <div class="text-xs text-text-secondary mb-1">From: ${process.from}</div>
                    ${process.command ? `<div class="text-xs text-text-secondary mb-2">Command: ${process.command.substring(0, 80)}${process.command.length > 80 ? '...' : ''}</div>` : ''}
                    ${process.status === 'completed' && process.response ? `<div class="text-xs mt-2 p-2 bg-green-50 rounded border border-green-200">✅ <strong>Result:</strong><br/>${process.response.substring(0, 500)}${process.response.length > 500 ? '...' : ''}</div>` : ''}
                    ${process.status === 'failed' && process.error ? `<div class="text-xs mt-2 p-2 bg-red-50 rounded border border-red-200">❌ <strong>Error:</strong> ${process.error}</div>` : ''}
                    <div class="text-xs text-text-secondary mt-2">
                        Archived: ${new Date(archivedDate).toLocaleString()}
                    </div>
                </div>
            `;
        }).join('');
    }
}

// Archive a process (move from active to archived)
async function archiveProcess(notificationId) {
    try {
        const response = await fetch(`/api/email/notifications/${notificationId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            // Remove from active notifications
            allNotifications = allNotifications.filter(n => n.id !== notificationId);
            // Refresh archived processes
            await loadArchivedProcesses();
            // Update views
            updateScheduledProcessesView();
            console.log('Process archived successfully');
        } else {
            console.error('Failed to archive process');
        }
    } catch (error) {
        console.error('Error archiving process:', error);
    }
}

// Load archived processes from backend
async function loadArchivedProcesses() {
    try {
        const response = await fetch('/api/email/archived');
        const data = await response.json();
        
        if (data.success && data.processes) {
            archivedProcesses = data.processes;
        } else {
            archivedProcesses = [];
        }
    } catch (error) {
        console.error('Error loading archived processes:', error);
        archivedProcesses = [];
    }
}

// Refresh scheduled processes
async function refreshScheduledProcesses() {
    // Load archived processes if on completed tab
    if (currentScheduledProcessesTab === 'completed') {
        await loadArchivedProcesses();
    }
    updateScheduledProcessesView();
    // Also refresh notifications to get latest data
    checkEmailNotifications();
}

// Update notifications view
function updateNotificationsView() {
    const notificationsList = document.getElementById('notifications-list');
    if (!notificationsList) return;

    if (allNotifications.length === 0) {
        notificationsList.innerHTML = '<div class="text-center text-text-secondary">No notifications</div>';
        return;
    }

    notificationsList.innerHTML = allNotifications.map(notification => {
        const icon = notification.type === 'command' ? '⚙️' : '📧';
        const unreadClass = notification.read ? '' : 'unread';

        return `
            <div class="notification-item ${unreadClass}">
                <div class="flex items-center justify-between mb-2">
                    <div class="font-semibold text-sm">${icon} ${notification.subject}</div>
                    ${!notification.read ? '<span class="text-xs text-blue-600 font-semibold">NEW</span>' : ''}
                </div>
                <div class="text-xs text-text-secondary mb-1">From: ${notification.from}</div>
                ${notification.body ? `<div class="text-xs text-text-secondary">${notification.body.substring(0, 100)}${notification.body.length > 100 ? '...' : ''}</div>` : ''}
                <div class="text-xs text-text-secondary mt-2">${new Date(notification.timestamp).toLocaleString()}</div>
            </div>
        `;
    }).join('');
}

// Poll for email command notifications
async function checkEmailNotifications() {
    try {
        const response = await fetch('/api/email/notifications');
        
        if (!response.ok) {
            console.warn(`Failed to fetch notifications: HTTP ${response.status}`);
            return;
        }
        
        const data = await response.json();

        if (data.success) {
            // Update our notifications list (always update, even if empty)
            if (data.notifications && data.notifications.length > 0) {
                allNotifications = data.notifications.map(n => ({
                    ...n,
                    read: shownNotifications.has(n.id)
                }));

                // Mark new notifications as shown (but don't mark them as read automatically)
                data.notifications.forEach(notification => {
                    if (!shownNotifications.has(notification.id)) {
                        shownNotifications.add(notification.id);
                        // Log new notifications for debugging
                        console.log('New notification:', notification.type, notification.subject);
                    }
                });
            } else {
                allNotifications = [];
            }

            // Always update badges and views (even if empty)
            updateMailboxBadge();
            updateScheduledProcessesView();
            updateNotificationsView();
        } else {
            console.warn('Failed to fetch notifications:', data);
            allNotifications = [];
            updateMailboxBadge();
            updateScheduledProcessesView();
            updateNotificationsView();
        }
    } catch (error) {
        console.error('Error checking email notifications:', error);
        // Still try to update views with empty list
        allNotifications = [];
        updateMailboxBadge();
        updateScheduledProcessesView();
        updateNotificationsView();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // File manager will refresh when window is opened

    // Start polling for email notifications immediately and then every 10 seconds
    checkEmailNotifications();
    setInterval(checkEmailNotifications, 10000);
    
    // Also ensure desktop icons are initialized
    setTimeout(() => {
        ensureDesktopIcons();
    }, 200);
});

// Load file manager on window creation
const originalCreateWindow = createWindow;
function createWindowWithInit(appName, title, position) {
    const windowId = originalCreateWindow(appName, title, position);
    setTimeout(() => {
        if (appName === 'file_manager') {
            fileManagerRefresh();
        } else if (appName === 'mailbox') {
            mailboxRefresh();
        }
    }, 100);
    return windowId;
}

// Mailbox Functions
let mailboxCurrentPage = 1;
const mailboxPerPage = 20;

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function mailboxRefresh(page = 1) {
    const inboxView = document.getElementById('mailbox-inbox-view');
    const status = document.getElementById('mailbox-status');
    const paginationEl = document.getElementById('mailbox-pagination');
    const prevBtn = document.getElementById('mailbox-prev');
    const nextBtn = document.getElementById('mailbox-next');
    const pageInfo = document.getElementById('mailbox-page-info');
    
    if (!inboxView) return;
    
    mailboxCurrentPage = page;
    
    inboxView.innerHTML = '<div class="text-center text-text-secondary">Loading inbox...</div>';
    if (status) status.textContent = 'Loading...';
    if (paginationEl) paginationEl.classList.add('hidden');
    
    try {
        const response = await fetch(`/api/email/inbox?page=${page}&per_page=${mailboxPerPage}&summaries=true`);
        const data = await response.json();
        
        if (data.success) {
            const pagination = data.pagination || {};
            const totalCount = pagination.total || 0;
            const receivedCount = data.received_count || 0;
            const sentCount = data.sent_count || 0;
            
            if (status) {
                let statusText = `${totalCount} email${totalCount !== 1 ? 's' : ''}`;
                if (receivedCount > 0 || sentCount > 0) {
                    statusText += ` (${receivedCount} received, ${sentCount} sent)`;
                }
                status.textContent = statusText;
            }
            
            // Update pagination controls
            if (paginationEl && pagination.total_pages > 1) {
                paginationEl.classList.remove('hidden');
                if (pageInfo) {
                    pageInfo.textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
                }
                if (prevBtn) {
                    prevBtn.disabled = !pagination.has_prev;
                    prevBtn.style.opacity = pagination.has_prev ? '1' : '0.5';
                    prevBtn.style.cursor = pagination.has_prev ? 'pointer' : 'not-allowed';
                }
                if (nextBtn) {
                    nextBtn.disabled = !pagination.has_next;
                    nextBtn.style.opacity = pagination.has_next ? '1' : '0.5';
                    nextBtn.style.cursor = pagination.has_next ? 'pointer' : 'not-allowed';
                }
            } else if (paginationEl) {
                paginationEl.classList.add('hidden');
            }
            
            if (data.emails && data.emails.length > 0) {
                inboxView.innerHTML = '';
                data.emails.forEach(email => {
                    const emailItem = document.createElement('div');
                    emailItem.className = 'mailbox-email-item';
                    
                    // Handle timestamp
                    let timestamp = 'Just now';
                    if (email.received_at) {
                        timestamp = new Date(email.received_at).toLocaleString();
                    } else if (email.timestamp) {
                        timestamp = new Date(email.timestamp).toLocaleString();
                    }
                    
                    // Get preview text
                    const previewText = email.text || email.body || '';
                    const preview = previewText ? escapeHtml(previewText.substring(0, 150).replace(/\n/g, ' ').trim() + (previewText.length > 150 ? '...' : '')) : 'No preview';
                    
                    // Determine sender/recipient
                    const isReceived = email.sent === false || email.status === 'received';
                    const senderRecipient = isReceived 
                        ? escapeHtml(email.from || 'Unknown sender')
                        : escapeHtml(email.to || 'Unknown recipient');
                    
                    const subject = escapeHtml(email.subject || '(No subject)');
                    const emailId = escapeHtml(String(email.id || email.message_id || ''));
                    
                    // Status badge
                    let statusBadge = '';
                    if (email.status === 'sent' || email.sent === true) {
                        statusBadge = '<span class="text-xs px-2 py-0.5 bg-green-500/20 text-green-600 rounded">Sent</span>';
                    } else if (email.status === 'received' || isReceived) {
                        statusBadge = '<span class="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-600 rounded">Received</span>';
                    }
                    
                    emailItem.innerHTML = `
                        <div class="flex items-start gap-4 p-4 border-b border-border hover:bg-hover transition cursor-pointer" data-email-id="${emailId}">
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="font-semibold text-black text-sm">${senderRecipient}</span>
                                    ${statusBadge}
                                </div>
                                <div class="font-medium text-black text-sm mb-1">${subject}</div>
                                <div class="text-xs text-text-secondary line-clamp-2">${preview}</div>
                                <div class="text-xs text-text-secondary mt-2">${escapeHtml(timestamp)}</div>
                            </div>
                        </div>
                    `;
                    emailItem.querySelector('[data-email-id]').addEventListener('click', () => {
                        mailboxViewEmail(emailId, email);
                    });
                    inboxView.appendChild(emailItem);
                });
            } else {
                inboxView.innerHTML = `
                    <div class="text-center text-text-secondary py-12">
                        <i class="fas fa-inbox text-4xl mb-4 opacity-50"></i>
                        <p>No emails yet</p>
                        <p class="text-xs mt-2">Click "Compose" to send your first email</p>
                    </div>
                `;
            }
        } else {
            inboxView.innerHTML = '<div class="text-center text-red-500">Error loading inbox</div>';
        }
    } catch (error) {
        inboxView.innerHTML = '<div class="text-center text-red-500">Error loading inbox</div>';
        console.error(error);
    }
}

function mailboxPreviousPage() {
    if (mailboxCurrentPage > 1) {
        mailboxRefresh(mailboxCurrentPage - 1);
        // Scroll to top of inbox
        const inboxView = document.getElementById('mailbox-inbox-view');
        if (inboxView) {
            inboxView.scrollTop = 0;
        }
    }
}

function mailboxNextPage() {
    mailboxRefresh(mailboxCurrentPage + 1);
    // Scroll to top of inbox
    const inboxView = document.getElementById('mailbox-inbox-view');
    if (inboxView) {
        inboxView.scrollTop = 0;
    }
}

function mailboxCompose() {
    const inboxView = document.getElementById('mailbox-inbox-view');
    const composeView = document.getElementById('mailbox-compose-view');
    const instructionsTextarea = document.getElementById('compose-instructions');
    const paginationEl = document.getElementById('mailbox-pagination');
    
    if (inboxView) inboxView.classList.add('hidden');
    if (paginationEl) paginationEl.classList.add('hidden');
    if (composeView) {
        composeView.classList.remove('hidden');
        if (instructionsTextarea) {
            instructionsTextarea.value = '';
            instructionsTextarea.focus();
        }
    }
}

function mailboxBackToInbox() {
    const inboxView = document.getElementById('mailbox-inbox-view');
    const composeView = document.getElementById('mailbox-compose-view');
    const instructionsTextarea = document.getElementById('compose-instructions');
    const paginationEl = document.getElementById('mailbox-pagination');
    
    if (composeView) composeView.classList.add('hidden');
    if (inboxView) inboxView.classList.remove('hidden');
    if (instructionsTextarea) instructionsTextarea.value = '';
    // Reset to first page when going back to inbox
    mailboxRefresh(1);
}

async function mailboxSendEmail() {
    const instructionsTextarea = document.getElementById('compose-instructions');
    const status = document.getElementById('mailbox-status');
    
    if (!instructionsTextarea) return;
    
    const instructions = instructionsTextarea.value.trim();
    if (!instructions) {
        alert('Please enter instructions for the email');
        return;
    }
    
    if (status) status.textContent = 'Sending...';
    
    const response = await fetch('/api/email/compose-send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instructions })
    });
    
    const data = await response.json();
    console.log('Email API Response:', data);
    
    if (data.success) {
        instructionsTextarea.value = '';
        mailboxBackToInbox();
        mailboxRefresh();
        alert('Email sent successfully!');
    } else {
        alert('Error sending email. Please try again.');
    }
    if (status) status.textContent = '';
}

function mailboxViewEmail(emailId, emailData = null) {
    // Create a modal to display email details
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-[100]';
    modal.innerHTML = `
        <div class="bg-menu border border-border rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col">
            <div class="flex items-center justify-between p-4 border-b border-border">
                <h3 class="text-white font-semibold text-lg">Email Details</h3>
                <button onclick="this.closest('.fixed').remove()" class="text-text-secondary hover:text-white p-2">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="flex-1 overflow-auto p-6">
                ${emailData ? `
                    <div class="space-y-4">
                        <div>
                            <label class="text-text-secondary text-xs uppercase tracking-wide">From</label>
                            <p class="text-white text-sm mt-1">${escapeHtml(emailData.from || emailData.to || 'Unknown')}</p>
                        </div>
                        <div>
                            <label class="text-text-secondary text-xs uppercase tracking-wide">Subject</label>
                            <p class="text-white text-sm mt-1">${escapeHtml(emailData.subject || '(No subject)')}</p>
                        </div>
                        <div>
                            <label class="text-text-secondary text-xs uppercase tracking-wide">Date</label>
                            <p class="text-white text-sm mt-1">${emailData.received_at ? new Date(emailData.received_at).toLocaleString() : (emailData.timestamp ? new Date(emailData.timestamp).toLocaleString() : 'Unknown')}</p>
                        </div>
                        <div>
                            <label class="text-text-secondary text-xs uppercase tracking-wide">Message</label>
                            <div class="text-white text-sm mt-1 whitespace-pre-wrap bg-input/50 p-4 rounded-lg">
                                ${escapeHtml(emailData.text || emailData.body || emailData.html || 'No content')}
                            </div>
                        </div>
                    </div>
                ` : '<p class="text-text-secondary">Loading email details...</p>'}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Browser Functions
let browserWindowSessions = new Map(); // Map window IDs to session IDs

function getBrowserSession() {
    // Find the active browser window and get its session
    const browserWindows = Array.from(document.querySelectorAll('.window'))
        .filter(w => w.querySelector('#browser-url'));
    
    if (browserWindows.length === 0) return 'default';
    
    // Get the topmost browser window
    const topBrowserWindow = browserWindows
        .sort((a, b) => parseInt(b.style.zIndex || 0) - parseInt(a.style.zIndex || 0))[0];
    
    if (topBrowserWindow && topBrowserWindow.dataset.browserSession) {
        return topBrowserWindow.dataset.browserSession;
    }
    
    // Fallback: try to get from window ID
    const windowId = topBrowserWindow?.id;
    if (windowId && browserWindowSessions.has(windowId)) {
        return browserWindowSessions.get(windowId);
    }
    
    return 'default';
}

async function browserNavigateWithSession(sessionId, url, windowElement = null, agentGoal = null) {
    // If no window element provided, find the current one
    if (!windowElement) {
        const browserWindows = Array.from(document.querySelectorAll('.window'))
            .filter(w => w.querySelector('#browser-url'));
        windowElement = browserWindows
            .sort((a, b) => parseInt(b.style.zIndex || 0) - parseInt(a.style.zIndex || 0))[0];
    }
    
    if (!windowElement) return;
    
    const urlInput = windowElement.querySelector('#browser-url');
    const contentDiv = windowElement.querySelector('#browser-content');
    const iframe = windowElement.querySelector('#browser-iframe');
    const placeholder = windowElement.querySelector('#browser-placeholder');
    
    if (!urlInput || !contentDiv) return;
    
    urlInput.value = url;
    
    // Show loading
    if (placeholder) placeholder.style.display = 'flex';
    if (iframe) iframe.style.display = 'none';
    
    try {
        const response = await fetch('/api/browser/navigate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, session_id: sessionId, agent_goal: agentGoal })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (urlInput) urlInput.value = data.url;
            
            // Load the proxied page in iframe
            if (iframe && data.proxy_url) {
                iframe.src = data.proxy_url;
                iframe.style.display = 'block';
                iframe.onload = () => {
                    if (placeholder) placeholder.style.display = 'none';
                };
            } else {
                if (placeholder) placeholder.style.display = 'none';
            }
            
            // Update window title if possible
            if (windowElement && data.title) {
                const titleSpan = windowElement.querySelector('.window-title span');
                if (titleSpan) {
                    titleSpan.textContent = data.title.length > 40 ? data.title.substring(0, 40) + '...' : data.title;
                }
            }
            
            // If agent goal is set, start the agent and add status panel
            if (data.agent_goal) {
                addAgentStatusPanel(windowElement, sessionId, data.agent_goal);
                pollAgentStatus(sessionId, windowElement);
            }
        } else {
            alert('Error navigating to URL');
            if (placeholder) placeholder.style.display = 'flex';
        }
    } catch (error) {
        alert('Error: ' + error.message);
        console.error(error);
        if (placeholder) placeholder.style.display = 'flex';
    }
}

async function browserNavigate(sessionId = null) {
    const urlInput = document.getElementById('browser-url');
    const contentDiv = document.getElementById('browser-content');
    const iframe = document.getElementById('browser-iframe');
    const placeholder = document.getElementById('browser-placeholder');
    
    if (!urlInput || !contentDiv) return;
    
    const url = urlInput.value.trim();
    if (!url) return;
    
    // Get session ID for this browser window
    if (!sessionId) {
        sessionId = getBrowserSession();
    }
    
    // Show loading
    if (placeholder) placeholder.style.display = 'flex';
    if (iframe) iframe.style.display = 'none';
    
    try {
        const response = await fetch('/api/browser/navigate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, session_id: sessionId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            urlInput.value = data.url;
            
            // Load the proxied page in iframe
            if (iframe && data.proxy_url) {
                iframe.src = data.proxy_url;
                iframe.style.display = 'block';
                iframe.onload = () => {
                    if (placeholder) placeholder.style.display = 'none';
                };
            } else {
                if (placeholder) placeholder.style.display = 'none';
            }
            
            // Update window title if possible
            const browserWindow = contentDiv.closest('.window');
            if (browserWindow && data.title) {
                const titleSpan = browserWindow.querySelector('.window-title span');
                if (titleSpan) {
                    titleSpan.textContent = data.title.length > 40 ? data.title.substring(0, 40) + '...' : data.title;
                }
            }
        } else {
            alert('Error navigating to URL');
            if (placeholder) placeholder.style.display = 'flex';
        }
    } catch (error) {
        alert('Error: ' + error.message);
        console.error(error);
        if (placeholder) placeholder.style.display = 'flex';
    }
}

async function browserReload() {
    const urlInput = document.getElementById('browser-url');
    if (!urlInput || !urlInput.value) return;
    
    await browserNavigate();
}

async function browserBack() {
    const sessionId = getBrowserSession();
    try {
        const response = await fetch('/api/browser/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'back', session_id: sessionId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const urlInput = document.getElementById('browser-url');
            const iframe = document.getElementById('browser-iframe');
            const placeholder = document.getElementById('browser-placeholder');
            
            if (urlInput) urlInput.value = data.url;
            if (iframe && data.proxy_url) {
                iframe.src = data.proxy_url;
                iframe.style.display = 'block';
            }
            if (placeholder) placeholder.style.display = 'none';
        }
    } catch (error) {
        console.error('Error going back:', error);
    }
}

async function browserForward() {
    const sessionId = getBrowserSession();
    try {
        const response = await fetch('/api/browser/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'forward', session_id: sessionId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const urlInput = document.getElementById('browser-url');
            const iframe = document.getElementById('browser-iframe');
            const placeholder = document.getElementById('browser-placeholder');
            
            if (urlInput) urlInput.value = data.url;
            if (iframe && data.proxy_url) {
                iframe.src = data.proxy_url;
                iframe.style.display = 'block';
            }
            if (placeholder) placeholder.style.display = 'none';
        }
    } catch (error) {
        console.error('Error going forward:', error);
    }
}

// Note: Clicks and interactions now work directly in the iframe
// The iframe loads the proxied HTML which includes interactive elements

// Perform automatic browser search
async function performBrowserSearch(sessionId, searchTerm, windowElement) {
    if (!sessionId || !searchTerm) return;
    
    try {
        // Directly call control_browser endpoint with the search command
        const response = await fetch('/api/browser/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                command: `type ${searchTerm} in the search box and click the search button or press enter`,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.data && data.data.proxy_url) {
            // Update the browser iframe
            const iframe = windowElement.querySelector('#browser-iframe');
            const urlInput = windowElement.querySelector('#browser-url');
            const placeholder = windowElement.querySelector('#browser-placeholder');
            
            if (iframe && data.data.proxy_url) {
                iframe.src = data.data.proxy_url;
                iframe.style.display = 'block';
            }
            if (placeholder) placeholder.style.display = 'none';
            if (urlInput && data.data.url) {
                urlInput.value = data.data.url;
            }
        }
    } catch (error) {
        console.error('Error performing automatic search:', error);
    }
}

// Agent Status Functions
function addAgentStatusPanel(windowElement, sessionId, goal) {
    if (!windowElement) return;
    
    // Check if panel already exists
    let panel = windowElement.querySelector('.agent-status-panel');
    if (panel) return;
    
    const browserContent = windowElement.querySelector('#browser-content');
    if (!browserContent) return;
    
    // Create agent status panel
    panel = document.createElement('div');
    panel.className = 'agent-status-panel bg-slate-900/90 border-t border-slate-700 p-3 text-white text-xs';
    panel.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
                <div class="agent-status-indicator w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
                <span class="font-semibold">Agent Active</span>
            </div>
            <button class="toggle-logs-btn text-slate-400 hover:text-white" onclick="toggleAgentLogs(this)">
                <i class="fas fa-chevron-down"></i>
            </button>
        </div>
        <div class="agent-goal text-slate-300 mb-2">${goal}</div>
        <div class="agent-logs-container hidden max-h-40 overflow-y-auto space-y-1"></div>
    `;
    
    panel.dataset.sessionId = sessionId;
    browserContent.appendChild(panel);
}

function pollAgentStatus(sessionId, windowElement) {
    const panel = windowElement.querySelector('.agent-status-panel');
    if (!panel) return;
    
    const statusIndicator = panel.querySelector('.agent-status-indicator');
    const logsContainer = panel.querySelector('.agent-logs-container');
    
    const poll = async () => {
        try {
            const response = await fetch(`/api/browser/agent/${sessionId}`);
            const data = await response.json();
            
            // Update status indicator
            if (statusIndicator) {
                const colors = {
                    'idle': 'bg-gray-400',
                    'active': 'bg-green-400',
                    'thinking': 'bg-yellow-400 animate-pulse',
                    'analyzing': 'bg-blue-400 animate-pulse',
                    'planning': 'bg-purple-400 animate-pulse',
                    'executing': 'bg-orange-400 animate-pulse',
                    'completed': 'bg-green-500',
                    'error': 'bg-red-400'
                };
                statusIndicator.className = `agent-status-indicator w-2 h-2 rounded-full ${colors[data.status] || 'bg-gray-400'}`;
            }
            
            // Update logs
            if (logsContainer && data.logs && data.logs.length > 0) {
                logsContainer.innerHTML = '';
                data.logs.slice(-10).forEach(log => {
                    const logEntry = document.createElement('div');
                    logEntry.className = 'text-slate-400 text-xs flex items-start gap-2';
                    
                    const icon = {
                        'analyzing': '📸',
                        'planning': '🧠',
                        'click': '🖱️',
                        'type': '⌨️',
                        'scroll': '📜',
                        'done': '✅',
                        'error': '❌',
                        'started': '🚀',
                        'goal_set': '📝'
                    }[log.action] || '•';
                    
                    const time = new Date(log.timestamp).toLocaleTimeString();
                    logEntry.innerHTML = `
                        <span>${icon}</span>
                        <span class="flex-1">
                            <span class="text-slate-500">[${time}]</span> ${log.message || ''}
                            ${log.progress ? `<div class="text-slate-500 ml-4">${log.progress}</div>` : ''}
                            ${log.next ? `<div class="text-slate-500 ml-4">➡️ ${log.next}</div>` : ''}
                        </span>
                    `;
                    logsContainer.appendChild(logEntry);
                });
            }
            
            // Continue polling if agent is active
            if (data.status !== 'completed' && data.status !== 'error') {
                setTimeout(poll, 2000); // Poll every 2 seconds
            } else if (data.status === 'completed') {
                if (statusIndicator) {
                    statusIndicator.className = 'agent-status-indicator w-2 h-2 rounded-full bg-green-500';
                }
            }
        } catch (error) {
            console.error('Error polling agent status:', error);
            setTimeout(poll, 5000); // Retry after 5 seconds on error
        }
    };
    
    // Start polling
    poll();
}

function toggleAgentLogs(btn) {
    const panel = btn.closest('.agent-status-panel');
    const logsContainer = panel.querySelector('.agent-logs-container');
    const icon = btn.querySelector('i');
    
    if (logsContainer.classList.contains('hidden')) {
        logsContainer.classList.remove('hidden');
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        logsContainer.classList.add('hidden');
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
}

// Slideshow Functions
let currentSlideshowHtml = '';
let currentSlideIndex = 0;
let totalSlides = 0;
let selectedTemplate = 'modern';

function selectTemplate(template) {
    selectedTemplate = template;
    // Update UI
    document.querySelectorAll('.template-option').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-template="${template}"]`)?.classList.add('active');
}

async function slideshowGenerate(promptText = null, autoTemplate = null) {
    const prompt = document.getElementById('slideshow-prompt');
    const status = document.getElementById('slideshow-status');
    const preview = document.getElementById('slideshow-preview');
    const iframe = document.getElementById('slideshow-iframe');
    
    const finalPrompt = promptText || (prompt ? prompt.value.trim() : '');
    if (!finalPrompt) {
        alert('Please enter a description for the slideshow');
        return;
    }
    
    if (status) status.textContent = 'Generating slideshow...';
    
    // Use selected template or auto-selected one
    const templateToUse = autoTemplate || selectedTemplate;
    
    try {
        const response = await fetch('/api/slideshow/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                prompt: finalPrompt,
                template_style: templateToUse 
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.html) {
            currentSlideshowHtml = data.html;
            totalSlides = data.slide_count || 1;
            currentSlideIndex = 0;
            
            // Show preview
            if (preview) preview.style.display = 'block';
            if (iframe) {
                iframe.srcdoc = currentSlideshowHtml;
            }
            
            if (status) status.textContent = `Generated ${totalSlides} slides`;
            
            // Switch to player view
            slideshowShowPlayer();
        } else {
            alert('Error generating slideshow: ' + (data.error || 'Unknown error'));
            if (status) status.textContent = 'Error';
        }
    } catch (error) {
        alert('Error generating slideshow: ' + error.message);
        console.error(error);
        if (status) status.textContent = 'Error';
    }
}

function slideshowShowPlayer() {
    const creatorView = document.getElementById('slideshow-creator-view');
    const playerView = document.getElementById('slideshow-player-view');
    const playerIframe = document.getElementById('slideshow-player-iframe');
    
    if (creatorView) creatorView.classList.add('hidden');
    if (playerView) {
        playerView.classList.remove('hidden');
        if (playerIframe && currentSlideshowHtml) {
            playerIframe.srcdoc = currentSlideshowHtml;
            // Wait for iframe to load then navigate to first slide
            playerIframe.onload = () => {
                try {
                    const iframeDoc = playerIframe.contentDocument || playerIframe.contentWindow.document;
                    if (iframeDoc) {
                        // Navigate to first slide
                        showSlide(0);
                    }
                } catch (e) {
                    console.error('Error accessing iframe:', e);
                }
            };
        }
    }
}

function slideshowBackToCreator() {
    const creatorView = document.getElementById('slideshow-creator-view');
    const playerView = document.getElementById('slideshow-player-view');
    
    if (playerView) playerView.classList.add('hidden');
    if (creatorView) creatorView.classList.remove('hidden');
}

function showSlide(index) {
    const playerIframe = document.getElementById('slideshow-player-iframe');
    if (!playerIframe || !currentSlideshowHtml) return;
    
    try {
        const iframeDoc = playerIframe.contentDocument || playerIframe.contentWindow.document;
        if (!iframeDoc) return;
        
        const slides = iframeDoc.querySelectorAll('.slide');
        if (slides.length === 0) return;
        
        totalSlides = slides.length;
        currentSlideIndex = Math.max(0, Math.min(index, totalSlides - 1));
        
        // Hide all slides
        slides.forEach((slide, i) => {
            slide.style.display = i === currentSlideIndex ? 'flex' : 'none';
        });
        
        // Update slide indicator if it exists
        const indicator = iframeDoc.querySelector('.slide-indicator');
        if (indicator) {
            indicator.textContent = `${currentSlideIndex + 1} / ${totalSlides}`;
        }
    } catch (e) {
        console.error('Error showing slide:', e);
    }
}

function slideshowNext() {
    showSlide(currentSlideIndex + 1);
}

function slideshowPrev() {
    showSlide(currentSlideIndex - 1);
}

async function slideshowCreate() {
    const prompt = document.getElementById('slideshow-prompt');
    if (prompt) prompt.value = '';
    const preview = document.getElementById('slideshow-preview');
    if (preview) preview.style.display = 'none';
    currentSlideshowHtml = '';
}

async function slideshowLoad() {
    const filename = prompt('Enter slideshow file name:');
    if (!filename) return;
    
    try {
        const response = await fetch(`/api/files/read?path=${encodeURIComponent(filename)}`);
        const data = await response.json();
        
        if (data.content) {
            currentSlideshowHtml = data.content;
            const preview = document.getElementById('slideshow-preview');
            const iframe = document.getElementById('slideshow-iframe');
            if (preview) preview.style.display = 'block';
            if (iframe) iframe.srcdoc = data.content;
            slideshowShowPlayer();
        }
    } catch (error) {
        alert('Error loading slideshow: ' + error.message);
    }
}

async function slideshowSave() {
    if (!currentSlideshowHtml) {
        alert('No slideshow to save');
        return;
    }
    
    const filename = prompt('Enter file name:', 'slideshow.html');
    if (!filename) return;
    
    try {
        const response = await fetch('/api/files/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                path: filename.endsWith('.html') ? filename : filename + '.html',
                content: currentSlideshowHtml
            })
        });
        
        if (response.ok) {
            alert('Slideshow saved!');
            refreshDesktop();
        } else {
            alert('Error saving slideshow');
        }
    } catch (error) {
        alert('Error saving slideshow: ' + error.message);
    }
}

// ============================================
// Sync Application Functions
// ============================================

let currentUserToken = null;
const userId = 'default_user'; // In production, this would come from authentication

async function syncLoadIntegrations() {
    const loading = document.getElementById('sync-loading');
    const integrationsView = document.getElementById('sync-integrations');
    const integrationsGrid = document.getElementById('integrations-grid');

    if (!integrationsGrid) return;

    try {
        // Generate user token
        const tokenResponse = await fetch('/api/hyperspell/user-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });

        const tokenData = await tokenResponse.json();
        currentUserToken = tokenData.token;

        // Fetch available integrations
        const integrationsResponse = await fetch('/api/hyperspell/integrations');
        const data = await integrationsResponse.json();

        if (data.success && data.integrations) {
            integrationsGrid.innerHTML = '';

            data.integrations.forEach(integration => {
                const card = document.createElement('div');
                card.className = 'integration-card bg-slate-700/50 hover:bg-slate-700 p-4 rounded-lg border border-border hover:border-blue-500/50 transition cursor-pointer';
                card.innerHTML = `
                    <div class="flex items-start gap-3">
                        <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                            <i class="fab ${integration.icon} text-white text-lg"></i>
                        </div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-white font-semibold text-sm mb-1">${integration.name}</h4>
                            <p class="text-text-secondary text-xs line-clamp-2">${integration.description}</p>
                        </div>
                    </div>
                    <button class="mt-3 w-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium px-3 py-2 rounded-lg transition" onclick="syncConnectIntegration('${integration.id}', '${integration.name}')">
                        Connect
                    </button>
                `;
                integrationsGrid.appendChild(card);
            });

            if (loading) loading.classList.add('hidden');
            if (integrationsView) integrationsView.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error loading integrations:', error);
        if (loading) {
            loading.innerHTML = `
                <i class="fas fa-exclamation-triangle text-3xl mb-3 text-red-400"></i>
                <p>Error loading integrations</p>
            `;
        }
    }
}

async function syncConnectIntegration(integrationId, integrationName) {
    try {
        // Get the integration connection link
        const response = await fetch('/api/hyperspell/integration-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                integration_id: integrationId,
                user_id: userId,
                redirect_uri: window.location.origin
            })
        });

        const data = await response.json();

        if (data.success && data.link) {
            // Open Hyperspell Connect in a new window
            const connectWindow = window.open(
                data.link,
                `Connect ${integrationName}`,
                'width=600,height=700,menubar=no,toolbar=no,location=no'
            );

            // Optional: Poll for connection status
            if (connectWindow) {
                const pollInterval = setInterval(() => {
                    if (connectWindow.closed) {
                        clearInterval(pollInterval);
                        // Refresh integrations list
                        syncRefreshConnectedIntegrations();
                    }
                }, 1000);
            }
        } else {
            alert('Error generating connection link');
        }
    } catch (error) {
        console.error('Error connecting integration:', error);
        alert('Error connecting to integration');
    }
}

async function syncRefreshConnectedIntegrations() {
    const connectedDiv = document.getElementById('connected-integrations');
    if (!connectedDiv) return;

    try {
        const response = await fetch(`/api/hyperspell/user/${userId}`);
        const data = await response.json();

        if (data.success && data.user) {
            const connectedIntegrations = data.user.connected_integrations || [];

            if (connectedIntegrations.length > 0) {
                connectedDiv.innerHTML = connectedIntegrations.map(integration => `
                    <div class="bg-slate-700/50 p-3 rounded-lg border border-border flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center">
                                <i class="fas fa-check text-green-400"></i>
                            </div>
                            <span class="text-white text-sm font-medium">${integration}</span>
                        </div>
                        <button class="text-text-secondary hover:text-red-400 transition text-xs" onclick="syncDisconnectIntegration('${integration}')">
                            Disconnect
                        </button>
                    </div>
                `).join('');
            } else {
                connectedDiv.innerHTML = '<p class="text-sm text-text-secondary">No integrations connected yet</p>';
            }
        }
    } catch (error) {
        console.error('Error refreshing connected integrations:', error);
    }
}

async function syncDisconnectIntegration(integrationId) {
    if (!confirm(`Are you sure you want to disconnect ${integrationId}?`)) {
        return;
    }

    // In production, this would call a disconnect API
    alert('Disconnect functionality would be implemented with Hyperspell API');
    syncRefreshConnectedIntegrations();
}

// ============================================
// Keyboard navigation for slideshow
// ============================================
document.addEventListener('keydown', (e) => {
    const playerView = document.getElementById('slideshow-player-view');
    if (playerView && !playerView.classList.contains('hidden')) {
        if (e.key === 'ArrowRight' || e.key === ' ') {
            e.preventDefault();
            slideshowNext();
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            slideshowPrev();
        }
    }
});

