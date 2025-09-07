from langchain.text_splitter import RecursiveCharacterTextSplitter
from nltk.tokenize import sent_tokenize
import nltk
nltk.download("punkt")


def chunk_docs(docs , chunk_size=800 , overlap=100):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = chunk_size,
        chunk_overlap= overlap
    )
    return splitter.split_documents(docs)


def chunk_text(text , max_tokens=400 , overlap_tokens=80):
    sentences = sent_tokenize(text)
    chunks , cur , cur_len = [],[],0
    for s in sentences:
        toks = len(s.split())
        if cur_len + toks > max_tokens and cur:
            chunks.append(" ".join(cur))
            overlap = cur[-overlap_tokens:]if overlap_tokens else []
            cur = overlap
            cur_len = len(" ".join(cur).split())
        cur.append(s)
        cur_len += toks
        if cur:
            chunks.append(" ".join(cur))
        return chunks 
