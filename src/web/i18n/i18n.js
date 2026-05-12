/**
 * PinkyBrain — Internationalization (i18n) Module
 * Supports: fr (default), en, es, zh, hi, ar, pt, ja
 * RTL support for Arabic.
 */

const I18N_SUPPORTED = {
    fr: 'Français',
    en: 'English',
    es: 'Español',
    zh: '中文',
    hi: 'हिन्दी',
    ar: 'العربية',
    pt: 'Português (BR)',
    ja: '日本語',
};

const I18N_DEFAULT = 'fr';
const I18N_RTL_LANGS = new Set(['ar']);

class I18N {
    constructor() {
        this.locale = I18N_DEFAULT;
        this.translations = {};
        this._loaded = false;
    }

    /** Detect browser language and pick the best supported locale */
    detectLocale() {
        const browserLangs = navigator.languages || [navigator.language || navigator.userLanguage || ''];
        for (const bl of browserLangs) {
            const code = bl.split('-')[0].toLowerCase();
            if (I18N_SUPPORTED[code]) return code;
        }
        return I18N_DEFAULT;
    }

    /** Load a locale file. Returns a promise. */
    async loadLocale(locale) {
        if (!I18N_SUPPORTED[locale]) locale = I18N_DEFAULT;
        try {
            // Try relative path first (works when served from the web server)
            const url = `i18n/${locale}.json`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            this.translations[locale] = await resp.json();
        } catch (e) {
            console.warn(`[i18n] Failed to load locale "${locale}":`, e);
            // Fallback: if not the default, load default
            if (locale !== I18N_DEFAULT && !this.translations[I18N_DEFAULT]) {
                await this.loadLocale(I18N_DEFAULT);
            }
        }
    }

    /** Initialize: detect language, load translations, apply */
    async init() {
        // Check localStorage for saved preference
        const saved = localStorage.getItem('ub-locale');
        const locale = saved && I18N_SUPPORTED[saved] ? saved : this.detectLocale();

        await this.loadLocale(locale);
        // Always ensure default is loaded as fallback
        if (locale !== I18N_DEFAULT && !this.translations[I18N_DEFAULT]) {
            await this.loadLocale(I18N_DEFAULT);
        }

        this.locale = locale;
        this._loaded = true;
        this.applyDirection();
        this.updateHtmlLang();
        return locale;
    }

    /** Set locale, load if needed, save preference */
    async setLocale(locale) {
        if (!I18N_SUPPORTED[locale]) return;
        if (!this.translations[locale]) {
            await this.loadLocale(locale);
        }
        this.locale = locale;
        localStorage.setItem('ub-locale', locale);
        this.applyDirection();
        this.updateHtmlLang();
    }

    /** Get a translated string by dot-notation key, e.g. t('header.connected') */
    t(key, params) {
        const translation = this.translations[this.locale] || {};
        const defaultTranslation = this.translations[I18N_DEFAULT] || {};

        // Walk the key path
        const parts = key.split('.');
        let value = translation;
        for (const part of parts) {
            if (value && typeof value === 'object' && part in value) {
                value = value[part];
            } else {
                value = undefined;
                break;
            }
        }

        // Fallback to default locale
        if (value === undefined) {
            value = defaultTranslation;
            for (const part of parts) {
                if (value && typeof value === 'object' && part in value) {
                    value = value[part];
                } else {
                    value = key; // Last resort: return the key
                    break;
                }
            }
        }

        // If it's a string, interpolate params
        if (typeof value === 'string' && params) {
            return value.replace(/\{(\w+)\}/g, (_, k) => params[k] !== undefined ? params[k] : `{${k}}`);
        }

        return value || key;
    }

    /** Is the current locale RTL? */
    isRTL() {
        return I18N_RTL_LANGS.has(this.locale);
    }

    /** Apply direction to <html> and <body> */
    applyDirection() {
        const dir = this.isRTL() ? 'rtl' : 'ltr';
        document.documentElement.setAttribute('dir', dir);
        document.documentElement.style.direction = dir;
        // Toggle a class for CSS targeting
        document.body.classList.toggle('rtl', this.isRTL());
    }

    /** Update <html lang=...> */
    updateHtmlLang() {
        document.documentElement.setAttribute('lang', this.locale);
    }

    /** Get the list of supported locales for a language selector */
    getSupportedLocales() {
        return Object.entries(I18N_SUPPORTED).map(([code, name]) => ({
            code,
            name,
            active: code === this.locale,
        }));
    }
}

// Global instance
const i18n = new I18N();