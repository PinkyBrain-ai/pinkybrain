/**
 * PinkyBrain Desktop — Main Application (Vanilla JS)
 * No frameworks. Just clean, functional JavaScript.
 * Full i18n support via i18n module.
 */

(function () {
    'use strict';

    // ─── State ──────────────────────────────────────────────

    const state = {
        connected: false,
        currentTab: 'chat',
        conversations: [],
        activeConversation: null,
        models: [],
        peers: [],
        status: {},
        config: {},
        wsConnected: false,
        sendInProgress: false,
    };

    // ─── DOM refs ───────────────────────────────────────────

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ─── i18n helper ────────────────────────────────────────

    function t(key, params) {
        return i18n.t(key, params);
    }

    /** Update all translatable elements in the DOM that have data-i18n attributes */
    function applyI18NToDOM() {
        // Update elements with data-i18n="key"
        $$('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            el.textContent = t(key);
        });
        // Update placeholders
        $$('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = t(key);
        });
        // Update titles
        $$('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = t(key);
        });
    }

    // ─── Init ───────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', async () => {
        // Initialize i18n first
        await i18n.init();
        populateLangSelect();
        loadConversationsFromStorage();
        setupTabs();
        setupChat();
        setupShare();
        loadBandwidthQuota();
        setupNetwork();
        setupConfig();
        setupSidebar();
        setupMobile();
        applyI18NToDOM();
        refreshAll();
        api.connectWebSocket();

        // Periodic refresh
        setInterval(refreshAll, 15000);
    });

    // ─── Language selector ──────────────────────────────────

    function populateLangSelect() {
        const select = $('#cfgLang');
        if (!select) return;
        select.innerHTML = '';
        i18n.getSupportedLocales().forEach(({ code, name, active }) => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = name;
            if (active) opt.selected = true;
            select.appendChild(opt);
        });
    }

    // ─── Refresh all data ──────────────────────────────────

    async function refreshAll() {
        const [status, peers, models, capabilities] = await Promise.allSettled([
            api.getStatus(),
            api.getPeers(),
            api.getModels(),
            api.getCapabilities(),
        ]);

        if (status.value) {
            state.status = status.value;
            state.connected = true;
            updateHeader(status.value);
            updateSidebarStats(status.value);
        } else {
            state.connected = false;
            updateHeader(null);
        }

        if (peers.value) {
            state.peers = peers.value.peers || peers.value || [];
            renderNetworkPeers();
        }

        if (models.value) {
            state.models = models.value.models || models.value || [];
            renderModelsList();
            renderModelsShareList();
            updateModelSelect();
        }

        if (capabilities.value) {
            updateCapabilities(capabilities.value);
        }
    }

    // ─── Header ────────────────────────────────────────────

    function updateHeader(status) {
        const dot = $('#statusDot');
        const text = $('#statusText');
        const peerCt = $('#peerCount');

        if (!status) {
            dot.className = 'status-dot error';
            text.textContent = t('header.disconnected');
            peerCt.textContent = t('header.peers_zero');
            return;
        }

        dot.className = 'status-dot connected';
        text.textContent = t('header.connected');
        const peerCount = state.peers ? state.peers.length : 0;
        peerCt.textContent = t('header.peers', { count: peerCount });
        $('#nodeVersion').textContent = `v${status.version || '4.2.0'}`;
    }

    function updateSidebarStats(status) {
        if (!status) return;
        const cpuEl = $('#sidebarCpu');
        const ramEl = $('#sidebarRam');
        if (status.cpu_percent !== undefined) cpuEl.textContent = `${status.cpu_percent}%`;
        if (status.ram_percent !== undefined) ramEl.textContent = `${status.ram_percent}%`;
    }

    // ─── Tabs ──────────────────────────────────────────────

    function setupTabs() {
        $$('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('.tab-btn').forEach(b => b.classList.remove('active'));
                $$('.tab-panel').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                const tabId = `tab-${btn.dataset.tab}`;
                $(`#${tabId}`).classList.add('active');
                state.currentTab = btn.dataset.tab;
            });
        });
    }

    // ─── Chat ──────────────────────────────────────────────

    function setupChat() {
        const input = $('#chatInput');
        const sendBtn = $('#sendBtn');
        const newConvBtn = $('#newConvBtn');

        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });

        newConvBtn.addEventListener('click', newConversation);

        renderConversationsList();
    }

    function newConversation() {
        const conv = {
            id: `conv_${Date.now()}`,
            title: t('sidebar.newConversationTitle'),
            messages: [],
            created: Date.now(),
            model: 'auto',
        };
        state.conversations.unshift(conv);
        state.activeConversation = conv.id;
        renderConversationsList();
        renderChatMessages();
        saveConversationsToStorage();
    }

    function selectConversation(id) {
        state.activeConversation = id;
        renderConversationsList();
        renderChatMessages();
    }

    function deleteConversation(id) {
        state.conversations = state.conversations.filter(c => c.id !== id);
        if (state.activeConversation === id) {
            state.activeConversation = state.conversations[0]?.id || null;
        }
        renderConversationsList();
        renderChatMessages();
        saveConversationsToStorage();
    }

    async function sendMessage() {
        if (state.sendInProgress) return;

        const input = $('#chatInput');
        const text = input.value.trim();
        if (!text) return;

        // Create conversation if needed
        if (!state.activeConversation) {
            newConversation();
        }

        const conv = state.conversations.find(c => c.id === state.activeConversation);
        if (!conv) return;

        // Add user message
        conv.messages.push({ role: 'user', content: text, timestamp: Date.now() });

        // Update title from first message
        if (conv.messages.filter(m => m.role === 'user').length === 1) {
            conv.title = text.substring(0, 60) + (text.length > 60 ? '...' : '');
        }

        input.value = '';
        input.style.height = 'auto';
        renderChatMessages();
        renderConversationsList();
        scrollToBottom();

        // Show typing indicator
        state.sendInProgress = true;
        showTypingIndicator();

        const model = $('#modelSelect').value;
        const strategy = $('#strategySelect').value;
        const specialty = $('#specialtySelect').value;
        const multiMode = $('#multiModeSelect').value;

        // Decide which endpoint to use
        let result;
        if (multiMode !== 'single' || specialty) {
            // Use /api/multi for multi-model or specialty-based queries
            result = await api.sendMulti(text, {
                model: model !== 'auto' ? model : undefined,
                specialty: specialty || undefined,
                mode: multiMode,
                strategy: strategy,
            });
        } else {
            // Use /api/chat for single-model queries
            result = await api.sendChat(text, model, strategy, privacy);
        }

        state.sendInProgress = false;
        removeTypingIndicator();

        // Add assistant message
        conv.messages.push({
            role: 'assistant',
            content: result.response || t('chat.noResponse'),
            model: result.model || model,
            source: result.source || 'local',
            models_used: result.models_used || [],
            mode: result.mode || null,
            specialty: result.specialty || result.specialist_routing?.detected_specialties?.map(s => s[0]).join(', ') || null,
            confidence: result.confidence || null,
            tokens: result.tokens_used || 0,
            timestamp: Date.now(),
        });

        renderChatMessages();
        saveConversationsToStorage();
        scrollToBottom();
    }

    function renderChatMessages() {
        const container = $('#chatMessages');
        const conv = state.conversations.find(c => c.id === state.activeConversation);

        if (!conv || conv.messages.length === 0) {
            container.innerHTML = `
                <div class="chat-welcome">
                    <div class="welcome-icon">🧠</div>
                    <h2>${PinkyBrainAPI.sanitize(t('chat.welcomeTitle'))}</h2>
                    <p>${PinkyBrainAPI.sanitize(t('chat.welcomeText'))}</p>
                </div>`;
            return;
        }

        container.innerHTML = conv.messages.map(msg => {
            if (msg.role === 'user') {
                return `<div class="msg user">${PinkyBrainAPI.sanitize(msg.content)}</div>`;
            } else {
                const meta = [];
                if (msg.model) meta.push(msg.model);
                if (msg.source) meta.push(msg.source === 'local' ? t('chat.local') : msg.source);
                if (msg.specialty) meta.push(`🎯 ${msg.specialty}`);
                if (msg.mode && msg.mode !== 'single') meta.push(`🔀 ${msg.mode}`);
                if (msg.models_used && msg.models_used.length > 1) meta.push(`${msg.models_used.length} modèles`);
                if (msg.confidence) meta.push(`${Math.round(msg.confidence * 100)}%`);
                if (msg.tokens) meta.push(t('chat.tokens', { n: msg.tokens }));
                
                // Format multi-model responses
                let content = PinkyBrainAPI.renderMarkdown(msg.content);
                if (msg.responses && Object.keys(msg.responses).length > 1) {
                    // Show individual model responses in compare/fuse mode
                    const responsesHtml = Object.entries(msg.responses).map(([model, resp]) => {
                        const shortName = model.split(':')[0].split('/').pop();
                        return `<div class="multi-response">
                            <div class="multi-response-header">🤖 ${PinkyBrainAPI.sanitize(shortName)}</div>
                            <div class="multi-response-body">${PinkyBrainAPI.renderMarkdown(resp)}</div>
                        </div>`;
                    }).join('\n');
                    content = responsesHtml;
                }
                
                return `<div class="msg assistant">
                    ${content}
                    ${meta.length ? `<div class="msg-meta">${PinkyBrainAPI.sanitize(meta.join(' | '))}</div>` : ''}
                </div>`;
            }
        }).join('');
    }

    function showTypingIndicator() {
        const container = $('#chatMessages');
        const div = document.createElement('div');
        div.className = 'msg typing';
        div.id = 'typingIndicator';
        div.innerHTML = '<div class="typing-dots"><span>●</span><span>●</span><span>●</span></div>';
        container.appendChild(div);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        const el = $('#typingIndicator');
        if (el) el.remove();
    }

    function scrollToBottom() {
        const container = $('#chatMessages');
        requestAnimationFrame(() => {
            container.scrollTop = container.scrollHeight;
        });
    }

    // ─── Conversations List (sidebar) ──────────────────────

    function renderConversationsList() {
        const list = $('#conversationsList');
        if (!state.conversations.length) {
            list.innerHTML = `<div style="color:var(--text-muted);font-size:0.8rem;padding:4px 8px;">${t('sidebar.noConversation')}</div>`;
            return;
        }

        list.innerHTML = state.conversations.map(conv => {
            const isActive = conv.id === state.activeConversation;
            const timeStr = formatTime(conv.created);
            return `<div class="conv-item ${isActive ? 'active' : ''}" data-id="${PinkyBrainAPI.sanitize(conv.id)}">
                <span class="conv-icon">📝</span>
                <span class="conv-title">${PinkyBrainAPI.sanitize(conv.title)}</span>
                <span class="conv-time">${PinkyBrainAPI.sanitize(timeStr)}</span>
                <span class="conv-delete" data-delete="${PinkyBrainAPI.sanitize(conv.id)}" title="${t('chat.deleteConversation')}">✕</span>
            </div>`;
        }).join('');

        // Click handlers
        list.querySelectorAll('.conv-item').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.classList.contains('conv-delete')) {
                    deleteConversation(e.target.dataset.delete);
                } else {
                    selectConversation(el.dataset.id);
                }
            });
        });
    }

    // ─── Models (sidebar + share tab) ──────────────────────

    function renderModelsList() {
        const list = $('#modelsList');
        if (!state.models.length) {
            list.innerHTML = `<div style="color:var(--text-muted);font-size:0.8rem;">${t('sidebar.noModels')}</div>`;
            return;
        }

        list.innerHTML = state.models.map(m => {
            const isLocal = m.source === 'local' || !m.source;
            const dotClass = isLocal ? 'local' : (m.available ? 'mesh' : 'offline');
            const latency = m.latency ? `${m.latency}ms` : '';
            return `<div class="model-item">
                <span class="model-dot ${dotClass}"></span>
                <span class="model-name">${PinkyBrainAPI.sanitize(m.name || m)}</span>
                ${latency ? `<span class="model-latency">${PinkyBrainAPI.sanitize(latency)}</span>` : ''}
            </div>`;
        }).join('');
    }

    function updateModelSelect() {
        const select = $('#modelSelect');
        const current = select.value;
        select.innerHTML = `<option value="auto">${t('chat.modelAuto')}</option>`;
        state.models.forEach(m => {
            const name = m.name || m;
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        });
        select.value = current || 'auto';
    }

    function renderModelsShareList() {
        const list = $('#modelsShareList');
        if (!state.models.length) {
            list.innerHTML = `<div style="color:var(--text-muted);font-size:0.85rem;">${t('share.noModels')}</div>`;
            return;
        }

        list.innerHTML = state.models.map(m => {
            const name = m.name || m;
            const shared = m.shared || false;
            const size = m.size_mb ? `${m.size_mb} MB` : '';
            return `<div class="model-share-item">
                <span class="model-dot ${shared ? 'local' : 'offline'}"></span>
                <span class="model-share-name">${PinkyBrainAPI.sanitize(name)}</span>
                ${size ? `<span class="model-share-size">${PinkyBrainAPI.sanitize(size)}</span>` : ''}
                <span class="model-share-status ${shared ? 'shared' : 'not-shared'}">${shared ? t('share.shared') : t('share.notShared')}</span>
                <button class="btn btn-sm ${shared ? 'btn-danger' : 'btn-primary'}"
                        data-model="${PinkyBrainAPI.sanitize(name)}"
                        data-action="${shared ? 'unshare' : 'share'}">
                    ${shared ? t('share.stop') : t('share.share')}
                </button>
            </div>`;
        }).join('');

        // Bind share/unshare buttons
        list.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', async () => {
                const model = btn.dataset.model;
                const action = btn.dataset.action;
                if (action === 'share') {
                    const ok = await api.shareModel(model);
                    showToast(ok ? t('share.modelShared', { model }) : t('share.modelShareError', { model }), ok ? 'success' : 'error');
                } else {
                    const ok = await api.unshareModel(model);
                    showToast(ok ? t('share.modelStopped', { model }) : t('share.modelStopError', { model }), ok ? 'success' : 'error');
                }
                refreshAll();
            });
        });
    }

    // ─── Share Tab ─────────────────────────────────────────

    function setupShare() {
        const cpuSlider = $('#cpuSlider');
        const ramSlider = $('#ramSlider');
        const bwSlider = $('#bwSlider');
        const dataSlider = $('#dataSlider');
        const gpuToggle = $('#gpuToggle');

        // CPU: 5-70%, chaque ressource est indépendante
        cpuSlider?.addEventListener('input', () => {
            const v = parseInt(cpuSlider.value);
            $('#cpuValue').textContent = v === 70 ? `${v}% (max)` : `${v}%`;
            $('#cpuMax').textContent = `${v}%`;
        });

        // RAM: 128MB-70% du total, chaque ressource est indépendante
        ramSlider?.addEventListener('input', () => {
            const mb = parseInt(ramSlider.value);
            const gb = (mb / 1024).toFixed(1);
            $('#ramValue').textContent = mb >= 1024 ? `${gb} GB` : `${mb} MB`;
            $('#ramMax').textContent = mb >= 1024 ? `${gb} GB` : `${mb} MB`;
        });

        // Bande passante: 0=illimité, chaque ressource est indépendante
        bwSlider?.addEventListener('input', () => {
            const kbps = parseInt(bwSlider.value);
            if (kbps === 0) {
                $('#bwValue').textContent = '∞ Illimité';
                $('#bwMax').textContent = '∞ Illimité';
            } else {
                const mbps = (kbps / 1000).toFixed(1);
                $('#bwValue').textContent = kbps >= 1000 ? `${mbps} Mbps` : `${kbps} Kbps`;
                $('#bwMax').textContent = kbps >= 1000 ? `${mbps} Mbps` : `${kbps} Kbps`;
            }
        });

        // Données/mois: 0=illimité, chaque ressource est indépendante
        dataSlider?.addEventListener('input', () => {
            const gb = parseInt(dataSlider.value);
            if (gb === 0) {
                $('#dataValue').textContent = '∞ Illimité';
            } else if (gb >= 1024) {
                const tb = (gb / 1024).toFixed(1);
                $('#dataValue').textContent = `${tb} TB`;
            } else {
                $('#dataValue').textContent = `${gb} GB`;
            }
        });

        $('#resumeShareBtn')?.addEventListener('click', () => {
            showToast(t('share.resumeShareToast'), 'info');
        });

        // Save each resource independently on slider release (change event)
        cpuSlider?.addEventListener('change', () => saveResource('cpu'));
        ramSlider?.addEventListener('change', () => saveResource('ram'));
        bwSlider?.addEventListener('change', () => saveResource('bandwidth'));
        dataSlider?.addEventListener('change', () => saveResource('bandwidth'));
        $('#periodSelect')?.addEventListener('change', () => saveResource('bandwidth'));
        gpuToggle?.addEventListener('change', () => saveResource('gpu'));
    }

    function updateCapabilities(caps) {
        if (!caps) return;
        if (caps.cpu_cores) {
            // Update CPU info
        }
        if (caps.ram_total_mb) {
            const ramMax = Math.floor(caps.ram_total_mb * 0.70);  // 70% hard cap
            if ($('#ramSlider')) {
                $('#ramSlider').max = ramMax;
            }
        }
    }

    // Load bandwidth quota status from API
    async function loadBandwidthQuota() {
        try {
            const resp = await fetch('/api/bandwidth');
            if (!resp.ok) return;
            const bq = await resp.json();

            // Update data slider
            const dataSlider = $('#dataSlider');
            if (dataSlider && bq.monthly_data_gb !== undefined) {
                dataSlider.value = bq.monthly_data_gb;
                if (bq.monthly_data_gb === 0) {
                    $('#dataValue').textContent = '∞ Illimité';
                } else {
                    $('#dataValue').textContent = `${bq.monthly_data_gb} GB`;
                }
            }

            // Update period select
            const periodSelect = $('#periodSelect');
            if (periodSelect && bq.period) {
                periodSelect.value = bq.period;
            }

            // Update data reset info
            if (bq.period_end) {
                const resetDate = new Date(bq.period_end * 1000);
                const resetStr = resetDate.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
                const dataReset = $('#dataReset');
                if (dataReset) dataReset.textContent = resetStr;
            }

            // Update bandwidth slider
            const bwSlider = $('#bwSlider');
            if (bwSlider && bq.bandwidth_limit_kbps !== undefined) {
                bwSlider.value = bq.bandwidth_limit_kbps;
                if (bq.bandwidth_limit_kbps === 0) {
                    $('#bwValue').textContent = '∞ Illimité';
                    $('#bwMax').textContent = '∞ Illimité';
                }
            }
        } catch (e) {
            // API not available yet
        }
    }

    // ─── Resource Save Handlers (chaque ressource est indépendante) ──────

    function saveResource(type) {
        const token = localStorage.getItem('ub_token') || '';
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        if (type === 'cpu') {
            const val = parseInt($('#cpuSlider')?.value || 10);
            fetch('/api/resources/config', { method: 'POST', headers, body: JSON.stringify({ max_cpu_percent: val }) })
                .then(r => r.json()).then(d => showToast(`💾 CPU → ${val}%`, 'success')).catch(e => showToast('Erreur CPU', 'error'));
        } else if (type === 'ram') {
            const val = parseInt($('#ramSlider')?.value || 256);
            fetch('/api/resources/config', { method: 'POST', headers, body: JSON.stringify({ max_ram_share_mb: val }) })
                .then(r => r.json()).then(d => showToast(`💾 RAM → ${val >= 1024 ? (val/1024).toFixed(1)+' GB' : val+' MB'}`, 'success')).catch(e => showToast('Erreur RAM', 'error'));
        } else if (type === 'gpu') {
            const val = $('#gpuToggle')?.checked || false;
            fetch('/api/resources/config', { method: 'POST', headers, body: JSON.stringify({ gpu_share: val }) })
                .then(r => r.json()).then(d => showToast(`💾 GPU → ${val ? '✅' : '❌'}`, 'success')).catch(e => showToast('Erreur GPU', 'error'));
        } else if (type === 'bandwidth') {
            const bwKbps = parseInt($('#bwSlider')?.value || 5000);
            const dataGb = parseInt($('#dataSlider')?.value || 5);
            const period = $('#periodSelect')?.value || 'monthly';
            fetch('/api/bandwidth', { method: 'POST', headers, body: JSON.stringify({ bandwidth_limit_kbps: bwKbps, monthly_data_gb: dataGb, quota_period: period }) })
                .then(r => r.json()).then(d => {
                    const bwStr = bwKbps === 0 ? '∞ Illimité' : (bwKbps >= 1000 ? `${(bwKbps/1000).toFixed(1)} Mbps` : `${bwKbps} Kbps`);
                    const dataStr = dataGb === 0 ? '∞ Illimité' : `${dataGb} GB`;
                    showToast(`💾 Bande passante → ${bwStr}, Données → ${dataStr}/${period}`, 'success');
                }).catch(e => showToast('Erreur bande passante', 'error'));
        }
    }

    // ─── Network Tab ───────────────────────────────────────

    function setupNetwork() {
        $('#refreshMeshBtn')?.addEventListener('click', refreshAll);
        $('#addPeerBtn')?.addEventListener('click', () => showAddPeerModal());
        $('#genInviteBtn')?.addEventListener('click', () => showInviteModal());
        $('#joinMeshBtn')?.addEventListener('click', () => showToast(t('network.joinMeshSoon'), 'info'));
        $('#leaveMeshBtn')?.addEventListener('click', () => showToast(t('network.leaveMeshSoon'), 'info'));
    }

    function renderNetworkPeers() {
        // Private peers
        const privateList = $('#privatePeersList');
        const privatePeers = state.peers.filter(p => p.source !== 'mesh');
        $('#privatePeerCount').textContent = privatePeers.length;

        if (!privatePeers.length) {
            privateList.innerHTML = `<div style="color:var(--text-muted);font-size:0.85rem;">${t('network.noPrivatePeers')}</div>`;
        } else {
            privateList.innerHTML = privatePeers.map(p => `
                <div class="peer-card">
                    <div class="peer-name">
                        <span class="status-indicator online" style="width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;"></span>
                        ${PinkyBrainAPI.sanitize(p.name || p.host)}
                    </div>
                    <div class="peer-status">
                        ${PinkyBrainAPI.sanitize(p.host)}:${PinkyBrainAPI.sanitize(String(p.port || 8081))}
                        ${p.latency ? ` · ${PinkyBrainAPI.sanitize(String(Math.round(p.latency)))}ms` : ''}
                    </div>
                </div>`).join('');
        }

        // Mesh nodes (from discovery)
        const meshList = $('#meshNodesList');
        const meshNodes = state.peers.filter(p => p.source === 'mesh' || p.source === 'discovery');
        const meshSubtitle = $('#meshSubtitle');

        if (meshNodes.length) {
            meshSubtitle.textContent = t('network.meshNodes', { count: meshNodes.length });
            $('#joinMeshBtn').style.display = 'none';
            $('#leaveMeshBtn').style.display = 'inline-flex';

            meshList.innerHTML = meshNodes.map(n => `
                <div class="mesh-node-card">
                    <div class="node-name">${PinkyBrainAPI.sanitize(n.name || t('network.unknownNode'))}</div>
                    <div class="node-info">
                        <span>${t('share.cpu')}: ${PinkyBrainAPI.sanitize(String(n.capabilities?.cpu_cores || '?'))} ${t('network.cores')}</span>
                        <span>RAM: ${PinkyBrainAPI.sanitize(String(n.capabilities?.ram_share_mb || '?'))} MB</span>
                        ${n.score ? `<span>${t('network.score')}: ${PinkyBrainAPI.sanitize(String(n.score))}</span>` : ''}
                        ${n.latency ? `<span>${t('network.latency')}: ${PinkyBrainAPI.sanitize(String(Math.round(n.latency)))}ms</span>` : ''}
                    </div>
                </div>`).join('');
        } else {
            meshSubtitle.textContent = t('network.meshDisabledNoNodes');
            meshList.innerHTML = `<div style="color:var(--text-muted);font-size:0.85rem;">${t('network.noMeshNodes')}</div>`;
            $('#joinMeshBtn').style.display = 'inline-flex';
            $('#leaveMeshBtn').style.display = 'none';
        }
    }

    function showAddPeerModal() {
        const modal = $('#modalOverlay');
        const content = $('#modalContent');
        content.innerHTML = `
            <h3>${t('network.addPeerTitle')}</h3>
            <div class="form-group">
                <label>${t('network.name')}</label>
                <input type="text" id="modalPeerName" placeholder="${t('network.namePlaceholder')}">
            </div>
            <div class="form-group">
                <label>${t('network.ipAddress')}</label>
                <input type="text" id="modalPeerHost" placeholder="${t('network.ipPlaceholder')}">
            </div>
            <div class="form-group">
                <label>${t('network.port')}</label>
                <input type="text" id="modalPeerPort" value="8081">
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="modalCancelBtn">${t('network.cancel')}</button>
                <button class="btn btn-primary" id="modalAddPeerConfirm">${t('network.add')}</button>
            </div>`;
        modal.style.display = 'flex';

        $('#modalCancelBtn').addEventListener('click', () => { modal.style.display = 'none'; });
        $('#modalAddPeerConfirm').addEventListener('click', () => {
            const name = $('#modalPeerName').value.trim();
            const host = $('#modalPeerHost').value.trim();
            const port = parseInt($('#modalPeerPort').value) || 8081;
            if (!host) { showToast(t('network.ipRequired'), 'error'); return; }
            showToast(t('network.peerAdded', { name: name || host }), 'info');
            modal.style.display = 'none';
        });
    }

    function showInviteModal() {
        const modal = $('#modalOverlay');
        const content = $('#modalContent');
        const inviteCode = btoa(JSON.stringify({ node: state.status?.node_name || 'unknown', ts: Date.now() }));
        content.innerHTML = `
            <h3>${t('network.inviteTitle')}</h3>
            <p style="color:var(--text-secondary);margin-bottom:12px;font-size:0.9rem;">
                ${t('network.inviteText')}
            </p>
            <div style="background:var(--bg-input);padding:12px;border-radius:6px;font-family:var(--font-mono);word-break:break-all;font-size:0.85rem;">
                ${PinkyBrainAPI.sanitize(inviteCode)}
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="modalCopyBtn">${t('network.copy')}</button>
                <button class="btn btn-secondary" id="modalCloseBtn">${t('network.close')}</button>
            </div>`;
        modal.style.display = 'flex';

        $('#modalCopyBtn').addEventListener('click', () => {
            navigator.clipboard.writeText(inviteCode);
            modal.style.display = 'none';
        });
        $('#modalCloseBtn').addEventListener('click', () => { modal.style.display = 'none'; });
    }

    // ─── Config Tab ────────────────────────────────────────

    function setupConfig() {
        // Load config from status
        const loadConfig = async () => {
            const status = await api.getStatus();
            if (status) {
                const cfg = status.config || {};
                $('#cfgNodeName').value = cfg.node_name || status.node_name || '';
                $('#cfgP2PSecret').value = '••••••••••••';
                $('#cfgMeshEnabled').checked = cfg.public_mesh?.enabled || false;
                $('#cfgTracker').value = cfg.public_mesh?.tracker_url || 'https://tracker.pinkybrain.ai';
                $('#cfgPriority').value = cfg.public_mesh?.priority || 'local_first';
                $('#cfgStealth').checked = cfg.stealth_mode || false;
                $('#cfgAutoPause').checked = cfg.auto_pause !== false;
                $('#cfgDevMode').checked = cfg.dev_mode || false;
                $('#cfgPeerCount').textContent = state.peers.length;
            }
        };

        loadConfig();

        $('#toggleSecretBtn')?.addEventListener('click', () => {
            const input = $('#cfgP2PSecret');
            input.type = input.type === 'password' ? 'text' : 'password';
        });

        $('#saveConfigBtn')?.addEventListener('click', async () => {
            const config = {
                node_name: $('#cfgNodeName').value.trim(),
                public_mesh: {
                    enabled: $('#cfgMeshEnabled').checked,
                    tracker_url: $('#cfgTracker').value.trim(),
                    priority: $('#cfgPriority').value,
                },
                stealth_mode: $('#cfgStealth').checked,
            };
            const ok = await api.saveConfig(config);
            showToast(ok ? t('config.saved') : t('config.saveError'), ok ? 'success' : 'error');
        });

        $('#resetConfigBtn')?.addEventListener('click', () => {
            loadConfig();
            showToast(t('config.resetDone'), 'info');
        });

        // Language change
        $('#cfgLang')?.addEventListener('change', async (e) => {
            await i18n.setLocale(e.target.value);
            applyI18NToDOM();
            updateDynamicTexts();
            populateLangSelect();
        });

        // Theme toggle
        $('#cfgTheme')?.addEventListener('change', (e) => {
            document.body.classList.toggle('light-theme', e.target.value === 'light');
            localStorage.setItem('ub-theme', e.target.value);
        });

        // Apply saved theme
        const savedTheme = localStorage.getItem('ub-theme');
        if (savedTheme === 'light') {
            document.body.classList.add('light-theme');
            const themeSelect = $('#cfgTheme');
            if (themeSelect) themeSelect.value = 'light';
        }
    }

    /** Update all dynamic text that's generated in JS (not data-i18n in HTML) */
    function updateDynamicTexts() {
        updateHeader(state.connected ? state.status : null);
        renderConversationsList();
        renderModelsList();
        renderModelsShareList();
        renderChatMessages();
        renderNetworkPeers();
        updateModelSelect();
        loadModelNetworks();

        // Update tab buttons
        const tabBtns = $$('.tab-btn');
        const tabKeys = ['chat', 'share', 'network', 'config'];
        tabBtns.forEach((btn, i) => {
            if (tabKeys[i]) btn.textContent = t(`tabs.${tabKeys[i]}`);
        });

        // Update sidebar titles
        const sidebarTitles = $$('.sidebar-title');
        const sidebarKeys = ['sidebar.conversations', 'sidebar.models'];
        sidebarTitles.forEach((el, i) => {
            if (sidebarKeys[i]) el.textContent = t(sidebarKeys[i]);
        });

        // Update button text
        const newConvBtn = $('#newConvBtn');
        if (newConvBtn) newConvBtn.textContent = t('sidebar.newConversation');

        // Chat input placeholder
        const chatInput = $('#chatInput');
        if (chatInput) chatInput.placeholder = t('chat.placeholder');

        // Send button title
        const sendBtn = $('#sendBtn');
        if (sendBtn) sendBtn.title = t('chat.sendTitle');

        // Select titles
        const modelSelect = $('#modelSelect');
        if (modelSelect) modelSelect.title = t('chat.modelSelect');
        const strategySelect = $('#strategySelect');
        if (strategySelect) {
            strategySelect.title = t('chat.strategySelect');
            // Update strategy option texts
            const stratOpts = strategySelect.querySelectorAll('option');
            const stratKeys = ['chat.strategyAuto', 'chat.strategyLocal', 'chat.strategyPeer', 'chat.strategyConsensus'];
            stratOpts.forEach((opt, i) => { if (stratKeys[i]) opt.textContent = t(stratKeys[i]); });
        }
        const privacySelect = $('#privacySelect');
        if (privacySelect) {
            privacySelect.title = t('chat.privacySelect');
            const privOpts = privacySelect.querySelectorAll('option');
            const privKeys = ['chat.privacyPrivate', 'chat.privacySynced'];
            privOpts.forEach((opt, i) => { if (privKeys[i]) opt.textContent = t(privKeys[i]); });
        }

        // Section headings in share tab
        const shareH3s = $$('#tab-share h3');
        const shareKeys = ['share.sharedResources', 'share.sharedModels', 'share.statistics'];
        shareH3s.forEach((el, i) => { if (shareKeys[i]) el.textContent = t(shareKeys[i]); });

        // Section headings in network tab
        const netH3s = $$('#tab-network h3');
        const netKeys = ['network.privateNetwork', 'network.publicMesh', 'network.isolation'];
        netH3s.forEach((el, i) => { if (netKeys[i]) el.textContent = t(netKeys[i]); });

        // Section headings in config tab
        const cfgH3s = $$('#tab-config h3');
        const cfgKeys = ['config.general', 'config.privateNetwork', 'config.publicMesh', 'config.storage', 'config.advanced'];
        cfgH3s.forEach((el, i) => { if (cfgKeys[i]) el.textContent = t(cfgKeys[i]); });

        // Config labels
        const cfgNodeNameLabel = document.querySelector('label[for="cfgNodeName"]');
        if (cfgNodeNameLabel) cfgNodeNameLabel.textContent = t('config.nodeName');
        const cfgNodeNameInput = $('#cfgNodeName');
        if (cfgNodeNameInput) cfgNodeNameInput.placeholder = t('config.nodeNamePlaceholder');
        const cfgLangLabel = $('#cfgLangLabel');
        if (cfgLangLabel) cfgLangLabel.textContent = t('config.language');
        const cfgThemeLabel = document.querySelector('label[for="cfgTheme"]');
        if (cfgThemeLabel) cfgThemeLabel.textContent = t('config.theme');

        // Theme options
        const themeSelect = $('#cfgTheme');
        if (themeSelect) {
            const themeOpts = themeSelect.querySelectorAll('option');
            const themeKeys = ['config.themeDark', 'config.themeLight'];
            themeOpts.forEach((opt, i) => { if (themeKeys[i]) opt.textContent = t(themeKeys[i]); });
        }

        // Config button texts
        const saveBtn = $('#saveConfigBtn');
        if (saveBtn) saveBtn.textContent = t('config.save');
        const resetBtn = $('#resetConfigBtn');
        if (resetBtn) resetBtn.textContent = t('config.reset');

        // Share paused text
        const sharePaused = $('#sharePaused');
        if (sharePaused) {
            // First child is text node, then button
            const textNode = sharePaused.childNodes[0];
            if (textNode && textNode.nodeType === 3) {
                textNode.textContent = t('share.sharePaused');
            }
        }
        const resumeBtn = $('#resumeShareBtn');
        if (resumeBtn) resumeBtn.textContent = t('share.resumeShare');

        // Network buttons
        const addPeerBtn = $('#addPeerBtn');
        if (addPeerBtn) addPeerBtn.textContent = t('network.addPeer');
        const genInviteBtn = $('#genInviteBtn');
        if (genInviteBtn) genInviteBtn.textContent = t('network.generateInvite');
        const joinMeshBtn = $('#joinMeshBtn');
        if (joinMeshBtn) joinMeshBtn.textContent = t('network.joinMesh');
        const leaveMeshBtn = $('#leaveMeshBtn');
        if (leaveMeshBtn) leaveMeshBtn.textContent = t('network.leaveMesh');
        const refreshMeshBtn = $('#refreshMeshBtn');
        if (refreshMeshBtn) refreshMeshBtn.textContent = t('network.refresh');

        // Toggle labels in config
        const toggleLabels = $$('#tab-config .toggle-label span:last-child');
        const toggleKeys = ['config.enableMesh', 'config.stealthMode', 'config.autoPause', 'config.encryptConversations', 'config.devMode'];
        // Also the share GPU toggle
        const gpuToggleLabel = document.querySelector('#tab-share .toggle-label span:last-child');

        // We need to be more careful with toggle label mapping
        // Config toggles: meshEnabled, stealth, autoPause, encryptConversations, devMode
        const cfgToggles = $$('#tab-config .toggle-label');
        if (cfgToggles[0]) cfgToggles[0].querySelector('span:last-child').textContent = t('config.enableMesh');
        if (cfgToggles[1]) cfgToggles[1].querySelector('span:last-child').textContent = t('config.stealthMode');
        if (cfgToggles[2]) cfgToggles[2].querySelector('span:last-child').textContent = t('config.autoPause');
        if (cfgToggles[3]) cfgToggles[3].querySelector('span:last-child').textContent = t('config.encryptConversations');
        if (cfgToggles[4]) cfgToggles[4].querySelector('span:last-child').textContent = t('config.devMode');

        // GPU toggle in share tab
        if (gpuToggleLabel) gpuToggleLabel.textContent = t('share.shareGpu');
        const gpuHint = $('#tab-share .toggle-hint');
        if (gpuHint) gpuHint.textContent = t('share.shareGpuHint');

        // Stat labels
        const statLabels = $$('#tab-share .stat-label');
        const statKeys = ['share.contributionScore', 'share.queriesServed', 'share.publicQuota', 'share.uptime'];
        statLabels.forEach((el, i) => { if (statKeys[i]) el.textContent = t(statKeys[i]); });

        // Priority select options
        const prioritySelect = $('#cfgPriority');
        if (prioritySelect) {
            const pOpts = prioritySelect.querySelectorAll('option');
            const pKeys = ['config.priorityLocalFirst', 'config.priorityMeshFirst', 'config.priorityBalanced'];
            pOpts.forEach((opt, i) => { if (pKeys[i]) opt.textContent = t(pKeys[i]); });
        }

        // Isolation checks
        const checkItems = $$('#tab-network .check-item');
        const privatePort = $('#privatePort');
        if (checkItems[0] && privatePort) {
            checkItems[0].innerHTML = `✅ ${t('network.privatePort', { port: privatePort.textContent || '8081' })}`;
        }
        const meshPort = $('#meshPort');
        if (checkItems[1] && meshPort) {
            checkItems[1].innerHTML = `✅ ${t('network.meshPort', { port: meshPort.textContent || '8090' })}`;
        }
        const checkNoPrivateData = $('#checkNoPrivateData');
        if (checkNoPrivateData) checkNoPrivateData.innerHTML = `✅ ${t('network.noPrivateData')}`;
        const checkResourceGuard = $('#checkResourceGuard');
        if (checkResourceGuard) checkResourceGuard.innerHTML = `✅ ${t('network.resourceGuard')}`;

        // Form info: peers connected
        const cfgPeerCountEl = $('#cfgPeerCount');
        if (cfgPeerCountEl) {
            const peerInfoEl = cfgPeerCountEl.parentElement;
            if (peerInfoEl) peerInfoEl.innerHTML = `${t('config.peersConnected', { count: state.peers.length })}`;
        }
    }

    // ─── Sidebar ───────────────────────────────────────────

    function setupSidebar() {
        // Conversation clicks are handled in renderConversationsList
    }

    // ─── Mobile ────────────────────────────────────────────

    function setupMobile() {
        const toggle = $('#sidebarToggle');
        const sidebar = $('#sidebar');

        toggle?.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
                if (!sidebar.contains(e.target) && e.target !== toggle) {
                    sidebar.classList.remove('open');
                }
            }
        });
    }

    // ─── WebSocket events ──────────────────────────────────

    api.on('ws_connected', () => {
        state.wsConnected = true;
        const dot = $('#statusDot');
        if (dot) dot.classList.add('connected');
    });

    api.on('ws_disconnected', () => {
        state.wsConnected = false;
        const dot = $('#statusDot');
        if (dot) dot.classList.remove('connected');
    });

    api.on('status_update', (data) => {
        state.status = data;
        updateHeader(data);
        updateSidebarStats(data);
    });

    api.on('peer_update', (data) => {
        if (data.peers) {
            state.peers = data.peers;
            renderNetworkPeers();
        }
    });

    // ─── localStorage ──────────────────────────────────────

    function saveConversationsToStorage() {
        try {
            const toSave = state.conversations.slice(0, 50).map(c => ({
                id: c.id,
                title: c.title?.substring(0, 200),
                messages: c.messages.slice(-100).map(m => ({
                    role: m.role,
                    content: m.content?.substring(0, 10000),
                    model: m.model,
                    source: m.source,
                    timestamp: m.timestamp,
                })),
                created: c.created,
                model: c.model,
            }));
            localStorage.setItem('ub_conversations', JSON.stringify(toSave));
        } catch (e) {
            console.warn('[UB] Cannot save conversations:', e);
        }
    }

    function loadConversationsFromStorage() {
        try {
            const saved = localStorage.getItem('ub_conversations');
            if (saved) {
                state.conversations = JSON.parse(saved);
                if (state.conversations.length > 0) {
                    state.activeConversation = state.conversations[0].id;
                }
            }
        } catch (e) {
            console.warn('[UB] Cannot load conversations:', e);
            state.conversations = [];
        }
    }

    // ─── Toast ─────────────────────────────────────────────

    function showToast(message, type = 'info') {
        const container = $('#toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = '0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ─── Utils ─────────────────────────────────────────────

    function formatTime(ts) {
        if (!ts) return '';
        const d = new Date(ts);
        const now = Date.now();
        const diff = now - ts;

        if (diff < 60000) return t('chat.justNow');
        if (diff < 3600000) return t('chat.minutesAgo', { n: Math.floor(diff / 60000) });
        if (diff < 86400000) return t('chat.hoursAgo', { n: Math.floor(diff / 3600000) });
        return d.toLocaleDateString(i18n.locale === 'en' ? 'en-US' : i18n.locale, { day: 'numeric', month: 'short' });
    }

    // ─── Model Networks (v5.2) ──────────────────────────────

    let modelNetworksData = {
        private_networks: [],
        model_permissions: {},
        local_models: []
    };

    async function loadModelNetworks() {
        try {
            const resp = await fetch('/api/model-networks', { headers: api.authHeaders() });
            if (!resp.ok) return;
            modelNetworksData = await resp.json();
            renderModelPermsTable();
            renderPrivateNetworksTable();
        } catch (e) {
            console.warn('Failed to load model networks:', e);
        }
    }

    function renderModelPermsTable() {
        const container = $('#modelPermsContainer');
        if (!container) return;

        const models = modelNetworksData.local_models || [];
        const networks = modelNetworksData.private_networks || [];
        const perms = modelNetworksData.model_permissions || {};

        if (models.length === 0) {
            container.innerHTML = '<div class="no-models-msg">Aucun modèle disponible</div>';
            return;
        }

        // Build table
        const netHeaders = networks.map(n =>
            `<th class="col-share-private">📤<br><span class="network-header">${PinkyBrainAPI.sanitize(n.name)}</span></th>\n<th class="col-use-private">📥<br><span class="network-header">${PinkyBrainAPI.sanitize(n.name)}</span></th>`
        ).join('\n');

        let rows = '';
        for (const model of models) {
            const p = perms[model] || {};
            const sharePriv = p.share_private || [];
            const usePriv = p.use_private || [];
            const sharePub = p.share_public || false;
            const usePub = p.use_public || false;

            let netCols = '';
            for (const net of networks) {
                const sid = `perm-${model}-share-private-${net.id}`;
                const uid = `perm-${model}-use-private-${net.id}`;
                netCols += `<td><input type="checkbox" id="${sid}" ${sharePriv.includes(net.id) ? 'checked' : ''}></td>\n<td><input type="checkbox" id="${uid}" ${usePriv.includes(net.id) ? 'checked' : ''}></td>`;
            }

            rows += `<tr>
                <td title="${PinkyBrainAPI.sanitize(model)}">${PinkyBrainAPI.sanitize(model)}</td>
                ${netCols}
                <td class="col-share-public"><input type="checkbox" id="perm-${model}-share-public" ${sharePub ? 'checked' : ''}></td>
                <td class="col-use-public"><input type="checkbox" id="perm-${model}-use-public" ${usePub ? 'checked' : ''}></td>
            </tr>`;
        }

        container.innerHTML = `
            <div class="model-perms-table-wrap">
                <table class="model-perms-table">
                    <thead>
                        <tr>
                            <th>🤖 Modèle</th>
                            ${netHeaders}
                            <th class="col-share-public">📤<br><span class="network-header">Public</span></th>
                            <th class="col-use-public">📥<br><span class="network-header">Public</span></th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    }

    function renderPrivateNetworksTable() {
        const container = $('#privateNetworksContainer');
        if (!container) return;

        const networks = modelNetworksData.private_networks || [];

        if (networks.length === 0) {
            container.innerHTML = '<div class="no-models-msg">Aucun réseau privé configuré</div>';
            return;
        }

        let rows = '';
        for (const net of networks) {
            const secretDisplay = net.secret ? '<code>••••••••</code>' : '<code style="color:var(--text-muted)">Non défini</code>';
            rows += `<tr data-network-id="${net.id}">
                <td style="text-align:center;font-weight:600;">#${net.id}</td>
                <td><input type="text" class="network-name-input" data-network-id="${net.id}" value="${PinkyBrainAPI.sanitize(net.name)}" placeholder="Nom du réseau"></td>
                <td>
                    <div class="secret-field">
                        ${secretDisplay}
                        <button class="btn-icon" data-action="generate-secret" data-network-id="${net.id}" title="Générer une nouvelle clé">🔑</button>
                        <button class="btn-icon" data-action="copy-secret" data-network-id="${net.id}" title="Copier la clé" style="display:none">📋</button>
                    </div>
                </td>
                <td><button class="btn-icon btn-danger" data-action="remove-network" data-network-id="${net.id}" title="Supprimer ce réseau">🗑️</button></td>
            </tr>`;
        }

        container.innerHTML = `
            <table class="private-networks-table">
                <thead>
                    <tr>
                        <th style="width:50px">#</th>
                        <th>Nom du réseau</th>
                        <th>Clé secrète</th>
                        <th style="width:40px"></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;

        // Bind network actions
        container.querySelectorAll('[data-action="generate-secret"]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const netId = parseInt(btn.dataset.networkId);
                await generateNetworkSecret(netId);
            });
        });

        container.querySelectorAll('[data-action="remove-network"]').forEach(btn => {
            btn.addEventListener('click', () => {
                const netId = parseInt(btn.dataset.networkId);
                removeNetwork(netId);
            });
        });
    }

    async function generateNetworkSecret(networkId) {
        try {
            const resp = await fetch(`/api/model-networks/${networkId}/generate-secret`, {
                method: 'POST',
                headers: api.authHeaders()
            });
            if (!resp.ok) {
                showToast('Erreur lors de la génération de la clé', 'error');
                return;
            }
            const data = await resp.json();
            // Show the secret once
            const secret = data.secret;
            const name = data.network_name;
            // Copy to clipboard
            try {
                await navigator.clipboard.writeText(secret);
                showToast(`🔑 Nouvelle clé pour « ${name} » copiée dans le presse-papier !`, 'success');
            } catch {
                // Fallback: show in a prompt
                prompt(`Clé pour le réseau « ${name} » — stockez-la en lieu sûr :`, secret);
            }
            // Reload to update UI
            await loadModelNetworks();
        } catch (e) {
            showToast('Erreur réseau', 'error');
        }
    }

    function removeNetwork(networkId) {
        modelNetworksData.private_networks = modelNetworksData.private_networks.filter(n => n.id !== networkId);
        // Also remove from model permissions
        for (const model of Object.keys(modelNetworksData.model_permissions)) {
            const p = modelNetworksData.model_permissions[model];
            if (p.share_private) p.share_private = p.share_private.filter(id => id !== networkId);
            if (p.use_private) p.use_private = p.use_private.filter(id => id !== networkId);
        }
        renderPrivateNetworksTable();
        renderModelPermsTable();
    }

    function addNetwork() {
        const ids = modelNetworksData.private_networks.map(n => n.id);
        const nextId = ids.length > 0 ? Math.max(...ids) + 1 : 1;
        modelNetworksData.private_networks.push({
            id: nextId,
            name: `Réseau ${nextId}`,
            secret: ''
        });
        renderPrivateNetworksTable();
        renderModelPermsTable();
    }

    function collectModelPermsFromUI() {
        const models = modelNetworksData.local_models || [];
        const networks = modelNetworksData.private_networks || [];
        const permissions = {};

        for (const model of models) {
            const perm = {
                share_private: [],
                use_private: [],
                share_public: false,
                use_public: false
            };
            for (const net of networks) {
                const shareEl = document.getElementById(`perm-${model}-share-private-${net.id}`);
                const useEl = document.getElementById(`perm-${model}-use-private-${net.id}`);
                if (shareEl && shareEl.checked) perm.share_private.push(net.id);
                if (useEl && useEl.checked) perm.use_private.push(net.id);
            }
            const sharePubEl = document.getElementById(`perm-${model}-share-public`);
            const usePubEl = document.getElementById(`perm-${model}-use-public`);
            if (sharePubEl) perm.share_public = sharePubEl.checked;
            if (usePubEl) perm.use_public = usePubEl.checked;
            permissions[model] = perm;
        }
        return permissions;
    }

    function collectPrivateNetworksFromUI() {
        const networks = [];
        document.querySelectorAll('.network-name-input').forEach(input => {
            const id = parseInt(input.dataset.networkId);
            const name = input.value.trim() || `Réseau ${id}`;
            // Find existing secret (preserve it)
            const existing = modelNetworksData.private_networks.find(n => n.id === id);
            networks.push({
                id: id,
                name: name,
                secret: existing ? existing.secret : ''
            });
        });
        return networks;
    }

    async function saveModelNetworks() {
        const statusEl = $('#saveNetworkStatus');
        if (statusEl) { statusEl.textContent = '⏳ Sauvegarde...'; statusEl.className = 'save-status'; }

        try {
            const networks = collectPrivateNetworksFromUI();
            const permissions = collectModelPermsFromUI();

            const resp = await fetch('/api/model-networks', {
                method: 'POST',
                headers: { ...api.authHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    private_networks: networks,
                    model_permissions: permissions
                })
            });

            if (!resp.ok) {
                const err = await resp.json();
                if (statusEl) { statusEl.textContent = `❌ ${err.error || 'Erreur'}`; statusEl.className = 'save-status error'; }
                return;
            }

            const data = await resp.json();
            modelNetworksData.private_networks = data.private_networks;
            modelNetworksData.model_permissions = data.model_permissions;
            renderModelPermsTable();
            renderPrivateNetworksTable();

            if (statusEl) { statusEl.textContent = '✅ Sauvegardé !'; statusEl.className = 'save-status success'; }
            showToast('Configuration des réseaux sauvegardée', 'success');
            setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 3000);
        } catch (e) {
            if (statusEl) { statusEl.textContent = '❌ Erreur réseau'; statusEl.className = 'save-status error'; }
            showToast('Erreur de sauvegarde', 'error');
        }
    }

    // Bind save button and add network button
    document.getElementById('saveNetworkConfigBtn')?.addEventListener('click', saveModelNetworks);
    document.getElementById('addNetworkBtn')?.addEventListener('click', addNetwork);

    // Load model networks on init
    loadModelNetworks();

    // ─── Close modal on overlay click ──────────────────────

    document.addEventListener('click', (e) => {
        if (e.target.id === 'modalOverlay') {
            e.target.style.display = 'none';
        }
    });

    // ─── Close modal on Escape ─────────────────────────────

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = $('#modalOverlay');
            if (modal && modal.style.display !== 'none') {
                modal.style.display = 'none';
            }
        }
    });

})();