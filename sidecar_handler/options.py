from __future__ import annotations

import importlib
from typing import Optional

from picard.plugin3.api import OptionsPage

from .config import (
    ConfigError,
    SidecarRule,
    default_rules,
    rules_from_json,
    rules_to_json,
    validate_rules_static,
)
from .plugin_hooks import RULES_KEY, SUPERSEDE_KEY


def _qt():
    qtwidgets = importlib.import_module("PyQt6.QtWidgets")
    qtcore = importlib.import_module("PyQt6.QtCore")
    return qtwidgets, qtcore


class _RuleDialog:
    def __init__(self, parent, rule: Optional[SidecarRule] = None):
        QtWidgets, QtCore = _qt()
        self._QtCore = QtCore

        self.dialog = QtWidgets.QDialog(parent)
        self.dialog.setWindowTitle("Sidecar Rule")

        layout = QtWidgets.QVBoxLayout(self.dialog)
        form = QtWidgets.QFormLayout()

        self.type_edit = QtWidgets.QLineEdit()
        self.embedded_cb = QtWidgets.QCheckBox("Embedded")
        self.value_edit = QtWidgets.QLineEdit()
        self.enabled_cb = QtWidgets.QCheckBox("Enabled")
        self.enabled_cb.setChecked(True)

        form.addRow("Sidecar Type", self.type_edit)
        form.addRow("Embedded", self.embedded_cb)
        form.addRow("Embedded Tag / Filemask", self.value_edit)
        form.addRow("Enabled", self.enabled_cb)
        layout.addLayout(form)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(btns)

        btns.accepted.connect(self.dialog.accept)
        btns.rejected.connect(self.dialog.reject)

        if rule is not None:
            self.type_edit.setText(rule.type_label)
            self.embedded_cb.setChecked(rule.embedded)
            self.value_edit.setText(rule.embedded_tag if rule.embedded else rule.filemask)
            self.enabled_cb.setChecked(rule.enabled)

    def exec(self) -> int:
        return self.dialog.exec()

    def get_rule(self) -> SidecarRule:
        type_label = self.type_edit.text().strip()
        embedded = self.embedded_cb.isChecked()
        value = self.value_edit.text().strip()
        enabled = self.enabled_cb.isChecked()
        if embedded:
            return SidecarRule(
                type_label=type_label,
                embedded=True,
                enabled=enabled,
                embedded_tag=value,
                filemask="",
            )
        return SidecarRule(
            type_label=type_label,
            embedded=False,
            enabled=enabled,
            embedded_tag="",
            filemask=value,
        )


class SidecarHandlerOptionsPage(OptionsPage):
    NAME = "sidecar_handler"
    TITLE = "Sidecar Handler"
    PARENT = "plugins"

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self.api = api

        QtWidgets, QtCore = _qt()
        self._QtCore = QtCore
        self._QtWidgets = QtWidgets

        root = QtWidgets.QWidget(parent)
        layout = QtWidgets.QVBoxLayout(root)

        self.table = QtWidgets.QTableWidget(root)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Sidecar Type", "Embedded", "Embedded Tag / Filemask", "Enabled"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add")
        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.remove_btn = QtWidgets.QPushButton("Remove")
        self.restore_btn = QtWidgets.QPushButton("Restore defaults")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.restore_btn)
        layout.addLayout(btn_row)

        self.supersede_cb = QtWidgets.QCheckBox("Supersede additional files handling")
        layout.addWidget(self.supersede_cb)

        self.add_btn.clicked.connect(self._add_row)
        self.edit_btn.clicked.connect(self._edit_row)
        self.remove_btn.clicked.connect(self._remove_row)
        self.restore_btn.clicked.connect(self._restore_defaults)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self._update_buttons()

        self.setLayout(layout)
        self._root = root

    def get_widget(self):
        return self._root

    def load(self):
        self.api.plugin_config.register_option(RULES_KEY, rules_to_json(default_rules()))
        self.api.plugin_config.register_option(SUPERSEDE_KEY, False)

        raw = self.api.plugin_config.get(RULES_KEY)
        try:
            rules = rules_from_json(raw) if raw else default_rules()
        except Exception:
            rules = default_rules()
        self._load_rules_into_table(rules)

        self.supersede_cb.setChecked(bool(self.api.plugin_config.get(SUPERSEDE_KEY, False)))

    def save(self):
        rules = self._rules_from_table()
        validate_rules_static(rules)
        self.api.plugin_config[RULES_KEY] = rules_to_json(rules)
        self.api.plugin_config[SUPERSEDE_KEY] = self.supersede_cb.isChecked()

    def _message_error(self, title: str, message: str) -> None:
        QtWidgets = self._QtWidgets
        box = QtWidgets.QMessageBox(self._root)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()

    def _selected_row(self) -> Optional[int]:
        sel = self.table.selectionModel().selectedRows()
        return sel[0].row() if sel else None

    def _update_buttons(self):
        row = self._selected_row()
        has_sel = row is not None
        self.edit_btn.setEnabled(has_sel)
        self.remove_btn.setEnabled(has_sel and self.table.rowCount() > 1)

    def _load_rules_into_table(self, rules: list[SidecarRule]) -> None:
        self.table.setRowCount(0)
        for rule in rules:
            self._append_table_row(rule)
        self._update_buttons()

    def _append_table_row(self, rule: SidecarRule) -> None:
        QtCore = self._QtCore
        QtWidgets = self._QtWidgets

        row = self.table.rowCount()
        self.table.insertRow(row)

        t_item = QtWidgets.QTableWidgetItem(rule.type_label)

        e_item = QtWidgets.QTableWidgetItem()
        e_item.setFlags(e_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        e_item.setCheckState(QtCore.Qt.CheckState.Checked if rule.embedded else QtCore.Qt.CheckState.Unchecked)

        v = rule.embedded_tag if rule.embedded else rule.filemask
        v_item = QtWidgets.QTableWidgetItem(v)

        en_item = QtWidgets.QTableWidgetItem()
        en_item.setFlags(en_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        en_item.setCheckState(QtCore.Qt.CheckState.Checked if rule.enabled else QtCore.Qt.CheckState.Unchecked)

        self.table.setItem(row, 0, t_item)
        self.table.setItem(row, 1, e_item)
        self.table.setItem(row, 2, v_item)
        self.table.setItem(row, 3, en_item)

    def _rule_from_row(self, row: int) -> SidecarRule:
        QtCore = self._QtCore
        type_label = self.table.item(row, 0).text().strip()
        embedded = self.table.item(row, 1).checkState() == QtCore.Qt.CheckState.Checked
        value = self.table.item(row, 2).text().strip()
        enabled = self.table.item(row, 3).checkState() == QtCore.Qt.CheckState.Checked
        if embedded:
            return SidecarRule(type_label=type_label, embedded=True, enabled=enabled, embedded_tag=value, filemask="")
        return SidecarRule(type_label=type_label, embedded=False, enabled=enabled, embedded_tag="", filemask=value)

    def _rules_from_table(self) -> list[SidecarRule]:
        rules: list[SidecarRule] = []
        for row in range(self.table.rowCount()):
            rules.append(self._rule_from_row(row))
        return rules

    def _add_row(self):
        try:
            dlg = _RuleDialog(self._root, default_rules()[0])
            if dlg.exec() != 1:
                return
            rule = dlg.get_rule()
            validate_rules_static(self._rules_from_table() + [rule])
            self._append_table_row(rule)
            self._update_buttons()
        except ConfigError as exc:
            self._message_error("Invalid rule", str(exc))

    def _edit_row(self):
        row = self._selected_row()
        if row is None:
            return
        try:
            current = self._rule_from_row(row)
            dlg = _RuleDialog(self._root, current)
            if dlg.exec() != 1:
                return
            rule = dlg.get_rule()
            # Validate with replacement.
            rules = self._rules_from_table()
            rules[row] = rule
            validate_rules_static(rules)
            # Apply to table.
            self.table.item(row, 0).setText(rule.type_label)
            self.table.item(row, 1).setCheckState(self._QtCore.Qt.CheckState.Checked if rule.embedded else self._QtCore.Qt.CheckState.Unchecked)
            self.table.item(row, 2).setText(rule.embedded_tag if rule.embedded else rule.filemask)
            self.table.item(row, 3).setCheckState(self._QtCore.Qt.CheckState.Checked if rule.enabled else self._QtCore.Qt.CheckState.Unchecked)
        except ConfigError as exc:
            self._message_error("Invalid rule", str(exc))

    def _remove_row(self):
        row = self._selected_row()
        if row is None:
            return
        if self.table.rowCount() <= 1:
            return
        self.table.removeRow(row)
        self._update_buttons()

    def _restore_defaults(self):
        self._load_rules_into_table(default_rules())
