# place near your existing retriever/llm setup in rag_chain.py
from langchain import LLMChain, PromptTemplate
from typing import List
from rag.rag_chain import llm, retriever  

PROMPT = """You are a helpful, concise travel assistant with expertise in Sri Lanka.

You are given retrieved source passages and for each source a list of image URLs (and optional captions). IMPORTANT: you cannot view the images themselves. Use the textual content and any available image captions or filenames to inform your answer. If you must infer visual details, clearly mark these as inferred (e.g., "inferred from caption/filename"). Always provide:

1. A short, accurate answer to the user's question.
2. When helpful, list recommended image(s) the user should open for more info, labeled [Image 1], [Image 2], etc., with the image URL.
3. If an image URL has an associated caption, include that caption beside the image link.
4. If no caption exists, you may mention the filename or the URL text briefly but be explicit that you did not view it.
5. When giving itineraries or place suggestions, refer to images as visual references only (do not pretend to have seen them).

=== Retrieved sources (each source includes Title, Text, and Images) ===
{context}

=== Question ===
{question}

Answer succinctly, then (if images are relevant) add a short "Images to inspect" list with numbered links and optional captions.
"""

prompt = PromptTemplate(input_variables=["context", "question"], template=PROMPT)
chain = LLMChain(llm=llm, prompt=prompt)  # llm is your ChatMistralAI instance

def _build_context_from_docs(docs: List):
    """
    docs: list of LangChain Document objects (doc.page_content, doc.metadata)
    Returns a single string that merges title, snippet, and image urls/captions.
    """
    parts = []
    for i, d in enumerate(docs):
        title = d.metadata.get("title") or f"Source_{i+1}"
        text = (d.page_content or "").strip()
        images = d.metadata.get("images") or []
        # images may be list of strings or list of dicts [{"url":..., "caption":...}]
        img_lines = []
        for j, img in enumerate(images):
            if isinstance(img, dict):
                url = img.get("url")
                caption = img.get("caption") or img.get("alt") or ""
            else:
                url = img
                caption = ""
            label = f"[Image {j+1}]"
            if caption:
                img_lines.append(f"{label} {caption} — {url}")
            else:
                img_lines.append(f"{label} {url}")
        imgs_text = "\n".join(img_lines) if img_lines else "None"
        parts.append(f"Source {i+1} — Title: {title}\nText: {text}\nImages:\n{imgs_text}\n---")
    return "\n\n".join(parts)

def answer_query_with_images(query: str):
    # 1) retrieve docs (k as you like)
    docs = retriever.get_relevant_documents(query)  # retriever from your setup
    context = _build_context_from_docs(docs)
    # 2) call LLM chain
    answer = chain.run({"context": context, "question": query})
    # 3) return answer plus docs for UI rendering
    return {"result": answer, "source_documents": docs}
