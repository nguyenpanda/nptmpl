import yaml
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from rich.console import Console

from nptmpl.core.errors import ValidationError, NptmplError

logger = logging.getLogger("nptmpl.metadata")
console = Console()

@dataclass(frozen=True)
class TemplateMetadata:
    """Immutable value object for template configuration and identity."""
    name: str
    version: str
    author: str
    description: str
    languages: List[str]
    email: Optional[str] = None
    license: Optional[str] = None
    url: Optional[str] = None
    added_date: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    ignore: List[str] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)
    hooks: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateMetadata":
        return cls(
            name=str(data.get("name", "")),
            version=str(data.get("version", "1.0.0")),
            author=str(data.get("author", "Unknown")),
            description=str(data.get("description", "")),
            languages=list(data.get("languages", [])),
            email=data.get("email"),
            license=data.get("license"),
            url=data.get("url"),
            added_date=data.get("added_date"),
            tags=list(data.get("tags", [])),
            ignore=list(data.get("ignore", [])),
            variables=dict(data.get("variables", {})),
            hooks=list(data.get("hooks", []))
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "name": self.name, "version": self.version, "author": self.author,
            "email": self.email, "description": self.description, "languages": self.languages,
            "license": self.license, "url": self.url, "added_date": self.added_date,
            "tags": self.tags, "ignore": self.ignore, "variables": self.variables, "hooks": self.hooks
        }
        return {k: v for k, v in data.items() if v is not None}

    def copy_with(self, **kwargs) -> "TemplateMetadata":
        from dataclasses import replace
        return replace(self, **kwargs)

class Version:
    """Semantic Versioning implementation with comparison logic."""
    REGEX = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<pre>(?:0|[1-9]\d*|\d*[a-zA-Z-][a-zA-Z0-9-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][a-zA-Z0-9-]*))*))?(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")

    def __init__(self, v_str: str):
        m = self.REGEX.match(v_str)
        if not m: raise ValidationError(f"Invalid SemVer format: {v_str}")
        self.v_str, self.major, self.minor, self.patch, self.pre = v_str, int(m.group("major")), int(m.group("minor")), int(m.group("patch")), m.group("pre")

    @property
    def tuple(self) -> Tuple[int, int, int]: return (self.major, self.minor, self.patch)

    @staticmethod
    def is_valid(v_str: str) -> bool: return bool(Version.REGEX.match(v_str))

    def __lt__(self, o: "Version") -> bool:
        if self.tuple != o.tuple: return self.tuple < o.tuple
        if self.pre and not o.pre: return True
        if not self.pre and o.pre: return False
        return self.pre < o.pre if self.pre and o.pre else False

    def __eq__(self, o: object) -> bool: return isinstance(o, Version) and self.tuple == o.tuple and self.pre == o.pre
    def __le__(self, o: "Version") -> bool: return self == o or self < o
    def __gt__(self, o: "Version") -> bool: return not (self <= o)
    def __ge__(self, o: "Version") -> bool: return self == o or self > o
    def __str__(self) -> str: return self.v_str

class MetadataManager:
    """Parsing and validation for .nptmpl descriptor files."""
    REQUIRED = ["version", "author", "description", "languages"]

    @staticmethod
    def create_default(path: Path, defaults: Optional[Dict[str, Any]] = None) -> None:
        if (path / ".nptmpl").exists(): raise ValidationError(".nptmpl already exists")
        d = defaults or {}
        content = {
            "name": path.name, "version": d.get("version", "1.0.0"), "author": d.get("author", "Unknown"),
            "email": d.get("email", ""), "description": d.get("description", "A new template."),
            "languages": d.get("languages", ["python"]), "license": d.get("license", "MIT"),
            "url": d.get("url", ""), "tags": d.get("tags", ["starter"]),
            "ignore": d.get("ignore", [".git", ".venv", "__pycache__"]),
            "variables": {"project_name": "Project Name"}, "hooks": ["echo 'Success'"]
        }
        with open(path / ".nptmpl", "w", encoding="utf-8") as f: yaml.dump(content, f, sort_keys=False)

    @staticmethod
    def edit_interactive(path: Path):
        import questionary
        meta = MetadataManager.load(path)
        try:
            def ask(p, c, m=False):
                r = questionary.text(p, default=str(c) if c else "").ask()
                if r is None: raise KeyboardInterrupt()
                return r.strip() if r.strip() or not m else c
            
            name = ask("Name:", meta.name)
            version = ask("Version:", meta.version, True)
            author = ask("Author:", meta.author, True)
            email = ask("Email:", meta.email)
            desc = ask("Description:", meta.description, True)
            langs = [l.strip() for l in ask("Languages (CSV):", ", ".join(meta.languages), True).split(",") if l.strip()]
            
            new_meta = meta.copy_with(name=name, version=version, author=author, email=email, description=desc, languages=langs)
            if questionary.confirm("Save?").ask():
                MetadataManager.save(path, new_meta)
                console.print("[bold green]Updated.[/bold green]")
        except KeyboardInterrupt: console.print("\n[yellow]Cancelled.[/yellow]")

    @staticmethod
    def load(path: Path) -> TemplateMetadata:
        f = path / ".nptmpl"
        if not f.exists(): raise ValidationError(f"Missing .nptmpl at {path}")
        with open(f, "r", encoding="utf-8") as stream: data = yaml.safe_load(stream)
        if not isinstance(data, dict): raise ValidationError("Invalid YAML format")
        for field in MetadataManager.REQUIRED:
            if field not in data: raise ValidationError(f"Missing mandatory field in .nptmpl: {field}")
        if not Version.is_valid(str(data["version"])): raise ValidationError(f"Invalid version format in .nptmpl: {data['version']}")
        return TemplateMetadata.from_dict(data)

    @staticmethod
    def save(path: Path, meta: TemplateMetadata) -> None:
        with open(path / ".nptmpl", "w", encoding="utf-8") as f: yaml.dump(meta.to_dict(), f, sort_keys=False)
