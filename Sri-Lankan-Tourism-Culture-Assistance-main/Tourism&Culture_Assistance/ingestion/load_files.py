from pathlib import Path
import json
from PyPDF2 import PdfReader


def load_pdfs(folder):
    docs = []
    for pdf_file in Path(folder).glob("*.pdf"):
        reader = PdfReader(pdf_file)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        docs.append({"id": pdf_file.stem,
                      "title": pdf_file.stem, 
                      "text": text,
                      "images": []})
    if docs is None: print("no PDF files ")
    return docs

import json
from pathlib import Path

def load_jsonl(folder):
    docs = []
    for jsonl_file in Path(folder).glob("*.jsonl"):
        print("Processing jsonl files:")
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                if not line.strip():
                    continue  
                try:
                    data = json.loads(line)
                    docs.append({
                        "id": f"{jsonl_file.stem}_{i}",
                        "title": data.get("title", jsonl_file.stem),
                        "text": data.get("text", "") or data.get("text_snippet" , ""),
                        "images": data.get("downloaded_images", []),
                    })
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON in {jsonl_file} at line {i}")
    return docs
    

def load_json(folder):
    docs = []
    for json_file in Path(folder).glob("*.json"):
        with open(json_file, "r") as f:
            data = json.load(f)
            docs.append(
                {
                    "id": json_file.stem, 
                    "title": data.get("title", json_file.stem),
                    "text": data.get("text_snippet", ""),
                    "images":data.get("images", [])
                    }
                      )
    return docs


def load_all_data(path):
    docs = []
    docs.extend(load_pdfs(path))
    docs.extend(load_json(path))
    docs.extend(load_jsonl(path))
    return docs