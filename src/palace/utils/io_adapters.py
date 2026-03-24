"""Model adapter utilities for specialized finetuned models.

Allows users to define per-model input/output transformations via YAML config
or programmatic API, so that models with fixed I/O formats (e.g., guardrails)
can be evaluated on standard palace tasklists.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from palace.utils.paths import IO_ADAPTERS_FILE
from palace.utils.printing import print

if TYPE_CHECKING:
    from palace.task_types.base import Task

# Available placeholders for input templates
INPUT_PLACEHOLDERS = {"objective", "document", "attachment", "expected"}


@dataclass
class IOAdapter:
    """Holds parsed adapter config and applies input/output transformations."""

    input_template: str | None = None
    output_pattern: re.Pattern | None = None
    output_template: str | None = None
    output_mapping: dict[str, dict[str, str]] = field(default_factory=dict)

    def adapt_input(self, task: "Task", attachment_content: str = "") -> str:
        """Apply input template with task field substitution.

        If no input_template is set, returns task.create_prompt().
        Placeholders: {objective}, {document}, {attachment}, {expected}
        Missing fields are substituted with empty string.
        """
        if self.input_template is None:
            return task.create_prompt()

        return self.input_template.format(
            objective=task.objective or "",
            document=task.document or "",
            attachment=attachment_content,
            expected=task.expected or "",
        )

    def adapt_output(self, raw_output: str) -> str:
        """Apply output regex extraction, mapping, and template formatting.

        If no output_pattern is set, returns raw_output unchanged.
        On pattern no-match: passthrough with warning.
        On mapping miss: passthrough captured value with warning.
        """
        if self.output_pattern is None:
            return raw_output

        match = self.output_pattern.search(raw_output)
        if match is None:
            print(
                f"[yellow bold]Adapter output pattern did not match. "
                f"Pattern: {self.output_pattern.pattern!r}, "
                f"Output: {raw_output[:200]!r}. Using raw output.[/]"
            )
            return raw_output

        groups = match.groupdict()

        # Apply mapping per group
        mapped = {}
        for name, value in groups.items():
            group_mapping = self.output_mapping.get(name)
            if group_mapping and value in group_mapping:
                mapped[name] = group_mapping[value]
            elif group_mapping and value not in group_mapping:
                print(
                    f"[yellow bold]Adapter mapping miss for group '{name}': "
                    f"value '{value}' not in mapping {group_mapping}. "
                    f"Using raw value.[/]"
                )
                mapped[name] = value
            else:
                mapped[name] = value

        # Format template or use first group
        if self.output_template is not None:
            return self.output_template.format(**mapped)

        # No template: return first capture group value
        first_group = match.group(1) if match.lastindex else raw_output
        first_group_name = list(groups.keys())[0] if groups else None
        return mapped.get(first_group_name, first_group) if first_group_name else first_group


def parse_io_adapter_config(config: dict) -> IOAdapter:
    """Parse a raw dict (from YAML or programmatic API) into a validated IOAdapter.

    Raises ValueError on invalid config (bad regex, template references unknown groups).
    """
    input_template = None
    output_pattern = None
    output_template = None
    output_mapping: dict[str, dict[str, str]] = {}

    # Parse input
    input_cfg = config.get("input")
    if input_cfg is not None:
        if not isinstance(input_cfg, dict) or "template" not in input_cfg:
            raise ValueError("Adapter 'input' must be a dict with 'template' key")
        input_template = input_cfg["template"]

    # Parse output
    output_cfg = config.get("output")
    if output_cfg is not None:
        if not isinstance(output_cfg, dict):
            raise ValueError("Adapter 'output' must be a dict")

        pattern_str = output_cfg.get("pattern")
        if pattern_str is not None:
            try:
                output_pattern = re.compile(pattern_str)
            except re.error as e:
                raise ValueError(f"Invalid regex in adapter output.pattern: {e}")

            # Validate template references existing groups
            output_template = output_cfg.get("template")
            if output_template is not None and output_pattern is not None:
                group_names = set(output_pattern.groupindex.keys())
                template_refs = set(re.findall(r"\{(\w+)\}", output_template))
                unknown = template_refs - group_names
                if unknown:
                    raise ValueError(
                        f"Adapter output.template references unknown groups: {unknown}. "
                        f"Available groups: {group_names}"
                    )

        output_mapping = output_cfg.get("mapping", {})
        if not isinstance(output_mapping, dict):
            raise ValueError("Adapter output.mapping must be a dict")

    return IOAdapter(
        input_template=input_template,
        output_pattern=output_pattern,
        output_template=output_template,
        output_mapping=output_mapping,
    )


def load_io_adapters(file_path: Path | None = None) -> dict[str, IOAdapter]:
    """Load and validate I/O adapters from YAML file.

    Returns ordered dict of {glob_pattern: IOAdapter}.
    Returns empty dict if file doesn't exist.
    Raises ValueError on invalid config.
    """
    path = file_path or IO_ADAPTERS_FILE
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Adapters file must be a YAML mapping, got {type(raw).__name__}")

    adapters: dict[str, IOAdapter] = {}
    for pattern, config in raw.items():
        try:
            adapters[str(pattern)] = parse_io_adapter_config(config)
        except ValueError as e:
            raise ValueError(f"Invalid adapter config for '{pattern}': {e}") from e

    return adapters


def get_io_adapter(
    model_name: str,
    explicit_adapter: dict | None = None,
    file_io_adapters: dict[str, IOAdapter] | None = None,
) -> IOAdapter | None:
    """Get I/O adapter for model. Priority: explicit > file > None.

    Args:
        model_name: The model name to match against adapter patterns
        explicit_adapter: Programmatic adapter dict (highest priority)
        file_io_adapters: Pre-loaded file adapters from load_io_adapters()
    """
    if explicit_adapter is not None:
        return parse_io_adapter_config(explicit_adapter)

    if file_io_adapters:
        for pattern, adapter in file_io_adapters.items():
            if fnmatch.fnmatch(model_name, pattern):
                return adapter

    return None
