from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from glider.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic


@dataclass
class SkillOption:
    name: str
    description: str
    url: str


def _build_option_text(option: SkillOption, is_enabled: bool) -> Text:
    text = Text(no_wrap=True)
    marker = "› " if is_enabled else "  "
    style = "bold" if is_enabled else ""
    text.append(marker, style="green" if is_enabled else "")
    text.append(option.name, style=style)
    text.append(f" - {option.description}", style="dim")
    return text


class DiscoverSkillsApp(Container):
    """Skills discover picker bottom app."""

    can_focus_children = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False)
    ]

    class SkillSelected(Message):
        def __init__(self, url: str) -> None:
            self.url = url
            super().__init__()

    class Cancelled(Message):
        pass

    def __init__(
        self, options: list[SkillOption], enabled_names: set[str], **kwargs: Any
    ) -> None:
        super().__init__(id="discover-skills-app", **kwargs)
        self._options = options
        self._enabled_names = enabled_names

    def compose(self) -> ComposeResult:
        option_list = [
            Option(_build_option_text(opt, opt.name in self._enabled_names), id=opt.url)
            for opt in self._options
        ]
        with Vertical(id="discover-skills-content"):
            yield NoMarkupStatic("Discover Skills", classes="modelpicker-title")
            yield OptionList(*option_list, id="discover-skills-options")
            yield NoMarkupStatic(
                "↑↓ Navigate  Enter Enable/Disable  Esc Cancel",
                classes="modelpicker-help",
            )

    def on_mount(self) -> None:
        option_list = self.query_one(OptionList)
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.post_message(self.SkillSelected(event.option.id))

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())
