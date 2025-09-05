import os
import hashlib
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from typing import List

# Load keys
load_dotenv()
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME')

# Init embedding + Pinecone
embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# --------- Helpers ----------

def chunk_text(text: str, max_words: int = 100) -> List[str]:
    """Breaks large text into smaller chunks"""
    words = text.split()
    return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

def check_content_against_sebi(content: str, top_k: int = 3, threshold: float = 0.75):
    """
    Check if given content is aligned with SEBI data in Pinecone.
    Returns potential misleading parts.
    """
    chunks = chunk_text(content)
    results = []

    for chunk in chunks:
        emb = embedding_model.encode(chunk).tolist()
        query_response = index.query(vector=emb, top_k=top_k, include_metadata=True)
        
        # Check top matches
        if not query_response.matches:
            results.append((chunk, "⚠️ No relevant SEBI data found (potentially misleading)"))
            continue
        
        best_match = query_response.matches[0]
        score = best_match.score
        ref_text = best_match.metadata.get("text", "")

        if score >= threshold:
            results.append((chunk, f"✅ Aligned with SEBI (score={score:.2f})\nRef: {ref_text[:200]}..."))
        else:
            results.append((chunk, f"⚠️ Possible misleading info (low similarity, score={score:.2f})"))
    
    return results

# --------- Usage Example ----------

if __name__ == "__main__":
    new_content = """
    Mutual funds guarantee fixed returns every year without any risk.
    Investors should never worry about market fluctuations when investing in SEBI-approved funds.
    """
    
    results = check_content_against_sebi(new_content)
    for chunk, verdict in results:
        print(f"\nChunk: {chunk}\nVerdict: {verdict}")
