from rag.rag_chain import answer_query , client
# from embeddings.embedder import ingest_doc
# from ingestion.load_files import load_all_data
res= answer_query("what are the food that i can try in sri lanka")
print(res["result"])
client.close()
# if __name__ == "__main__":
#     idoc = load_all_data("data/")
#     print(len(idoc))
