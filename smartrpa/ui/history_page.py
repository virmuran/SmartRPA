"""History Page — task execution history with stats and records list.

Full implementation: stats cards, color-coded record list, clear/refresh actions.
"""
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

from smartrpa.ui.theme import (
    T, section_title, btn_ghost, btn_danger, page_title, page_subtitle,
)
from smartrpa.business.history import HistoryStore


class HistoryPage(QWidget):
    """Page for viewing past task execution records with stats."""

    def __init__(self, parent=None):
        """Initialize the history page."""
        super().__init__(parent)
        self._main_window = None
        self._store = HistoryStore()
        self._build()
        self._refresh()

    # ── Public: dependency injection ──

    def set_main_window(self, mw) -> None:
        """Store reference to the main window for callbacks.

        Args:
            mw: The MainWindow instance that hosts this page.
        """
        self._main_window = mw
        if mw and hasattr(mw, 'theme_changed'):
            mw.theme_changed.connect(lambda _: self.refresh_theme())

    # ═══════════════════════════════════════════════
    #  Build UI
    # ═══════════════════════════════════════════════

    def _build(self) -> None:
        """Construct the full history page layout."""
        self.setStyleSheet(f"background: {T.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        root.setSpacing(T.SP_LG)

        # Header
        root.addWidget(page_title("历史记录"))
        root.addWidget(page_subtitle("查看过往的任务执行记录"))

        # ═══ Stats Cards ═══
        stats_row = QHBoxLayout()
        stats_row.setSpacing(T.SP_MD)

        self._stat_total = self._make_stat_card("总运行次数", "0")
        stats_row.addWidget(self._stat_total)

        self._stat_steps = self._make_stat_card("总步数", "0")
        stats_row.addWidget(self._stat_steps)

        self._stat_errors = self._make_stat_card("总错误数", "0")
        stats_row.addWidget(self._stat_errors)

        root.addLayout(stats_row)

        # ═══ Records List ═══
        list_card = QWidget()
        list_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        lc_ly = QVBoxLayout(list_card)
        lc_ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        lc_ly.setSpacing(T.SP_MD)

        list_hdr = QHBoxLayout()
        list_hdr.addWidget(section_title("运行记录"))
        list_hdr.addStretch()

        refresh_btn = btn_ghost("刷新")
        refresh_btn.clicked.connect(self._refresh)
        list_hdr.addWidget(refresh_btn)

        clear_btn = btn_danger("清空历史")
        clear_btn.clicked.connect(self._clear_history)
        list_hdr.addWidget(clear_btn)

        lc_ly.addLayout(list_hdr)

        self.record_list = QListWidget()
        self.record_list.setFont(QFont("Microsoft YaHei", 10))
        self.record_list.setStyleSheet(f"""
            QListWidget {{
                background: {T.SURFACE};
                color: {T.TEXT};
                border: 1px solid {T.LINE};
                border-radius: {T.R_MD}px;
                padding: 8px;
                font-size: 12px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 0px;
                border-radius: 4px;
                min-height: 28px;
            }}
            QListWidget::item:hover {{
                background: {T.CARD_HOVER};
            }}
        """)
        lc_ly.addWidget(self.record_list, 1)

        # Empty state
        self._empty_lbl = QLabel("暂无运行记录")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{T.TEXT3};font-size:13px;padding:24px;background:transparent;"
        )
        lc_ly.addWidget(self._empty_lbl)
        self._empty_lbl.hide()

        root.addWidget(list_card, 1)

    def _make_stat_card(self, title: str, value: str) -> QWidget:
        """Create a stat card widget.

        Args:
            title: Label for the stat.
            value: Numeric value string.

        Returns:
            A QWidget card showing the stat.
        """
        card = QWidget()
        card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(4)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"font-size:28px;font-weight:800;color:{T.TEXT};letter-spacing:-1px;"
        )
        val_lbl.setAlignment(Qt.AlignCenter)
        ly.addWidget(val_lbl)

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"font-size:11px;color:{T.TEXT3};font-weight:500;"
        )
        ttl_lbl.setAlignment(Qt.AlignCenter)
        ly.addWidget(ttl_lbl)

        return card

    # ═══════════════════════════════════════════════
    #  Data Loading & Refresh
    # ═══════════════════════════════════════════════

    def _refresh(self) -> None:
        """Reload records and update stats."""
        records = self._store.get_records(limit=200)
        self._update_stats(records)
        self._populate_list(records)

    def _update_stats(self, records: list) -> None:
        """Update the stat cards from a list of records.

        Args:
            records: List of record dicts from HistoryStore.
        """
        total_runs = len(records)
        total_steps = sum(r.get("steps", 0) for r in records)
        total_errors = sum(r.get("errors", 0) for r in records)

        # Find the value labels inside each stat card
        cards = [self._stat_total, self._stat_steps, self._stat_errors]
        values = [str(total_runs), str(total_steps), str(total_errors)]
        for card, val in zip(cards, values):
            # The value label is the first QLabel child
            val_lbl = card.layout().itemAt(0).widget()
            val_lbl.setText(val)

    def _populate_list(self, records: list) -> None:
        """Populate the QListWidget with formatted history records.

        Args:
            records: List of record dicts from HistoryStore.
        """
        self.record_list.clear()

        if not records:
            self._empty_lbl.show()
            self.record_list.hide()
            return

        self._empty_lbl.hide()
        self.record_list.show()

        for r in records:
            task_name = r.get("task_name", "未知任务")
            steps = r.get("steps", 0)
            errors = r.get("errors", 0)
            duration = r.get("duration", 0.0)
            ts = r.get("timestamp", "")

            # Format timestamp
            try:
                dt = datetime.datetime.fromisoformat(ts)
                ts_display = dt.strftime("%m/%d %H:%M:%S")
            except (ValueError, TypeError):
                ts_display = ts[:19] if ts else ""

            # Format duration
            if duration < 60:
                dur_str = f"{duration:.1f}s"
            else:
                m = int(duration // 60)
                s = duration % 60
                dur_str = f"{m}m{s:.0f}s"

            # Color: green for 0 errors, red otherwise
            has_errors = errors > 0
            status_color = T.RED if has_errors else T.GREEN
            status_text = f"{errors}错误" if has_errors else "成功"

            # Build display text
            display = (
                f"{task_name}  │  {steps}步  │  {status_text}  │  "
                f"{dur_str}  │  {ts_display}"
            )

            item = QListWidgetItem()
            item.setSizeHint(QSize(self.record_list.width() - 20, 28))
            self.record_list.addItem(item)

            row_w = QWidget()
            row_ly = QHBoxLayout(row_w)
            row_ly.setContentsMargins(8, 2, 8, 2)
            row_ly.setSpacing(8)

            # Status dot
            dot = QLabel("●")
            dot.setFixedWidth(16)
            dot.setStyleSheet(
                f"color:{status_color};font-size:10px;background:transparent;"
            )
            row_ly.addWidget(dot)

            # Text
            lbl = QLabel(display)
            lbl.setStyleSheet(f"font-size:11px;color:{T.TEXT};")
            lbl.setWordWrap(False)
            row_ly.addWidget(lbl, 1)

            self.record_list.setItemWidget(item, row_w)

    def _clear_history(self) -> None:
        """Confirm and clear all history records."""
        reply = QMessageBox.warning(
            self, "确认清空",
            "确定要清空所有历史记录吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._store.clear()
            self._refresh()

    # ═══════════════════════════════════════════════
    #  Theme Refresh
    # ═══════════════════════════════════════════════

    def refresh_theme(self) -> None:
        """Refresh all inline styles after a theme change."""
        self.setStyleSheet(f"background: {T.BG};")
        self._empty_lbl.setStyleSheet(
            f"color:{T.TEXT3};font-size:13px;padding:24px;background:transparent;"
        )
        # Re-populate list with current theme colors
        self._refresh()
