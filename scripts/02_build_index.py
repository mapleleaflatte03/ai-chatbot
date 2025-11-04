import argparse, json
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


def chunk_text(text, max_chars=1200):
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]


def build(csv_path, index_path, meta_path, model_name):
    df = pd.read_csv(csv_path)
    model = SentenceTransformer(model_name)

    passages, meta = [], []
    for _, row in df.iterrows():
        base = f"title: {row['title']}\nurl: {row['url']}\ncontent: "
        for ch in chunk_text(str(row["body"])):
            passages.append(f"passage: {base}{ch}")
            meta.append({"url": row["url"], "title": row["title"], "text": ch})

    emb = model.encode(passages, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    emb = np.asarray(emb, dtype="float32")

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    faiss.write_index(index, index_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "model": model_name}, f, ensure_ascii=False)

    print(f"Built index: {index.ntotal} chunks -> {index_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/faq.csv")
    ap.add_argument("--out", default="storage/index.faiss")
    ap.add_argument("--meta", default="storage/meta.json")
    ap.add_argument("--model", default="intfloat/multilingual-e5-base")
    args = ap.parse_args()
    build(args.csv, args.out, args.meta, args.model)
