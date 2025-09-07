import re
from typing import List, Dict

_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

def sentence_split(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    sents = _SENT_SPLIT_RE.split(text)
    return [s.strip() for s in sents if s.strip()]

def chunk_text(text: str, max_tokens: int = 400, overlap_tokens: int = 80) -> List[str]:
    """
    Split `text` into chunks of ~max_tokens words, with `overlap_tokens` overlap between chunks.
    This uses a simple word-count approximation (fast). For exact model tokens, use a tokenizer.
    """
    sentences = sentence_split(text)
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for s in sentences:
        toks = len(s.split())
        # if adding this sentence would exceed max, finalize current chunk
        if cur and (cur_len + toks > max_tokens):
            chunks.append(" ".join(cur))

            # prepare overlap: take last `overlap_tokens` words of current chunk as new start
            if overlap_tokens > 0:
                words = " ".join(cur).split()
                overlap_words = words[-overlap_tokens:] if len(words) >= overlap_tokens else words
                cur = overlap_words[:]  # new current chunk starts with overlap
                cur_len = len(cur)
            else:
                cur = []
                cur_len = 0

        # add this sentence to current chunk
        cur.append(s)
        cur_len += toks


    if cur:
        chunks.append(" ".join(cur))

    return chunks

def chunk_docs(docs: List[Dict], max_tokens: int = 400, overlap_tokens: int = 80) -> List[Dict]:
    """
    Convert list of docs (each {'id','title','text'}) into list of chunk dicts:
    {'source_id','title','chunk_index','text'}
    """
    out: List[Dict] = []
    for doc in docs:
        text = doc.get("text", "") or ""
        for i, chunk in enumerate(chunk_text(text, max_tokens=max_tokens, overlap_tokens=overlap_tokens)):
            out.append({
                "source_id": doc.get("id"),
                "title": doc.get("title"),
                "chunk_index": i,
                "text": chunk
            })
    return out
