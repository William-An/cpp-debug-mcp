"""LSP message construction helpers and response parsers."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiagnosticInfo:
    file: str
    line: int
    column: int
    end_line: int
    end_column: int
    severity: str
    message: str
    source: str

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
            "message": self.message,
            "source": self.source,
        }


@dataclass
class LocationInfo:
    file: str
    line: int
    column: int

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "column": self.column}


@dataclass
class HoverInfo:
    contents: str
    language: str = ""

    def to_dict(self) -> dict:
        return {"contents": self.contents, "language": self.language}


@dataclass
class SymbolInfo:
    name: str
    kind: int
    line: int
    column: int
    end_line: int
    end_column: int
    children: list = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "kind": SYMBOL_KIND_NAMES.get(self.kind, str(self.kind)),
            "line": self.line,
            "column": self.column,
        }
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        return result


SYMBOL_KIND_NAMES = {
    1: "File", 2: "Module", 3: "Namespace", 4: "Package", 5: "Class",
    6: "Method", 7: "Property", 8: "Field", 9: "Constructor", 10: "Enum",
    11: "Interface", 12: "Function", 13: "Variable", 14: "Constant",
    15: "String", 16: "Number", 17: "Boolean", 18: "Array", 19: "Object",
    20: "Key", 21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
    25: "Operator", 26: "TypeParameter",
}

SEVERITY_NAMES = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def file_uri(path: str) -> str:
    """Convert a file path to a file:// URI."""
    return Path(path).resolve().as_uri()


def uri_to_path(uri: str) -> str:
    """Convert a file:// URI to a path."""
    if uri.startswith("file://"):
        return uri[7:]
    return uri


def make_initialize_params(root_path: str) -> dict:
    """Construct initialize request params."""
    return {
        "processId": None,
        "rootUri": file_uri(root_path),
        "capabilities": {
            "textDocument": {
                "hover": {"contentFormat": ["plaintext", "markdown"]},
                "definition": {"linkSupport": False},
                "references": {},
                "documentSymbol": {
                    "hierarchicalDocumentSymbolSupport": True,
                },
                "signatureHelp": {
                    "signatureInformation": {
                        "parameterInformation": {"labelOffsetSupport": True},
                    },
                },
                "publishDiagnostics": {"relatedInformation": True},
            },
        },
    }


def make_did_open(file_path: str, content: str, language_id: str = "cpp") -> dict:
    """Construct textDocument/didOpen notification params."""
    return {
        "textDocument": {
            "uri": file_uri(file_path),
            "languageId": language_id,
            "version": 1,
            "text": content,
        }
    }


def make_text_document_position(file_path: str, line: int, column: int) -> dict:
    """Construct TextDocumentPositionParams (0-indexed line/column)."""
    return {
        "textDocument": {"uri": file_uri(file_path)},
        "position": {"line": line, "character": column},
    }


def make_reference_params(file_path: str, line: int, column: int) -> dict:
    """Construct ReferenceParams."""
    params = make_text_document_position(file_path, line, column)
    params["context"] = {"includeDeclaration": True}
    return params


def parse_diagnostic(raw: dict, file_path: str = "") -> DiagnosticInfo:
    """Parse a single LSP diagnostic."""
    range_ = raw.get("range", {})
    start = range_.get("start", {})
    end = range_.get("end", {})
    return DiagnosticInfo(
        file=file_path,
        line=start.get("line", 0),
        column=start.get("character", 0),
        end_line=end.get("line", 0),
        end_column=end.get("character", 0),
        severity=SEVERITY_NAMES.get(raw.get("severity", 0), "unknown"),
        message=raw.get("message", ""),
        source=raw.get("source", ""),
    )


def parse_hover(raw: dict | None) -> HoverInfo | None:
    """Parse a hover response."""
    if not raw:
        return None
    contents = raw.get("contents", "")
    if isinstance(contents, dict):
        return HoverInfo(
            contents=contents.get("value", ""),
            language=contents.get("language", ""),
        )
    if isinstance(contents, str):
        return HoverInfo(contents=contents)
    if isinstance(contents, list):
        parts = []
        lang = ""
        for item in contents:
            if isinstance(item, dict):
                parts.append(item.get("value", ""))
                lang = item.get("language", lang)
            else:
                parts.append(str(item))
        return HoverInfo(contents="\n".join(parts), language=lang)
    return None


def parse_location(raw: dict) -> LocationInfo:
    """Parse a Location object."""
    uri = raw.get("uri", raw.get("targetUri", ""))
    range_ = raw.get("range", raw.get("targetSelectionRange", {}))
    start = range_.get("start", {})
    return LocationInfo(
        file=uri_to_path(uri),
        line=start.get("line", 0),
        column=start.get("character", 0),
    )


def parse_document_symbol(raw: dict) -> SymbolInfo:
    """Parse a DocumentSymbol."""
    range_ = raw.get("range", raw.get("location", {}).get("range", {}))
    start = range_.get("start", {})
    end = range_.get("end", {})
    children = [parse_document_symbol(c) for c in raw.get("children", [])]
    return SymbolInfo(
        name=raw.get("name", ""),
        kind=raw.get("kind", 0),
        line=start.get("line", 0),
        column=start.get("character", 0),
        end_line=end.get("line", 0),
        end_column=end.get("character", 0),
        children=children,
    )
