from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Literal


MoveMode = Literal["move", "copy"]


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SidecarRule:
    type_label: str
    embedded: bool
    enabled: bool
    move_mode: MoveMode = "move"
    embedded_tag: str = ""
    filemask: str = ""

    @property
    def is_tree(self) -> bool:
        mask = self.filemask.replace("\\", "/")
        return (not self.embedded) and mask.endswith("/**")


def default_rules() -> list[SidecarRule]:
    return [
        SidecarRule(type_label="lyrics", embedded=False, enabled=True, filemask="{base}.lrc"),
        SidecarRule(type_label="cue", embedded=False, enabled=True, filemask="{base}.cue"),
        SidecarRule(type_label="nfo", embedded=False, enabled=True, filemask="{base}.nfo"),
        SidecarRule(type_label="xml", embedded=False, enabled=True, filemask="{base}.xml"),
        SidecarRule(type_label="log", embedded=False, enabled=True, filemask="{base}.log"),
        SidecarRule(type_label="m3u", embedded=False, enabled=True, filemask="{base}.m3u"),
        SidecarRule(type_label="booklet", embedded=False, enabled=True, filemask="{base}.pdf"),
        SidecarRule(type_label="checksums_sfv", embedded=False, enabled=True, filemask="{base}.sfv"),
        SidecarRule(type_label="checksums_md5", embedded=False, enabled=False, filemask="{base}.md5"),
        SidecarRule(type_label="cover_embedded", embedded=True, enabled=False, embedded_tag="coverart"),
    ]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def validate_rule(rule: SidecarRule) -> None:
    _require(rule.type_label.strip() != "", "type_label is required")
    _require(rule.move_mode in ("move", "copy"), "move_mode must be 'move' or 'copy'")

    if rule.embedded:
        _require(rule.embedded_tag.strip() != "", "embedded_tag is required when embedded=true")
        _require(rule.filemask.strip() == "", "filemask must be empty when embedded=true")
    else:
        _require(rule.filemask.strip() != "", "filemask is required when embedded=false")
        _require("{base}" in rule.filemask, "filemask must include '{base}'")
        _require(rule.embedded_tag.strip() == "", "embedded_tag must be empty when embedded=false")


def validate_rules_static(rules: Iterable[SidecarRule]) -> None:
    rules_list = list(rules)
    _require(len(rules_list) > 0, "At least one rule is required")
    seen_masks: set[str] = set()
    for rule in rules_list:
        validate_rule(rule)
        if rule.enabled and not rule.embedded:
            normalized = rule.filemask.replace("\\", "/")
            _require(
                normalized not in seen_masks,
                f"Duplicate filemask template for enabled external rule: {normalized!r}",
            )
            seen_masks.add(normalized)


def rules_to_json(rules: Iterable[SidecarRule]) -> str:
    payload = [
        {
            "type_label": r.type_label,
            "embedded": r.embedded,
            "embedded_tag": r.embedded_tag,
            "filemask": r.filemask,
            "enabled": r.enabled,
            "move_mode": r.move_mode,
        }
        for r in rules
    ]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def rules_from_json(raw: str) -> list[SidecarRule]:
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise ConfigError("Invalid rules JSON") from exc

    if not isinstance(data, list):
        raise ConfigError("Rules JSON must be a list")

    rules: list[SidecarRule] = []
    for item in data:
        if not isinstance(item, dict):
            raise ConfigError("Each rule must be an object")
        rules.append(
            SidecarRule(
                type_label=str(item.get("type_label", "")),
                embedded=bool(item.get("embedded", False)),
                embedded_tag=str(item.get("embedded_tag", "")),
                filemask=str(item.get("filemask", "")),
                enabled=bool(item.get("enabled", True)),
                move_mode=str(item.get("move_mode", "move")),
            )
        )

    validate_rules_static(rules)
    return rules


def coerce_rules(value: Any) -> list[SidecarRule]:
    if value is None:
        return default_rules()
    if isinstance(value, str):
        return rules_from_json(value)
    raise ConfigError("Unsupported rules value")
