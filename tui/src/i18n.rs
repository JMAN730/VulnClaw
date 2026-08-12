//! Minimal localization for the native LLM config panel.
//!
//! Language resolution mirrors the Python CLI (`vulnclaw.i18n.init_i18n`):
//! 1. Explicit override via `set_lang` / `init(Some(..))`
//! 2. Config `session.language` when exactly `zh` or `en` (not `auto`)
//! 3. `VULNCLAW_LANG` environment variable, exactly `zh` or `en`
//! 4. System `LANG` prefix (`zh*` / `en*`)
//! 5. Default English
//!
//! Only exact `zh`/`en` are honored for the explicit config/`VULNCLAW_LANG`
//! overrides so this panel never disagrees with the Python CLI, which matches
//! `VULNCLAW_LANG in ("zh", "en")` and treats unknown config values as English.
//!
//! **Missing-translation fallback:** active catalog → English catalog → key
//! string. English is the defined fallback language.

use std::cell::Cell;
use std::collections::HashMap;
use std::env;
use std::sync::{Mutex, OnceLock};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Lang {
    En,
    Zh,
}

impl Lang {
    /// Parse an explicit language override (config `session.language` or
    /// `VULNCLAW_LANG`).
    ///
    /// Only exact `zh`/`en` are accepted, mirroring the Python CLI: its
    /// `detect_language` matches `VULNCLAW_LANG` with `in ("zh", "en")`, and a
    /// config value like `zh-CN` resolves to a missing `zh-CN.json` and falls
    /// back to English. Accepting locale aliases (`zh-CN`, `en_US`, `zh-Hans`,
    /// …) here would make the native panel disagree with the rest of the CLI,
    /// so they intentionally fall through to `LANG`-prefix detection instead.
    pub fn parse(value: &str) -> Option<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "en" => Some(Lang::En),
            "zh" => Some(Lang::Zh),
            _ => None,
        }
    }
}

thread_local! {
    /// Per-thread language override so `cargo test` can run locales in parallel
    /// without races on the process-global default.
    static TLS_LANG: Cell<Option<Lang>> = const { Cell::new(None) };
}

fn global_lang() -> &'static Mutex<Lang> {
    static LANG: OnceLock<Mutex<Lang>> = OnceLock::new();
    LANG.get_or_init(|| Mutex::new(resolve_lang(None)))
}

/// Resolve UI language from optional config value + environment.
pub fn resolve_lang(config_language: Option<&str>) -> Lang {
    if let Some(lang) = config_language.and_then(Lang::parse) {
        return lang;
    }
    detect_language()
}

fn detect_language() -> Lang {
    if let Ok(value) = env::var("VULNCLAW_LANG") {
        if let Some(lang) = Lang::parse(&value) {
            return lang;
        }
    }
    if let Ok(value) = env::var("LANG") {
        let lower = value.to_ascii_lowercase();
        if lower.starts_with("zh") {
            return Lang::Zh;
        }
        if lower.starts_with("en") {
            return Lang::En;
        }
    }
    Lang::En
}

/// Apply language selection. Prefer an explicit/config value when provided.
pub fn init(config_language: Option<&str>) {
    set_lang(resolve_lang(config_language));
}

pub fn set_lang(lang: Lang) {
    TLS_LANG.with(|cell| cell.set(Some(lang)));
    if let Ok(mut guard) = global_lang().lock() {
        *guard = lang;
    }
}

pub fn current_lang() -> Lang {
    if let Some(lang) = TLS_LANG.with(|cell| cell.get()) {
        return lang;
    }
    global_lang()
        .lock()
        .map(|guard| *guard)
        .unwrap_or(Lang::En)
}

type Catalog = HashMap<&'static str, &'static str>;

fn en_catalog() -> Catalog {
    Catalog::from([
        ("tui.native_config.title", "Configure LLM"),
        (
            "tui.native_config.summary",
            "provider {provider}  url {url}  key {key}  model {model}",
        ),
        ("tui.native_config.label_provider", "Provider"),
        ("tui.native_config.label_base_url", "Base URL"),
        ("tui.native_config.label_api_key", "API key"),
        ("tui.native_config.label_model", "Model"),
        ("tui.native_config.label_actions", "Actions"),
        ("tui.native_config.choose", "choose"),
        ("tui.native_config.enter_to_edit", "Enter to edit"),
        ("tui.native_config.none", "(none)"),
        ("tui.native_config.fetch", "Fetch"),
        ("tui.native_config.save", "Save"),
        ("tui.native_config.suffix_loading", " (loading…)"),
        ("tui.native_config.suffix_disabled", " (disabled)"),
        (
            "tui.native_config.providers_hint",
            "Providers (Up/Down, Enter commits):",
        ),
        (
            "tui.native_config.models_hint",
            "Models (Up/Down, Enter commits):",
        ),
        (
            "tui.native_config.nav_hint",
            "Enter edit/select  ·  ↑/↓ navigate  ·  Tab/Shift+Tab move  ·  V/Ctrl+R reveal key  ·  Esc discard",
        ),
        (
            "tui.native_config.fetch_idle",
            "Press Fetch to load models.",
        ),
        (
            "tui.native_config.fetch_requires",
            "Fetch requires a provider, URL, and API key.",
        ),
        (
            "tui.native_config.load_failed",
            "Could not load LLM configuration.",
        ),
        (
            "tui.native_config.fetch_need_fields",
            "Enter a provider, URL, and API key before fetching.",
        ),
        ("tui.native_config.loading_models", "Loading models…"),
        (
            "tui.native_config.fetch_invalid",
            "Model fetch returned invalid data.",
        ),
        (
            "tui.native_config.api_key_empty",
            "API key cannot be empty.",
        ),
        (
            "tui.native_config.custom_need_url",
            "Custom providers require a base URL.",
        ),
        (
            "tui.native_config.url_warning",
            "Base URL may be malformed; press Save again to continue.",
        ),
        (
            "tui.native_config.saved",
            "Configuration saved: {provider}/{model}",
        ),
        (
            "tui.native_config.saved_cleared_pool",
            "Configuration saved: {provider}/{model} (cleared failover key pool so the new key is used)",
        ),
        (
            "tui.native_config.save_failed",
            "Could not save configuration.",
        ),
        (
            "tui.native_config.save_failed_with_error",
            "Could not save configuration: {error}",
        ),
        (
            "tui.native_config.discarded",
            "Configuration changes discarded.",
        ),
        (
            "tui.native_config.fetch_failed",
            "Could not fetch models; enter a model manually.",
        ),
        (
            "tui.native_config.fetch_failed_with_error",
            "Could not fetch models; enter a model manually. {error}",
        ),
        (
            "tui.native_config.no_models",
            "No models returned; enter a model manually.",
        ),
        (
            "tui.native_config.models_loaded",
            "Loaded {count} model(s). Select a model or type one manually.",
        ),
        // EN-only sentinel used to verify Chinese falls back to English.
        ("tui.native_config.__en_only__", "english-only-fallback"),
    ])
}

fn zh_catalog() -> Catalog {
    Catalog::from([
        ("tui.native_config.title", "配置 LLM"),
        (
            "tui.native_config.summary",
            "提供商 {provider}  地址 {url}  密钥 {key}  模型 {model}",
        ),
        ("tui.native_config.label_provider", "提供商"),
        ("tui.native_config.label_base_url", "Base URL"),
        ("tui.native_config.label_api_key", "API 密钥"),
        ("tui.native_config.label_model", "模型"),
        ("tui.native_config.label_actions", "操作"),
        ("tui.native_config.choose", "选择"),
        ("tui.native_config.enter_to_edit", "回车编辑"),
        ("tui.native_config.none", "(无)"),
        ("tui.native_config.fetch", "拉取"),
        ("tui.native_config.save", "保存"),
        ("tui.native_config.suffix_loading", " (加载中…)"),
        ("tui.native_config.suffix_disabled", " (不可用)"),
        (
            "tui.native_config.providers_hint",
            "提供商（↑/↓，回车确认）：",
        ),
        (
            "tui.native_config.models_hint",
            "模型（↑/↓，回车确认）：",
        ),
        (
            "tui.native_config.nav_hint",
            "回车 编辑/选择  ·  ↑/↓ 导航  ·  Tab/Shift+Tab 切换  ·  V/Ctrl+R 显示密钥  ·  Esc 放弃",
        ),
        (
            "tui.native_config.fetch_idle",
            "按「拉取」加载模型。",
        ),
        (
            "tui.native_config.fetch_requires",
            "拉取需要提供商、URL 和 API 密钥。",
        ),
        (
            "tui.native_config.load_failed",
            "无法加载 LLM 配置。",
        ),
        (
            "tui.native_config.fetch_need_fields",
            "拉取前请填写提供商、URL 和 API 密钥。",
        ),
        ("tui.native_config.loading_models", "正在加载模型…"),
        (
            "tui.native_config.fetch_invalid",
            "模型拉取返回了无效数据。",
        ),
        (
            "tui.native_config.api_key_empty",
            "API 密钥不能为空。",
        ),
        (
            "tui.native_config.custom_need_url",
            "自定义提供商需要 Base URL。",
        ),
        (
            "tui.native_config.url_warning",
            "Base URL 可能格式不正确；再次按保存以继续。",
        ),
        (
            "tui.native_config.saved",
            "配置已保存：{provider}/{model}",
        ),
        (
            "tui.native_config.saved_cleared_pool",
            "配置已保存：{provider}/{model}（已清空故障转移密钥池，以便使用新密钥）",
        ),
        (
            "tui.native_config.save_failed",
            "无法保存配置。",
        ),
        (
            "tui.native_config.save_failed_with_error",
            "无法保存配置：{error}",
        ),
        (
            "tui.native_config.discarded",
            "已放弃配置更改。",
        ),
        (
            "tui.native_config.fetch_failed",
            "无法拉取模型；请手动输入模型。",
        ),
        (
            "tui.native_config.fetch_failed_with_error",
            "无法拉取模型；请手动输入模型。{error}",
        ),
        (
            "tui.native_config.no_models",
            "未返回模型；请手动输入模型。",
        ),
        (
            "tui.native_config.models_loaded",
            "已加载 {count} 个模型。请选择模型或手动输入。",
        ),
    ])
}

fn catalogs() -> &'static (Catalog, Catalog) {
    static CATALOGS: OnceLock<(Catalog, Catalog)> = OnceLock::new();
    CATALOGS.get_or_init(|| (en_catalog(), zh_catalog()))
}

fn lookup(lang: Lang, key: &str) -> Option<&'static str> {
    let (en, zh) = catalogs();
    match lang {
        Lang::En => en.get(key).copied(),
        Lang::Zh => zh.get(key).copied().or_else(|| en.get(key).copied()),
    }
}

/// Translate `key` for the active language with English fallback.
pub fn t(key: &str) -> String {
    lookup(current_lang(), key)
        .or_else(|| lookup(Lang::En, key))
        .unwrap_or(key)
        .to_owned()
}

/// Translate and replace `{name}` placeholders from `args`.
pub fn t_args(key: &str, args: &[(&str, &str)]) -> String {
    let mut text = t(key);
    for (name, value) in args {
        text = text.replace(&format!("{{{name}}}"), value);
    }
    text
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn english_and_chinese_strings_differ() {
        set_lang(Lang::En);
        let en_title = t("tui.native_config.title");
        set_lang(Lang::Zh);
        let zh_title = t("tui.native_config.title");
        assert_eq!(en_title, "Configure LLM");
        assert_eq!(zh_title, "配置 LLM");
        assert_ne!(en_title, zh_title);

        set_lang(Lang::En);
        assert!(t("tui.native_config.fetch_idle").contains("Fetch"));
        set_lang(Lang::Zh);
        assert!(t("tui.native_config.fetch_idle").contains("拉取"));
    }

    #[test]
    fn missing_key_returns_key_literal() {
        set_lang(Lang::Zh);
        assert_eq!(
            t("tui.native_config.__missing_key__"),
            "tui.native_config.__missing_key__"
        );
        set_lang(Lang::En);
        assert_eq!(
            t("tui.native_config.__missing_key__"),
            "tui.native_config.__missing_key__"
        );
    }

    #[test]
    fn missing_chinese_entry_falls_back_to_english() {
        set_lang(Lang::Zh);
        assert_eq!(t("tui.native_config.__en_only__"), "english-only-fallback");
    }

    #[test]
    fn placeholder_substitution_works_in_both_locales() {
        set_lang(Lang::En);
        assert_eq!(
            t_args(
                "tui.native_config.models_loaded",
                &[("count", "2")],
            ),
            "Loaded 2 model(s). Select a model or type one manually."
        );
        set_lang(Lang::Zh);
        assert_eq!(
            t_args(
                "tui.native_config.models_loaded",
                &[("count", "2")],
            ),
            "已加载 2 个模型。请选择模型或手动输入。"
        );
    }

    #[test]
    fn resolve_lang_honors_config_zh_and_en() {
        assert_eq!(resolve_lang(Some("zh")), Lang::Zh);
        assert_eq!(resolve_lang(Some("en")), Lang::En);
        assert!(matches!(
            resolve_lang(Some("auto")),
            Lang::En | Lang::Zh
        ));
    }

    #[test]
    fn parse_accepts_only_exact_zh_and_en() {
        // Exact values (case-insensitive, trimmed) mirror the Python CLI.
        assert_eq!(Lang::parse("zh"), Some(Lang::Zh));
        assert_eq!(Lang::parse(" EN "), Some(Lang::En));
        // Locale aliases are intentionally rejected here: the Python CLI would
        // treat them as English (missing `zh-CN.json`) or fall through to
        // `LANG`, so accepting them would desync the native panel.
        for alias in ["zh-CN", "zh_cn", "zh-Hans", "zh-TW", "en-US", "en_us", "fr"] {
            assert_eq!(Lang::parse(alias), None, "alias {alias} should not parse");
        }
    }
}
