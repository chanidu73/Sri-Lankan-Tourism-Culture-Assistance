import requests
from embeddings.weaviate_client import get_client
from utils.config import MISTRAL_API_KEY


def query_rag(question , top_k=3):
    client = get_client()
    results = client.query.get("TourismDoc" , ['text' , "source"])\
    .with_near_text({'concepts': [question]})\
    .with_limit(top_k).do()


    context = '\n'.join([d['text'] for d in results['data']['get']['TourismDoc']])

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization":f"Bearer {MISTRAL_API_KEY}"}

    payload = {
        "model":"mistral-tiny", 
        "messages":[
            {"role" : "system" , "content":"You are a tourism and culture assistant."},
            {"role":"user" , "content" :f"{context}: \n Question {question}"}

        ] ,
    }
    resp = requests.post(url , json=payload , headers=headers)
    return resp.json()['choices'][0]["message"]["content"]