import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class ImportReport:
    def __init__(self, source_path, source_type, destination, strip_uids):
        self.source_path = source_path
        self.source_type = source_type
        self.destination = destination
        self.strip_uids = strip_uids
        self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.warnings = []
        self.infos = []
        self._seen_warnings = set()
        self._seen_infos = set()
        self.copied_media = []
        self._copied_media_seen = set()
        self.missing_media = []
        self.outputs = []
        self.metadata = {}
        self._context_stack = []

    def warn(self, message, context=None):
        warning = {"message": message}
        warning.update(self._merged_context())

        if context:
            warning["context"] = context
        key = self._report_item_key(warning)
        if key in self._seen_warnings:
            return warning
        self._seen_warnings.add(key)
        self.warnings.append(warning)
        return warning

    def info(self, message, context=None):
        if message == "Response placeholder will be recovered from duplicate statement fragments.":
            return None
        info = {"message": message}
        info.update(self._merged_context())

        if context:
            info["context"] = context
        key = self._report_item_key(info)
        if key in self._seen_infos:
            return info
        self._seen_infos.add(key)
        self.infos.append(info)
        return info

    def _merged_context(self):
        merged_context = {}
        for frame in self._context_stack:
            merged_context.update(frame)

        for key in ["manifest_path", "line", "item_type", "item_name"]:
            value = merged_context.get(key)
            if value in (None, ""):
                merged_context.pop(key, None)
        return merged_context

    @contextmanager
    def scoped_context(self, **context):
        cleaned = {key: value for key, value in context.items() if value not in (None, "")}
        self._context_stack.append(cleaned)
        try:
            yield
        finally:
            self._context_stack.pop()

    def add_output(self, path):
        self.outputs.append(path)

    def add_copied_media(self, filename, source_path):
        normalized_source_path = os.path.normpath(str(source_path))
        key = (str(filename), normalized_source_path.casefold())
        if key in self._copied_media_seen:
            return
        self._copied_media_seen.add(key)
        self.copied_media.append({"filename": filename, "source_path": normalized_source_path})

    def add_missing_media(self, filename):
        self.missing_media.append(filename)

    def to_dict(self):
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "destination": self.destination,
            "strip_uids": self.strip_uids,
            "created_at": self.created_at,
            "warnings": self.warnings,
            "infos": self.infos,
            "copied_media": self.copied_media,
            "missing_media": self.missing_media,
            "outputs": self.outputs,
            "metadata": self.metadata,
        }

    def to_text(self):
        lines = [
            "Nobius Import Report",
            f"Source: {self.source_path}",
            f"Source type: {self.source_type}",
            f"Destination: {self.destination}",
            f"Strip UIDs: {self.strip_uids}",
            f"Manifest: {self.metadata.get('manifest_path', '(unknown)')}",
            f"Warnings: {len(self.warnings)}",
            f"Info: {len(self.infos)}",
            f"Copied media: {len(self.copied_media)}",
            f"Missing media: {len(self.missing_media)}",
            "",
        ]

        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(self._format_report_line(warning))
            lines.append("")

        if self.infos:
            lines.append("Info:")
            for info in self.infos:
                lines.append(self._format_report_line(info))
            lines.append("")

        if self.copied_media:
            lines.append("Copied media:")
            for item in self.copied_media:
                lines.append(f"- {item['filename']} <- {item['source_path']}")
            lines.append("")

        if self.missing_media:
            lines.append("Missing media:")
            for item in self.missing_media:
                lines.append(f"- {item}")
            lines.append("")

        if self.outputs:
            lines.append("Outputs:")
            for path in self.outputs:
                lines.append(f"- {path}")

        return "\n".join(lines) + "\n"

    def _format_report_line(self, item):
        detail_parts = []
        if "item_type" in item and "item_name" in item:
            detail_parts.append(f"{item['item_type']}: {item['item_name']}")
        elif "item_name" in item:
            detail_parts.append(str(item["item_name"]))

        if "manifest_path" in item and "line" in item:
            detail_parts.append(f"{item['manifest_path']}:{item['line']}")
        elif "manifest_path" in item:
            detail_parts.append(str(item["manifest_path"]))

        if "context" in item:
            detail_parts.append(str(item["context"]))

        if detail_parts:
            return f"- {item['message']} [{' | '.join(detail_parts)}]"
        return f"- {item['message']}"

    def _report_item_key(self, item):
        return (
            item.get("message"),
            item.get("context"),
            item.get("manifest_path"),
            item.get("line"),
            item.get("item_type"),
            item.get("item_name"),
        )

    def write(self, destination_dir):
        destination = Path(destination_dir)
        json_path = destination / "import_report.json"
        text_path = destination / "import_report.txt"

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=2)

        with open(text_path, "w", encoding="utf-8") as file:
            file.write(self.to_text())

        return str(json_path), str(text_path)
