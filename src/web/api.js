/**
 * PinkyBrain Desktop — API Client
 * Communicates with the backend via REST and WebSocket.
 * All inputs are sanitized before display. CSRF tokens are handled.
 */

const API_BASE = window.location.origin; // same origin = localhost only

class PinkyBrainAPI {
    constructor() {
        this.baseUrl = API_BASE;
        this.wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
        this.ws = null;
        this.wsReconnectInterval = 3000;
        this.wsListeners = new Map();
        this.csrfToken = null;
    }

    // ─── CSRF ───────────────────────────────────────────────

    async _fetchCsrf() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/csrf`, { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                this.csrfToken = data.token || null;
            }
        } catch (e) {
            // CSRF endpoint might not exist yet; continue without
            this.csrfToken = null;
        }
    }

    _headers(extra = {}) {
        const h = { 'Content-Type': 'application/json', ...extra };
        if (this.csrfToken) h['X-CSRF-Token'] = this.csrfToken;
        return h;
    }

    // ─── REST API ───────────────────────────────────────────

    async getStatus() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/status`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : null;
        } catch (e) { return null; }
    }

    async getPeers() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/peers`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : { peers: [] };
        } catch (e) { return { peers: [] }; }
    }

    async getModels() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/brain/models`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : { models: [] };
        } catch (e) { return { models: [] }; }
    }

    async sendChat(prompt, model = 'auto', strategy = 'auto', privacy = 'private') {
        const body = { prompt: prompt.substring(0, 50000), model, strategy, privacy };
        try {
            const resp = await fetch(`${this.baseUrl}/api/brain/query`, {
                method: 'POST',
                headers: this._headers(),
                credentials: 'same-origin',
                body: JSON.stringify(body),
            });
            return resp.ok ? await resp.json() : { response: `Erreur ${resp.status}`, error: true };
        } catch (e) {
            return { response: 'Connexion perdue. Réessayez.', error: true };
        }
    }

    /** Send a multi-model or specialty-based query */
    async sendMulti(prompt, options = {}) {
        const body = {
            prompt: prompt.substring(0, 50000),
            mode: options.mode || 'single',
        };
        if (options.model) body.models = [options.model];
        if (options.specialty) body.specialties = [options.specialty];
        if (options.strategy) body.strategy = options.strategy;
        try {
            const resp = await fetch(`${this.baseUrl}/api/multi`, {
                method: 'POST',
                headers: this._headers(),
                credentials: 'same-origin',
                body: JSON.stringify(body),
            });
            return resp.ok ? await resp.json() : { response: `Erreur ${resp.status}`, error: true };
        } catch (e) {
            return { response: 'Connexion perdue.', error: true };
        }
    }

    /** Get available specialties */
    async getSpecialties() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/specialties`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : { specialties: {} };
        } catch (e) { return { specialties: {} }; }
    }

    /** Get models for a specialty */
    async getSpecialtyModels(specialtyName) {
        try {
            const resp = await fetch(`${this.baseUrl}/api/specialties/${encodeURIComponent(specialtyName)}/models`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : { models: [] };
        } catch (e) { return { models: [] }; }
    }

    async sendQuery(prompt, model = null) {
        const body = { prompt: prompt.substring(0, 50000) };
        if (model) body.model = model;
        try {
            const resp = await fetch(`${this.baseUrl}/api/query`, {
                method: 'POST',
                headers: this._headers(),
                credentials: 'same-origin',
                body: JSON.stringify(body),
            });
            return resp.ok ? await resp.json() : { response: `Erreur ${resp.status}`, error: true };
        } catch (e) {
            return { response: 'Connexion perdue.', error: true };
        }
    }

    async getResources() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/status`, { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                return data.resources || data || {};
            }
            return {};
        } catch (e) { return {}; }
    }

    async getConfig() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/status`, { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                return data.config || data || {};
            }
            return {};
        } catch (e) { return {}; }
    }

    async saveConfig(config) {
        try {
            const resp = await fetch(`${this.baseUrl}/api/config`, {
                method: 'POST',
                headers: this._headers(),
                credentials: 'same-origin',
                body: JSON.stringify(config),
            });
            return resp.ok;
        } catch (e) { return false; }
    }

    async shareModel(modelName) {
        try {
            const resp = await fetch(`${this.baseUrl}/api/models/${encodeURIComponent(modelName)}/share`, {
                method: 'POST',
                headers: this._headers(),
                credentials: 'same-origin',
            });
            return resp.ok;
        } catch (e) { return false; }
    }

    async unshareModel(modelName) {
        try {
            const resp = await fetch(`${this.baseUrl}/api/models/${encodeURIComponent(modelName)}/unshare`, {
                method: 'POST',
                headers: this._headers(),
                credentials: 'same-origin',
            });
            return resp.ok;
        } catch (e) { return false; }
    }

    async getCapabilities() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/capabilities`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : {};
        } catch (e) { return {}; }
    }

    async getQuota() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/quota`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : {};
        } catch (e) { return {}; }
    }

    async getDiscover() {
        try {
            const resp = await fetch(`${this.baseUrl}/api/discover`, { credentials: 'same-origin' });
            return resp.ok ? await resp.json() : {};
        } catch (e) { return {}; }
    }

    async getScore() {
        try {
            const status = await this.getStatus();
            return status?.score || 0;
        } catch (e) { return 0; }
    }

    // ─── WebSocket ─────────────────────────────────────────

    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

        try {
            this.ws = new WebSocket(this.wsUrl);

            this.ws.onopen = () => {
                console.log('[UB] WebSocket connecté');
                this._dispatch('ws_connected', {});
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._dispatch(data.type || 'ws_message', data);
                } catch (e) {
                    // non-JSON message, ignore
                }
            };

            this.ws.onclose = () => {
                console.log('[UB] WebSocket déconnecté, reconnexion...');
                this._dispatch('ws_disconnected', {});
                setTimeout(() => this.connectWebSocket(), this.wsReconnectInterval);
            };

            this.ws.onerror = () => {
                this.ws.close();
            };
        } catch (e) {
            setTimeout(() => this.connectWebSocket(), this.wsReconnectInterval);
        }
    }

    on(event, callback) {
        if (!this.wsListeners.has(event)) this.wsListeners.set(event, []);
        this.wsListeners.get(event).push(callback);
    }

    off(event, callback) {
        if (!this.wsListeners.has(event)) return;
        const cbs = this.wsListeners.get(event).filter(cb => cb !== callback);
        this.wsListeners.set(event, cbs);
    }

    _dispatch(event, data) {
        const cbs = this.wsListeners.get(event) || [];
        cbs.forEach(cb => { try { cb(data); } catch (e) { console.error('[UB] Listener error:', e); } });
        // Also dispatch to wildcard listeners
        const wildcards = this.wsListeners.get('*') || [];
        wildcards.forEach(cb => { try { cb(event, data); } catch (e) {} });
    }

    // ─── Helpers ───────────────────────────────────────────

    /**
     * Sanitize HTML to prevent XSS. Escapes &, <, >, ", '
     */
    static sanitize(str) {
        if (typeof str !== 'string') return String(str);
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return str.replace(/[&<>"']/g, c => map[c]);
    }

    /**
     * Simple markdown-like rendering for chat messages
     */
    static renderMarkdown(text) {
        if (!text) return '';
        let s = PinkyBrainAPI.sanitize(text);
        // Code blocks
        s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        // Inline code
        s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold
        s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Line breaks
        s = s.replace(/\n/g, '<br>');
        return s;
    }
}

// Global instance
const api = new PinkyBrainAPI();