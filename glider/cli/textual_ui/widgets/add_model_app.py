from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Static

from glider.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from glider.cli.textual_ui.widgets.vscode_compat import VscodeCompatInput
from glider.core.config import GliderConfig, ModelConfig

if TYPE_CHECKING:
    from glider.core.config import GliderConfig as GliderConfigType


class AddModelApp(Vertical):
    can_focus = True
    can_focus_children = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False)
    ]

    class ModelAdded(Message):
        def __init__(self, alias: str) -> None:
            super().__init__()
            self.alias = alias

    class Cancelled(Message):
        pass

    def __init__(self, config: GliderConfigType) -> None:
        super().__init__(id="addmodel-app")
        self.config = config
        self.input_widget: VscodeCompatInput | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="addmodel-content"):
            yield NoMarkupStatic("Add Model", classes="settings-title")
            yield NoMarkupStatic(
                "Enter the model name (e.g., anthropic/claude-3.5-sonnet)",
                classes="settings-description",
            )
            self.input_widget = VscodeCompatInput(
                placeholder="Model name...",
                id="addmodel-input",
                classes="addmodel-input",
            )
            yield self.input_widget
            yield NoMarkupStatic("Enter add model  ESC cancel", classes="settings-help")
            yield NoMarkupStatic(
                "⚠ Glider must be reloaded for the model to appear in the picker.",
                classes="settings-warning",
            )

    def focus(self, scroll_visible: bool = True) -> AddModelApp:
        if self.input_widget:
            self.input_widget.focus(scroll_visible=scroll_visible)
        else:
            super().focus(scroll_visible=scroll_visible)
        return self

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._add_model()

    def on_blur(self, _event: events.Blur) -> None:
        self.call_after_refresh(self._refocus_if_needed)

    def on_input_blurred(self, _event: Input.Blurred) -> None:
        self.call_after_refresh(self._refocus_if_needed)

    def _refocus_if_needed(self) -> None:
        if self.has_focus or (self.input_widget and self.input_widget.has_focus):
            return
        self.focus()

    def _add_model(self) -> None:
        if not self.input_widget:
            self.post_message(self.Cancelled())
            return

        model_name = self.input_widget.value.strip()
        if not model_name:
            return

        alias = f"{model_name.split('/')[-1].replace('-', '-').lower()}-openrouter"

        model_config = ModelConfig(
            name=model_name,
            provider="openrouter",
            alias=alias,
            temperature=0.2,
            input_price=0.0,
            output_price=0.0,
            thinking="off",
        )

        updates = {"models": [*self.config.models, model_config.model_dump()]}

        try:
            GliderConfig.save_updates(updates)
            self.post_message(self.ModelAdded(alias=alias))
        except Exception as e:
            self.post_message(self.Cancelled())
