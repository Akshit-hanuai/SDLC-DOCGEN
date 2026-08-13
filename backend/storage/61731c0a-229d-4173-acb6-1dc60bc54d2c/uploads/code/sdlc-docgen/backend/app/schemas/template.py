from typing import Literal

from pydantic import BaseModel, Field

FieldType = Literal[
    "free_text",
    "text",
    "date",
    "enum",
    "list",
    "table",
    "requirements",
    "traceability_matrix",
]

SectionType = Literal["free_text", "requirements", "traceability_matrix"]


class NumberingScheme(BaseModel):
    section_id_format: str = Field(default="{N}.{M}")
    requirement_id_format: str = Field(default="REQ-{PROJECT}-{NNNN}")
    annexure_prefix: str = Field(default="ANN")


class FieldSchema(BaseModel):
    id: str
    title: str
    type: FieldType
    required: bool = False
    default: str | None = None
    item_type: str | None = None
    columns: list[str] | None = None
    values: list[str] | None = None
    instructions: str | None = None


class HeaderFieldSchema(BaseModel):
    field: str
    type: FieldType = "text"
    required: bool = False
    default: str | None = None
    values: list[str] | None = None


class HeaderSchema(BaseModel):
    document_control: list[HeaderFieldSchema] = Field(default_factory=list)
    approval_signatures: bool = False
    table_of_contents: bool = False


class OutputSchema(BaseModel):
    presentation: Literal["table", "prose"] = "table"
    columns: list[str] = Field(default_factory=list)


class RequirementFilterSchema(BaseModel):
    req_type: str | None = None
    groups: list[str] | None = None


class SectionSchema(BaseModel):
    id: str
    title: str
    type: SectionType = "free_text"
    required: bool = True
    annexure: bool = False
    description: str | None = None
    fields: list[FieldSchema] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    requirement_filter: RequirementFilterSchema | None = None
    output: OutputSchema | None = None
    instructions: str | None = None


class TemplateSchema(BaseModel):
    template_id: str
    doc_type: Literal["SRS", "SDD", "ICD", "STP", "STR"]
    name: str
    version: str
    organization: str | None = None
    numbering: NumberingScheme = Field(default_factory=NumberingScheme)
    header: HeaderSchema = Field(default_factory=HeaderSchema)
    sections: list[SectionSchema]

    @property
    def required_section_ids(self) -> list[str]:
        return [s.id for s in self.sections if s.required]
