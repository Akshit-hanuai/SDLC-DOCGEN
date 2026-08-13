from pathlib import Path

import yaml

from app.schemas.template import TemplateSchema

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class TemplateStore:
    def __init__(self, templates_dir: Path | None = None):
        self.templates_dir = templates_dir or DEFAULT_TEMPLATES_DIR

    def _paths(self) -> list[Path]:
        return sorted(self.templates_dir.glob("*.yaml"))

    def list_summaries(self) -> list[dict]:
        summaries = []
        for path in self._paths():
            schema = self._load_path(path)
            summaries.append(
                {
                    "template_id": schema.template_id,
                    "doc_type": schema.doc_type,
                    "name": schema.name,
                    "version": schema.version,
                    "organization": schema.organization,
                    "num_sections": len(schema.sections),
                    "required_sections": schema.required_section_ids,
                }
            )
        return summaries

    def _load_path(self, path: Path) -> TemplateSchema:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return TemplateSchema.model_validate(data)

    def get(self, template_id: str) -> TemplateSchema | None:
        for path in self._paths():
            if path.stem == template_id:
                return self._load_path(path)
        return None

    def validate_all(self) -> list[str]:
        errors: list[str] = []
        for path in self._paths():
            try:
                schema = self._load_path(path)
                seen: set[str] = set()
                for section in schema.sections:
                    if section.id in seen:
                        errors.append(f"{path.name}: duplicate section id {section.id!r}")
                    seen.add(section.id)
                    field_ids = [f.id for f in section.fields]
                    if len(field_ids) != len(set(field_ids)):
                        errors.append(f"{path.name}/{section.id}: duplicate field ids")
            except Exception as exc:  # noqa: BLE001 - collect all validation problems
                errors.append(f"{path.name}: {exc}")
        return errors


template_store = TemplateStore()
