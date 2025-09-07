from langchain_mistralai import ChatMistralAI
from langchain_community.vectorstores import Weaviate
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_weaviate import WeaviateVectorStore
from utils.config import WEAVIATE_URL, WEAVIATE_API_KEY, MISTRAL_API_KEY
import weaviate
from weaviate.classes.init import Auth

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_URL,
    auth_credentials=Auth.api_key(WEAVIATE_API_KEY),
)


embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


vectorstore = WeaviateVectorStore(
    client=client,
    index_name="DocumentChunk",
    text_key="text",
    embedding=embeddings,
)

retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)


llm = ChatMistralAI(
    api_key=MISTRAL_API_KEY,
    model="mistral-medium",
    temperature=0,
)


qa_chain = RetrievalQA.from_chain_type(
    llm,
    retriever=retriever,
    return_source_documents=True,
)

def answer_query(query: str):
    return qa_chain({"query": query})

