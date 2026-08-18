from __future__ import annotations

"""
Module 1: Advanced Chunking Strategies
=======================================
Implement semantic, hierarchical, và structure-aware chunking.
So sánh với basic chunking (baseline) để thấy improvement.

Test: pytest tests/test_m1.py
"""

import os, sys, glob, re
from dataclasses import dataclass, field

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DATA_DIR, HIERARCHICAL_PARENT_SIZE, HIERARCHICAL_CHILD_SIZE,
                    SEMANTIC_THRESHOLD)


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)
    parent_id: str | None = None


def _extract_pdf_text(path: str) -> str:
    """Extract text layer từ PDF. Trả về "" nếu PDF là scan ảnh (không có text)."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def load_documents(data_dir: str = DATA_DIR) -> list[dict]:
    """Load tất cả markdown và PDF (có text layer) từ data/. (Đã implement sẵn)

    - .md: đọc trực tiếp.
    - .pdf: trích text layer bằng pypdf. PDF scan ảnh (không có text) bị bỏ qua
      kèm cảnh báo — RAG text-based không xử lý được scan nếu chưa OCR.
    """
    docs = []
    for fp in sorted(glob.glob(os.path.join(data_dir, "*.md"))):
        with open(fp, encoding="utf-8") as f:
            docs.append({"text": f.read(), "metadata": {"source": os.path.basename(fp)}})

    for fp in sorted(glob.glob(os.path.join(data_dir, "*.pdf"))):
        text = _extract_pdf_text(fp)
        if text:
            docs.append({"text": text, "metadata": {"source": os.path.basename(fp)}})
        else:
            print(f"  ⚠️  Bỏ qua {os.path.basename(fp)}: PDF scan ảnh, không có text layer (cần OCR).")

    return docs


# ─── Baseline: Basic Chunking (để so sánh) ──────────────


def chunk_basic(text: str, chunk_size: int = 500, metadata: dict | None = None) -> list[Chunk]:
    """
    Basic chunking: split theo paragraph (\\n\\n).
    Đây là baseline — KHÔNG phải mục tiêu của module này.
    (Đã implement sẵn)
    """
    metadata = metadata or {}
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for i, para in enumerate(paragraphs):
        if len(current) + len(para) > chunk_size and current:
            chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
    return chunks


# ─── Strategy 1: Semantic Chunking ───────────────────────


_SEMANTIC_MODEL = None


def _get_semantic_model():
    global _SEMANTIC_MODEL
    if _SEMANTIC_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _SEMANTIC_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _SEMANTIC_MODEL


def chunk_semantic(text: str, threshold: float = SEMANTIC_THRESHOLD,
                   metadata: dict | None = None) -> list[Chunk]:
    """
    Split text by sentence similarity — nhóm câu cùng chủ đề.
    Tốt hơn basic vì không cắt giữa ý.
    """
    metadata = metadata or {}
    if not text.strip():
        return []

    from numpy import dot
    from numpy.linalg import norm

    # Split text into sentences
    raw_sentences = re.split(r'(?<=[.!?])\s+|\n\n+', text)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    if not sentences:
        return [Chunk(text=text.strip(), metadata={**metadata, "strategy": "semantic", "chunk_index": 0})]
    if len(sentences) == 1:
        return [Chunk(text=sentences[0], metadata={**metadata, "strategy": "semantic", "chunk_index": 0})]

    model = _get_semantic_model()
    embeddings = model.encode(sentences)

    groups = [[sentences[0]]]
    for i in range(1, len(sentences)):
        a = embeddings[i - 1]
        b = embeddings[i]
        sim = dot(a, b) / (norm(a) * norm(b) + 1e-9)
        if sim < threshold:
            groups.append([sentences[i]])
        else:
            groups[-1].append(sentences[i])

    chunks = []
    for idx, g in enumerate(groups):
        joined_text = " ".join(g).strip()
        if joined_text:
            chunks.append(Chunk(text=joined_text, metadata={**metadata, "strategy": "semantic", "chunk_index": idx}))
    return chunks


# ─── Strategy 2: Hierarchical Chunking ──────────────────


def chunk_hierarchical(text: str, parent_size: int = HIERARCHICAL_PARENT_SIZE,
                       child_size: int = HIERARCHICAL_CHILD_SIZE,
                       metadata: dict | None = None) -> tuple[list[Chunk], list[Chunk]]:
    """
    Parent-child hierarchy: retrieve child (precision) → return parent (context).
    Đây là default recommendation cho production RAG.

    Returns:
        (parents, children) — mỗi child có parent_id link đến parent.
    """
    metadata = metadata or {}
    if not text.strip():
        return ([], [])

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    parents: list[Chunk] = []
    children: list[Chunk] = []

    current_parent = ""
    for para in paragraphs:
        if len(current_parent) + len(para) + 2 > parent_size and current_parent:
            pid = f"parent_{len(parents)}"
            parents.append(Chunk(
                text=current_parent.strip(),
                metadata={**metadata, "chunk_type": "parent", "parent_id": pid}
            ))
            current_parent = ""
        current_parent += (para + "\n\n")

    if current_parent.strip():
        pid = f"parent_{len(parents)}"
        parents.append(Chunk(
            text=current_parent.strip(),
            metadata={**metadata, "chunk_type": "parent", "parent_id": pid}
        ))

    for p in parents:
        pid = p.metadata.get("parent_id")
        p_text = p.text
        sub_units = re.split(r'(?<=[.!?])\s+|\n+', p_text)
        sub_units = [s.strip() for s in sub_units if s.strip()]
        if not sub_units:
            sub_units = [p_text]

        current_child = ""
        child_chunks_for_parent = []
        for unit in sub_units:
            while len(unit) > child_size:
                split_point = child_size
                space_idx = unit.rfind(" ", 0, split_point)
                if space_idx > child_size // 2:
                    split_point = space_idx
                part = unit[:split_point].strip()
                unit = unit[split_point:].strip()
                if current_child:
                    child_chunks_for_parent.append(current_child.strip())
                    current_child = ""
                if part:
                    child_chunks_for_parent.append(part)

            if len(current_child) + len(unit) + 1 > child_size and current_child:
                child_chunks_for_parent.append(current_child.strip())
                current_child = ""
            current_child += (unit + " ")

        if current_child.strip():
            child_chunks_for_parent.append(current_child.strip())

        for c_idx, c_text in enumerate(child_chunks_for_parent):
            children.append(Chunk(
                text=c_text,
                metadata={**metadata, "chunk_type": "child", "child_index": c_idx, "parent_id": pid},
                parent_id=pid
            ))

    return (parents, children)


# ─── Strategy 3: Structure-Aware Chunking ────────────────


def chunk_structure_aware(text: str, metadata: dict | None = None) -> list[Chunk]:
    """
    Parse markdown headers → chunk theo logical structure.
    Giữ nguyên tables, code blocks, lists — không cắt giữa chừng.
    """
    metadata = metadata or {}
    if not text.strip():
        return []

    tokens = re.split(r'(^#{1,6}\s+.+$)', text, flags=re.MULTILINE)
    chunks = []
    current_header = ""
    current_content = ""

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if re.match(r'^#{1,6}\s+', token):
            if current_content.strip() or current_header:
                full_text = f"{current_header}\n\n{current_content}".strip() if current_header else current_content.strip()
                if full_text:
                    chunks.append(Chunk(
                        text=full_text,
                        metadata={**metadata, "section": current_header, "strategy": "structure", "chunk_index": len(chunks)}
                    ))
                current_content = ""
            current_header = token
        else:
            current_content += (token + "\n\n")

    if current_content.strip() or current_header:
        full_text = f"{current_header}\n\n{current_content}".strip() if current_header else current_content.strip()
        if full_text:
            chunks.append(Chunk(
                text=full_text,
                metadata={**metadata, "section": current_header, "strategy": "structure", "chunk_index": len(chunks)}
            ))

    return chunks


# ─── A/B Test: Compare All Strategies ────────────────────


def compare_strategies(documents: list[dict]) -> dict:
    """
    Run all strategies on documents and compare.
    (Đã implement sẵn — sẽ hoạt động khi bạn implement 3 strategies ở trên)
    """
    def _stats(chunk_list):
        lengths = [len(c.text) for c in chunk_list]
        if not lengths:
            return {"count": 0, "avg_len": 0, "min_len": 0, "max_len": 0}
        return {
            "count": len(lengths),
            "avg_len": round(sum(lengths) / len(lengths)),
            "min_len": min(lengths),
            "max_len": max(lengths),
        }

    all_text = "\n\n".join(d["text"] for d in documents)
    meta = {"source": "all"}

    basic = chunk_basic(all_text, metadata=meta)
    semantic = chunk_semantic(all_text, metadata=meta)
    parents, children = chunk_hierarchical(all_text, metadata=meta)
    structure = chunk_structure_aware(all_text, metadata=meta)

    results = {
        "basic": _stats(basic),
        "semantic": _stats(semantic),
        "hierarchical": {**_stats(children), "parents": len(parents)},
        "structure": _stats(structure),
    }

    print(f"{'Strategy':<15} {'Chunks':>7} {'Avg':>5} {'Min':>5} {'Max':>5}")
    for name, s in results.items():
        print(f"{name:<15} {s['count']:>7} {s['avg_len']:>5} {s['min_len']:>5} {s['max_len']:>5}")

    return results


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} documents")
    results = compare_strategies(docs)
    for name, stats in results.items():
        print(f"  {name}: {stats}")
