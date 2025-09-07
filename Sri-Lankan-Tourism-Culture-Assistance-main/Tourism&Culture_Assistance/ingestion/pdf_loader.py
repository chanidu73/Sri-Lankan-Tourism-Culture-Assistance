from langchain.document_loaders import PyPDFLoader
import os
def load_pdfs(pdf_dir:str="data/"):
    docs=[]
    for file in os.listdir(pdf_dir):
        if file.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(pdf_dir , file))
            docs.extend(loader.load())
    return docs