"""Private one-shot PDF subprocess protocol; never accepts model arguments."""

import json
import sys

from wisetodo.files.model_content import pdf_model_content
from wisetodo.files.pdf import PdfReadError
from wisetodo.files.pdf_extract import extract_pdf
from wisetodo.files.references import FileReferenceError, FileReferences


def main() -> None:
    try:
        path = json.loads(sys.stdin.buffer.read(32769))
        if not isinstance(path, str):
            raise ValueError
        references = FileReferences([path])
        reference = references.descriptions()[0]["file_ref"]
        result = pdf_model_content(extract_pdf(references, reference))
    except (PdfReadError, FileReferenceError, ValueError, OSError):
        # A failed read is usable information for a clarification, not book facts.
        result = {
            "error": "pdf_unavailable",
            "notice": "无法解析此 PDF；请提供未加密的有效 PDF 或粘贴真实目录。",
        }
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
