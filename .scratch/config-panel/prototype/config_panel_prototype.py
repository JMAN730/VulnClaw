"""THROWAWAY PROTOTYPE — config_panel layout/feel exploration. NOT production code.

Answers wayfinder ticket 04: lock row order + labels + interaction feel for the
VulnClaw /config keyboard-navigable settings panel (LLM settings only).

Three STRUCTURALLY DIFFERENT variants of the same config_panel, all mounted inside a
floating popup that mimics the real `SecondaryPopup` (amber border, same palette).
Flip between them with the bottom switcher bar: keys 1/2/3 or ←/→.

    python .scratch/config-panel/prototype/config_panel_prototype.py

Variant A — Stacked labeled rows (mirrors /scope action_matrix: label+control per line, live summary
            top). Keyboard-driven: Up/Down moves the row cursor, Enter activates the focused row,
            Esc discards. Edits themselves are faked (toggle a canned value) — the point is row
            order + nav feel, not text entry.
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
    """Stacked rows with a real cursor: Up/Down moves, Enter activates, Esc discards.

    Rendered as a Static (action_matrix shape) rather than one focusable widget per row —
    the cursor is our own index over the *visible* rows, so the conditional base-URL row
    drops out of nav exactly like a `.display=False` row drops out of `focus_chain`.
    (The real panel uses focus_next/previous("#sec-popup *"); ticket 02 verified that
    against Textual 8.2.8. Here the point is the feel of the row order + activation.)
    """

    can_focus = True

    BINDINGS = [
        Binding("up", "row_up", "up", show=False),
        Binding("down", "row_down", "down", show=False),
        Binding("enter", "activate", "activate", show=False),
        Binding("escape", "discard", "discard", show=False),
    ]

    def __init__(self, d: Draft, **kw):
        super().__init__(d, **kw)
        self.cursor = 0

    def compose(self) -> ComposeResult:
        yield Static(id="a-summary", markup=True)
        yield Static(f"[bold {C_PRIMARY}]Configure LLM[/]", markup=True)
        yield Static(id="a-body", markup=True)
        yield Static(id="a-hint", markup=True)

    def on_mount(self) -> None:
        self.focus()
        super().on_mount()

    # -- nav model --

    def _rows(self) -> list[str]:
        """Visible, focusable row ids, top → bottom. base url only when custom (Q7)."""
        rows = ["provider"]
        if self.d.is_custom:
            rows.append("base_url")
        return rows + ["api_key", "model", "fetch", "save"]

    def _clamp(self) -> None:
        self.cursor = max(0, min(self.cursor, len(self._rows()) - 1))

    def action_row_up(self) -> None:
        self.cursor = (self.cursor - 1) % len(self._rows())
        self.refresh_view()

    def action_row_down(self) -> None:
        self.cursor = (self.cursor + 1) % len(self._rows())
        self.refresh_view()

    def action_discard(self) -> None:
        self.app.report(f"[{C_MUTED}]Esc — draft discarded, panel closed (simulated)[/]")

    def action_activate(self) -> None:
        """Enter on the focused row. Edits are faked (no real inputs in a Static layout)."""
        row = self._rows()[self.cursor]
        if row == "provider":
            self.app.action_cycle_provider()
        elif row == "base_url":
            self.d.base_url = "" if self.d.base_url else "https://localhost:1234/v1"
            self.on_field_change()
        elif row == "api_key":
            self.d.api_key = "" if self.d.api_key else "sk-proto-demo-key-1234"
            self.on_field_change()
        elif row == "model":
            if self.d.models:
                i = self.d.models.index(self.d.model) if self.d.model in self.d.models else -1
                self.d.model = self.d.models[(i + 1) % len(self.d.models)]
                self.refresh_view()
            else:
                self.app.report(f"[{C_MUTED}]no models yet — Fetch first[/]")
        elif row == "fetch":
            if self.d.can_fetch:
                self.start_fetch()
            else:
                self.app.report(f"[{C_MUTED}]Fetch disabled — need key{' + base url' if self.d.is_custom else ''}[/]")
        elif row == "save":
            self.try_save()

    # -- render --

    def refresh_view(self) -> None:
        d = self.d
        self._clamp()
        rows, cur = self._rows(), self._rows()[self.cursor]
        self.query_one("#a-summary", Static).update(summary_line(d))
        key = ("•" * min(len(d.api_key), 12)) if d.api_key and not d.revealed else (d.api_key or "")
        eye = "👁 shown" if d.revealed else "• hidden"

        def line(row_id: str, text: str) -> str:
            mark = f"[{C_PRIMARY}]>[/] " if row_id == cur else "  "
            return mark + (f"[reverse]{text}[/]" if row_id == cur else text)

        out = [line("provider", f"provider   [b]{d.provider}[/]")]
        if "base_url" in rows:
            out.append(line("base_url", f"base url   [b]{d.base_url or '[dim]—[/]'}[/]"))
        out += [
            line("api_key", f"api key    [b]{key or '[dim]—[/]'}[/]  [{C_MUTED}]({eye}, ^R)[/]"),
            line("model", f"model      [b]{d.model or '[dim]—[/]'}[/]"),
            "",
        ]
        fetch_col = C_PRIMARY if d.can_fetch else C_MUTED  # disabled Fetch is dimmed, still nav-able
        actions = (
            f"{'[reverse]' if cur == 'fetch' else ''}[{fetch_col}][ Fetch ][/]"
            f"{'[/]' if cur == 'fetch' else ''}   "
            f"{'[reverse]' if cur == 'save' else ''}[{C_PRIMARY}][ Save ][/]"
            f"{'[/]' if cur == 'save' else ''}   [{C_MUTED}](Esc discards)[/]"
        )
        mark = f"[{C_PRIMARY}]>[/] " if cur in ("fetch", "save") else "  "
        out.append(mark + actions)
        self.query_one("#a-body", Static).update("\n".join(out))
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
            f" ← 1/2/3 →   {name}   | ↑↓:row  Enter:activate  Esc:discard  ^R:reveal  p/k/f/s  q:quit "
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
