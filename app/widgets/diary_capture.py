"""日记快速记录（`Ctrl+M`）：一个输入框，回车就把这句话记到今天。

界面上**不写任何文字**（和记账面板同一套风格，只是更简单）。
内容**追加**到当天日记的末尾，不会覆盖你已经写过的部分；
要写长一点的日记，去「日记」页面写。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from .. import clock
from .. import diary as diary_store
from .common import AppDialog


class DiaryCaptureDialog(AppDialog):
    """极简日记窗：一个输入框，回车追加到今天。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.saved_text = ""
        self.day = clock.today_str()

        self.setObjectName("DiaryCapture")
        self.setWindowTitle("记日记")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMinimumWidth(520)
        self.setMaximumWidth(720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.input = QLineEdit()
        self.input.setObjectName("DiaryCaptureInput")
        self.input.returnPressed.connect(self._save)
        layout.addWidget(self.input)

        self.adjustSize()
        self.input.setFocus()

    def _save(self) -> None:
        text = self.input.text().strip()
        if not text:
            # 空着回车 = 什么都没记，直接关掉，不在日记里留空段
            self.reject()
            return
        diary_store.append_to_day(self.day, text)
        self.saved_text = text
        self.accept()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().showEvent(event)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            geometry = parent.frameGeometry()
            self.move(
                geometry.center().x() - self.width() // 2,
                geometry.center().y() - self.height() // 2,
            )
