import os, json, time
from typing import List, Dict
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import faiss, numpy as np
from sentence_transformers import SentenceTransformer

load_dotenv()

# config
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")
TOP_K = int(os.getenv("TOP_K", "4"))

INDEX_PATH = "storage/index.faiss"
META_PATH = "storage/meta.json"

# load index and metadata
index = faiss.read_index(INDEX_PATH)
with open(META_PATH, "r", encoding="utf-8") as f:
    meta = json.load(f)["meta"]

# load embedding model
embedder = SentenceTransformer(EMBED_MODEL)

# API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")

if OPENAI_API_KEY:
    from openai import OpenAI
    oai = OpenAI(api_key=OPENAI_API_KEY)
if GOOGLE_API_KEY:
    import google.generativeai as genai
    genai.configure(api_key=GOOGLE_API_KEY)
if ANTHROPIC_API_KEY:
    import anthropic
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI()

class AskReq(BaseModel):
    question: str

class AskRes(BaseModel):
    answer: str
    sources: List[Dict[str, str]]

@app.get("/health")
async def health():
    return {"ok": True}


def retrieve(q: str, top_k: int = TOP_K):
    # encode question
    q_emb = embedder.encode([f"query: {q}"], normalize_embeddings=True)
    # search in faiss
    D, I = index.search(np.asarray(q_emb, dtype="float32"), top_k)
    
    items = []
    for idx in I[0]:
        m = meta[idx]
        items.append({"url": m["url"], "title": m["title"], "text": m.get("text", "")})
    return items


def build_context(items):
    blocks = []
    for it in items:
        snippet = (it.get("text") or "")[:800]  # truncate to 800 chars
        blocks.append(f"[SOURCE] {it['title']} ({it['url']})\n{snippet}")
    return "\n\n".join(blocks)


def is_greeting_or_chitchat(question: str) -> tuple:
    # check if user is just saying hi or thanks
    q_lower = question.lower().strip()
    
    greetings = ['hi', 'hello', 'xin chào', 'chào', 'hey', 'chào bạn', 'xin chao']
    if any(g in q_lower for g in greetings) and len(q_lower.split()) <= 3:
        return (True, "Xin chào! Tôi là trợ lý AI của Mitek. Tôi có thể giúp bạn tìm hiểu về các giải pháp CNTT, phần mềm, dịch vụ công nghệ và các thông tin khác. Bạn muốn hỏi gì ạ?")
    
    thanks = ['cảm ơn', 'thank', 'thanks', 'cám ơn', 'cam on']
    if any(t in q_lower for t in thanks) and len(q_lower.split()) <= 5:
        return (True, "Rất vui được giúp đỡ bạn! Nếu có câu hỏi gì khác, đừng ngại hỏi nhé.")
    
    return (False, None)


def call_llm(question: str, context: str) -> str:
    # build prompt for LLM
    prompt = (
        "Bạn là trợ lý AI tư vấn chuyên nghiệp về công nghệ thông tin và phần mềm của Mitek.\n\n"
        "Hướng dẫn:\n"
        "- Trả lời ngắn gọn, thân thiện, chuyên nghiệp (60-100 từ)\n"
        "- Dựa trên thông tin được cung cấp bên dưới\n"
        "- KHÔNG chèn (SOURCE) hay trích dẫn URL trong câu trả lời\n"
        "- Nếu câu hỏi không liên quan đến công nghệ/phần mềm/CNTT, lịch sự từ chối và gợi ý hỏi về các chủ đề liên quan\n"
        "- Nếu thiếu thông tin, hướng dẫn khách hàng liên hệ để biết thêm chi tiết\n\n"
        f"Thông tin tham khảo:\n{context}\n\n"
        f"Câu hỏi: {question}\n\n"
        "Trả lời:"
    )
    try:
        if ANTHROPIC_API_KEY:
            msg = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        if OPENAI_API_KEY:
            resp = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        if GOOGLE_API_KEY:
            model = genai.GenerativeModel("gemini-2.5-flash")
            resp = model.generate_content(prompt)
            return resp.text.strip()
    except Exception as e:
        print(f"LLM Error: {type(e).__name__}: {e}")
    return "Chưa có trong tài liệu hoặc LLM không khả dụng."


def tfidf_fallback(question: str):
    # fallback to tfidf if llm fails
    try:
        import pandas as pd
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        df = pd.read_csv("data/faq.csv", encoding="utf-8")
        if df.empty:
            return None, []
        
        df['combined'] = df['title'].fillna('') + ' ' + df['body'].fillna('')
        texts = df['combined'].tolist()
        
        vectorizer = TfidfVectorizer(max_features=500)
        tfidf_matrix = vectorizer.fit_transform(texts + [question])
        
        similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
        best_idx = similarities.argmax()
        
        if similarities[best_idx] > 0.01:
            row = df.iloc[best_idx]
            answer = str(row['body'])[:240].strip()
            sources = [{"url": str(row['url']), "title": str(row['title'])}]
            return answer, sources
    except Exception:
        pass
    return None, []


@app.post("/ask", response_model=AskRes)
async def ask(req: AskReq):
    t0 = time.time()
    
    # check for greetings first
    is_chitchat, chitchat_response = is_greeting_or_chitchat(req.question)
    if is_chitchat:
        rec = {"q": req.question, "t": time.time(), "sources": [], "latency": time.time()-t0, "type": "chitchat"}
        os.makedirs("storage", exist_ok=True)
        with open("storage/log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {"answer": chitchat_response, "sources": []}
    
    # normal flow: retrieve -> llm
    items = retrieve(req.question)
    ctx = build_context(items)
    ans = call_llm(req.question, ctx)
    
    # use tfidf if llm failed
    if not ans or not ans.strip() or any(msg in ans for msg in ["Chưa có trong tài liệu", "không khả dụng"]):
        fallback_ans, fallback_sources = tfidf_fallback(req.question)
        if fallback_ans:
            ans = fallback_ans
            if fallback_sources:
                items = [{"url": s["url"], "title": s["title"], "text": ""} for s in fallback_sources]
    
    rec = {"q": req.question, "t": time.time(), "sources": items, "latency": time.time()-t0}
    os.makedirs("storage", exist_ok=True)
    with open("storage/log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"answer": ans, "sources": [{"url": i["url"], "title": i["title"]} for i in items]}


@app.get("/metrics")
async def metrics():
    import collections
    cnt = collections.Counter()
    lat = []
    try:
        with open("storage/log.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                lat.append(rec.get("latency", 0))
                q = (rec.get("q", "") or "").lower()
                if any(k in q for k in ["giá", "price", "báo giá"]):
                    cnt["pricing"] += 1
                elif any(k in q for k in ["bảo hành", "warranty"]):
                    cnt["warranty"] += 1
                elif any(k in q for k in ["hướng dẫn", "manual", "setup"]):
                    cnt["howto"] += 1
                else:
                    cnt["other"] += 1
    except FileNotFoundError:
        pass
    p95 = float(np.percentile(lat, 95)) if lat else 0.0
    return {"counts": dict(cnt), "p95_latency": p95}
