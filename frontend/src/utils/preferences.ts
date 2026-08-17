import { z } from "zod";

export interface UiPreferences {
  language: "zh-CN" | "en-US";
  defaultCheckMode: "quick" | "standard" | "deep" | "continuous";
  reportFormat: "markdown" | "html";
  showTechnicalLogs: boolean;
  defaultBoundary: BoundaryDefaults;
}

export interface BoundaryDefaults {
  onlyPort: string;
  onlyHost: string;
  onlyPath: string;
  blockedHost: string;
  blockedPath: string;
  allowActions: string[];
  blockActions: string[];
}

const STORAGE_KEY = "vulnclaw.ui.preferences";
export const UI_PREFERENCES_EVENT = "vulnclaw.ui.preferences.updated";

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  language: "en-US",
  defaultCheckMode: "standard",
  reportFormat: "markdown",
  showTechnicalLogs: false,
  defaultBoundary: {
    onlyPort: "",
    onlyHost: "",
    onlyPath: "",
    blockedHost: "",
    blockedPath: "",
    allowActions: [],
    blockActions: [],
  },
};

/**
 * Boundary schema for the persisted preferences blob. Unknown/legacy shapes
 * fall back to defaults per field via `.catch`, so a corrupt localStorage entry
 * degrades gracefully instead of throwing.
 */
const boundaryDefaultsSchema = z.object({
  onlyPort: z.string().catch(""),
  onlyHost: z.string().catch(""),
  onlyPath: z.string().catch(""),
  blockedHost: z.string().catch(""),
  blockedPath: z.string().catch(""),
  allowActions: z.array(z.string()).catch([]),
  blockActions: z.array(z.string()).catch([]),
});

const uiPreferencesSchema = z.object({
  language: z.enum(["zh-CN", "en-US"]).catch(DEFAULT_UI_PREFERENCES.language),
  defaultCheckMode: z
    .enum(["quick", "standard", "deep", "continuous"])
    .catch(DEFAULT_UI_PREFERENCES.defaultCheckMode),
  reportFormat: z.enum(["markdown", "html"]).catch(DEFAULT_UI_PREFERENCES.reportFormat),
  showTechnicalLogs: z.boolean().catch(false),
  defaultBoundary: boundaryDefaultsSchema.catch(DEFAULT_UI_PREFERENCES.defaultBoundary),
});

export function loadUiPreferences(): UiPreferences {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_UI_PREFERENCES;
    const parsed = uiPreferencesSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : DEFAULT_UI_PREFERENCES;
  } catch {
    return DEFAULT_UI_PREFERENCES;
  }
}

export function saveUiPreferences(preferences: UiPreferences): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  window.dispatchEvent(new CustomEvent<UiPreferences>(UI_PREFERENCES_EVENT, { detail: preferences }));
}

export function subscribeUiPreferences(onChange: (preferences: UiPreferences) => void): () => void {
  const handleLocalUpdate = (event: Event) => {
    const detail = event instanceof CustomEvent ? uiPreferencesSchema.safeParse(event.detail) : null;
    onChange(detail?.success ? detail.data : loadUiPreferences());
  };
  const handleStorageUpdate = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) onChange(loadUiPreferences());
  };

  window.addEventListener(UI_PREFERENCES_EVENT, handleLocalUpdate);
  window.addEventListener("storage", handleStorageUpdate);

  return () => {
    window.removeEventListener(UI_PREFERENCES_EVENT, handleLocalUpdate);
    window.removeEventListener("storage", handleStorageUpdate);
  };
}
