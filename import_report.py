import json
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
        self.copied_media = []
        self.missing_media = []
        self.outputs = []
        self.metadata = {}

    def warn(self, message, context=None):
        warning = {"message": message}
        if context:
            warning["context"] = context
        self.warnings.append(warning)
        return warning

    def add_output(self, path):
        self.outputs.append(path)

    def add_copied_media(self, filename, source_path):
        self.copied_media.append({"filename": filename, "source_path": source_path})

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
            f"Warnings: {len(self.warnings)}",
            f"Copied media: {len(self.copied_media)}",
            f"Missing media: {len(self.missing_media)}",
            "",
        ]

        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                if "context" in warning:
                    lines.append(f"- {warning['message']} [{warning['context']}]")
                else:
                    lines.append(f"- {warning['message']}")
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

    def write(self, destination_dir):
        destination = Path(destination_dir)
        json_path = destination / "import_report.json"
        text_path = destination / "import_report.txt"

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=2)

        with open(text_path, "w", encoding="utf-8") as file:
            file.write(self.to_text())

        return str(json_path), str(text_path)
