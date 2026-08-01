"""THROWAWAY PROTOTYPE — config_panel layout/feel exploration. NOT production code.

Answers wayfinder ticket 04: lock row order + labels + interaction feel for the
VulnClaw /config keyboard-navigable settings panel (LLM settings only).

Three STRUCTURALLY DIFFERENT variants of the same config_panel, all mounted inside a
floating popup that mimics the real `SecondaryPopup` (amber border, same palette).
Flip between them with the bottom switcher bar: keys 1/2/3 or ←/→.

    python .scratch/config-panel/prototype/config_panel_prototype.py

Variant A — Stacked labeled rows (mirrors /scope action_matrix: label+control per line, live summary top)
Variant B — Two-column grid (label column | control column, action button row at bottom)
Variant C — Grouped sections (Collapsible "Connection" / "Model" groups, footer actions)

All three cover: provider Select, conditional base-URL row (custom only), masked API key +
reveal toggle, model Select with fetch-feedback states, Fetch action, Save action, top summary.
Fetch is FAKED (0.8s timer -> canned model list). No real config I/O. State is in-memory only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import (
    Button,
    Collapsible,
    Input,
    Label,
    Select,
    Static,
)

# palette lifted from tui_textual.py CSS
C_PRIMARY = "#fab283"
C_SUCCESS = "#7fd88f"
C_ERROR = "#e06c75"
C_MUTED = "#8a8a8a"
C_TEXT = "#eeeeee"

PROVIDERS = ["openai", "anthropic", "deepseek", "custom"]
FAKE_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    "anthropic": ["claude-fable-5", "claude-opus-4-8", "claude-haiku-4-5"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "custom": ["local-model-a", "local-model-b"],
}


@dataclass
class Draft:
    """In-memory edit draft. A real panel deep-copies live config; here it starts blank."""
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str | None = None
    models: list[str] = field(default_factory=list)   # fetched list, empty until Fetch
    fetch_state: str = "idle"                          # idle | loading | ok | fail
    revealed: bool = False

    @property
    def is_custom(self) -> bool:
        return self.provider == "custom"

    @property
    def can_fetch(self) -> bool:
        # gated on required fields (ticket 02): key always, base_url only when custom
        if not self.api_key:
            return False
        if self.is_custom and not self.base_url:
            return False
        return True

    def save_error(self) -> str | None:
        if not self.api_key:
            return "API key required."
        if self.is_custom and not self.base_url:
            return "Base URL required for custom provider."
        return None


def summary_line(d: Draft) -> str:
    key = "—" if not d.api_key else ("*" * min(len(d.api_key), 8))
    if d.revealed and d.api_key:
        key = d.api_key
    model = d.model or f"[{C_MUTED}](none — press Fetch)[/]"
    url = d.base_url if d.is_custom else "[dim](preset)[/]"
    return (
        f"[bold {C_PRIMARY}]{d.provider}[/]   "
        f"url [italic]{url}[/]   "
        f"key [italic]{key}[/]   "
        f"model {model}"
    )


def fetch_hint(d: Draft) -> str:
    return {
        "idle": f"[{C_MUTED}]press Fetch to load models[/]",
        "loading": f"[{C_PRIMARY}]⠿ fetching models…[/]",
        "ok": f"[{C_SUCCESS}]✓ {len(d.models)} models loaded[/]",
        "fail": f"[{C_ERROR}]✗ fetch failed — type model manually[/]",
    }[d.fetch_state]


# ── Shared behaviour mixin: each variant is a Vertical that renders `self.d` ──

class VariantBase(Vertical):
    """Common draft + fetch logic; subclasses own compose() + refresh()."""

    def __init__(self, d: Draft, **kw):
        super().__init__(**kw)
        self.d = d

    def on_mount(self) -> None:
        self.refresh_view()

    # -- fetch simulation --
    def start_fetch(self) -> None:
        if not self.d.can_fetch or self.d.fetch_state == "loading":
            return
        self.d.fetch_state = "loading"
        self.d.model = None
        self.refresh_view()
        self.set_timer(0.8, self._finish_fetch)

    def _finish_fetch(self) -> None:
        models = FAKE_MODELS.get(self.d.provider, [])
        if models:
            self.d.models = models
            self.d.fetch_state = "ok"
            self.d.model = models[0]
        else:
            self.d.fetch_state = "fail"
        self.refresh_view()

    def on_field_change(self) -> None:
        # any provider/url/key edit clears the fetched model set (ticket 02)
        self.d.models = []
        self.d.model = None
        self.d.fetch_state = "idle"
        self.refresh_view()

    def toggle_reveal(self) -> None:
        self.d.revealed = not self.d.revealed
        self.refresh_view()

    def try_save(self) -> None:
        err = self.d.save_error()
        self.app.report(err or f"[{C_SUCCESS}]✓ saved & closed (simulated)[/]")

    def refresh_view(self) -> None:
        raise NotImplementedError


# ── Variant A: stacked labeled rows (action_matrix shape) ──

class VariantA(VariantBase):
    def compose(self) -> ComposeResult:
        yield Static(id="a-summary", markup=True)
        yield Static(f"[bold {C_PRIMARY}]Configure LLM[/]", markup=True)
        yield Static(id="a-body", markup=True)
        yield Static(id="a-hint", markup=True)

    def refresh_view(self) -> None:
        d = self.d
        self.query_one("#a-summary", Static).update(summary_line(d))
        key = ("•" * min(len(d.api_key), 12)) if d.api_key and not d.revealed else (d.api_key or "")
        rows = [
            f"  provider   [b]{d.provider}[/]",
        ]
        if d.is_custom:
            rows.append(f"  base url   [b]{d.base_url or '[dim]—[/]'}[/]")
        eye = "👁 shown" if d.revealed else "• hidden"
        rows += [
            f"  api key    [b]{key or '[dim]—[/]'}[/]  [{C_MUTED}]({eye}, ^R)[/]",
            f"  model      [b]{d.model or '[dim]—[/]'}[/]",
            "",
            f"  [{C_PRIMARY}][ Fetch ][/]   [{C_PRIMARY}][ Save ][/]   [{C_MUTED}](Esc discards)[/]",
        ]
        self.query_one("#a-body", Static).update("\n".join(rows))
        self.query_one("#a-hint", Static).update("  " + fetch_hint(d))


# ── Variant B: two-column grid with real widgets + button row ──

class VariantB(VariantBase):
    def compose(self) -> ComposeResult:
        d = self.d
        yield Static(id="b-summary", markup=True)
        with Grid(id="b-grid"):
            yield Label("provider")
            yield Select([(p, p) for p in PROVIDERS], value=d.provider, id="b-prov", allow_blank=False)
            yield Label("base url", id="b-url-label")
            yield Input(value=d.base_url, placeholder="https://…", id="b-url")
            yield Label("api key")
            yield Input(value=d.api_key, password=True, id="b-key", select_on_focus=False)
            yield Label("model")
            yield Select([(m, m) for m in d.models], value=d.model or Select.BLANK,
                         id="b-model", prompt="(fetch first)")
        with Horizontal(id="b-actions"):
            yield Button("Fetch models", id="b-fetch", variant="primary")
            yield Button("Save", id="b-save", variant="success")
            yield Button("Reveal key (^R)", id="b-reveal")
        yield Static(id="b-hint", markup=True)

    def refresh_view(self) -> None:
        d = self.d
        self.query_one("#b-summary", Static).update(summary_line(d))
        # conditional base-url row via display
        self.query_one("#b-url-label").display = d.is_custom
        self.query_one("#b-url").display = d.is_custom
        self.query_one("#b-key", Input).password = not d.revealed
        model_sel = self.query_one("#b-model", Select)
        model_sel.set_options([(m, m) for m in d.models])
        if d.model:
            model_sel.value = d.model
        self.query_one("#b-fetch", Button).disabled = not d.can_fetch or d.fetch_state == "loading"
        self.query_one("#b-hint", Static).update(fetch_hint(d))

    def on_select_changed(self, e: Select.Changed) -> None:
        if e.select.id == "b-prov" and e.value is not Select.BLANK:
            self.d.provider = str(e.value)
            self.on_field_change()
        elif e.select.id == "b-model" and e.value is not Select.BLANK:
            self.d.model = str(e.value)

    def on_input_changed(self, e: Input.Changed) -> None:
        if e.input.id == "b-url":
            self.d.base_url = e.value
        elif e.input.id == "b-key":
            self.d.api_key = e.value
        self.query_one("#b-summary", Static).update(summary_line(self.d))
        self.query_one("#b-fetch", Button).disabled = not self.d.can_fetch or self.d.fetch_state == "loading"

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "b-fetch":
            self.start_fetch()
        elif e.button.id == "b-save":
            self.try_save()
        elif e.button.id == "b-reveal":
            self.toggle_reveal()


# ── Variant C: grouped collapsible sections ──

class VariantC(VariantBase):
    def compose(self) -> ComposeResult:
        yield Static(id="c-summary", markup=True)
        with Collapsible(title="Connection", collapsed=False, id="c-conn"):
            yield Static(id="c-conn-body", markup=True)
        with Collapsible(title="Model", collapsed=False, id="c-model"):
            yield Static(id="c-model-body", markup=True)
        yield Static(id="c-footer", markup=True)

    def refresh_view(self) -> None:
        d = self.d
        self.query_one("#c-summary", Static).update(summary_line(d))
        key = ("•" * min(len(d.api_key), 12)) if d.api_key and not d.revealed else (d.api_key or "—")
        conn = [f"    provider   [b]{d.provider}[/]"]
        if d.is_custom:
            conn.append(f"    base url   [b]{d.base_url or '[dim]—[/]'}[/]")
        conn.append(f"    api key    [b]{key}[/]  [{C_MUTED}]({'👁' if d.revealed else '•'} ^R)[/]")
        self.query_one("#c-conn-body", Static).update("\n".join(conn))
        self.query_one("#c-model-body", Static).update(
            f"    model  [b]{d.model or '[dim]—[/]'}[/]\n    {fetch_hint(d)}"
        )
        self.query_one("#c-footer", Static).update(
            f"  [{C_PRIMARY}][ Fetch ][/]   [{C_PRIMARY}][ Save ][/]   [{C_MUTED}](Esc discards)[/]"
        )


VARIANTS = {
    "1": ("A — Stacked rows (action_matrix shape)", VariantA),
    "2": ("B — Two-column grid + buttons", VariantB),
    "3": ("C — Grouped collapsible sections", VariantC),
}


class SwitcherBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static(id="switch-label", markup=True)


class PrototypeApp(App):
    CSS = """
    Screen { align: center middle; background: #1a1a1a; }
    #popup {
        width: 72; height: auto; padding: 1 2;
        border: solid #fab283; background: #222222;
    }
    #popup Static { height: auto; }
    #b-grid { grid-size: 2; grid-columns: 12 1fr; grid-gutter: 0 1; height: auto; padding: 1 0; }
    #b-grid Label { padding: 1 0 0 0; color: #eeeeee; }
    #b-actions { height: auto; padding-top: 1; }
    #b-actions Button { margin-right: 1; }
    #switchbar {
        dock: bottom; height: 1; background: #fab283; color: #1a1a1a;
        content-align: center middle;
    }
    #switch-label { color: #1a1a1a; text-style: bold; }
    #toast { dock: bottom; height: 1; margin-bottom: 1; content-align: center middle; }
    Collapsible { border: none; }
    """
    BINDINGS = [
        Binding("1", "show('1')", "A"),
        Binding("2", "show('2')", "B"),
        Binding("3", "show('3')", "C"),
        Binding("left", "cycle(-1)", "prev"),
        Binding("right", "cycle(1)", "next"),
        Binding("ctrl+r", "reveal", "reveal key"),
        Binding("f", "fetch", "fetch"),
        Binding("s", "save", "save"),
        Binding("p", "cycle_provider", "provider"),
        Binding("k", "type_key", "fake-key"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self):
        super().__init__()
        self.d = Draft()
        self.current = "1"

    def compose(self) -> ComposeResult:
        with Vertical(id="popup"):
            yield VariantA(self.d, id="v-1")
        yield Static(id="toast", markup=True)
        with Horizontal(id="switchbar"):
            yield Static(id="switch-label", markup=True)

    def on_mount(self) -> None:
        self._update_bar()

    def report(self, msg: str) -> None:
        self.query_one("#toast", Static).update(msg)

    def _update_bar(self) -> None:
        name, _cls = VARIANTS[self.current]
        self.query_one("#switch-label", Static).update(
            f" ← 1/2/3 →   {name}   | p:provider  k:fake-key  ^R:reveal  f:fetch  s:save  q:quit "
        )

    def _mount_variant(self) -> None:
        popup = self.query_one("#popup", Vertical)
        for child in list(popup.children):
            child.remove()
        _name, cls = VARIANTS[self.current]
        popup.mount(cls(self.d, id=f"v-{self.current}"))
        self.report("")
        self._update_bar()

    def action_show(self, key: str) -> None:
        self.current = key
        self._mount_variant()

    def action_cycle(self, delta: int) -> None:
        keys = list(VARIANTS)
        i = (keys.index(self.current) + delta) % len(keys)
        self.current = keys[i]
        self._mount_variant()

    def _active(self) -> VariantBase:
        return self.query_one(f"#v-{self.current}", VariantBase)

    def action_reveal(self) -> None:
        self._active().toggle_reveal()

    def action_fetch(self) -> None:
        self._active().start_fetch()

    def action_save(self) -> None:
        self._active().try_save()

    def action_cycle_provider(self) -> None:
        i = (PROVIDERS.index(self.d.provider) + 1) % len(PROVIDERS)
        self.d.provider = PROVIDERS[i]
        # custom needs a url to fetch; give a fake one so states are reachable
        if self.d.provider == "custom" and not self.d.base_url:
            self.d.base_url = "https://localhost:1234/v1"
        self._active().on_field_change()

    def action_type_key(self) -> None:
        self.d.api_key = "sk-proto-demo-key-1234"
        self._active().on_field_change()


if __name__ == "__main__":
    PrototypeApp().run()
