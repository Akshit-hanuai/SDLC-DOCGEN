from dataclasses import dataclass, field


@dataclass
class Block:
    heading: str
    level: int
    text: str

    def path(self) -> str:
        return self.heading.strip() if self.heading.strip() else f"(body-{self.level})"


@dataclass
class ParsedDocument:
    filename: str
    doc_type: str
    text: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class RequirementExtract:
    req_id: str
    text: str
    context: str
    source: str
    req_type: str = "functional"
    extra: dict = field(default_factory=dict)


@dataclass
class MoMRecord:
    kind: str
    text: str
    owner: str | None = None
    due: str | None = None
    req_ids: list[str] = field(default_factory=list)


@dataclass
class CodeArtifact:
    artifact_id: str
    name: str
    kind: str
    module: str
    description: str
    req_ids: list[str] = field(default_factory=list)


@dataclass
class CodeAnalysis:
    language: str
    modules: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    artifacts: list[CodeArtifact] = field(default_factory=list)
    endpoints: list[CodeArtifact] = field(default_factory=list)
    messages: list[CodeArtifact] = field(default_factory=list)
