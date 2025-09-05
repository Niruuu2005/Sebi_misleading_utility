import uuid
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME_HISTORY, OPENAI_API_KEY

router = APIRouter()

# -------------------- Setup Pinecone -------------------- #
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure index exists
if PINECONE_INDEX_NAME_HISTORY not in [i["name"] for i in pc.list_indexes()]:
    pc.create_index(
        name=PINECONE_INDEX_NAME_HISTORY,
        dimension=384,  # Reduced embedding size
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(PINECONE_INDEX_NAME_HISTORY)

# -------------------- OpenAI Client -------------------- #
client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------- Request Schema -------------------- #
class ChannelData(BaseModel):
    verdict: str = Field(..., description="0 = non-misleading, 1 = misleading")
    channel_link: str = Field(..., description="Link to the channel")
    content: str = Field(..., description="Message or content text")
    input: str = Field(..., description="Optional input text for context")
    platform: str = Field(..., description="Source of data")

# -------------------- API Endpoint -------------------- #
@router.post("/store")
async def store_channel_data(data: ChannelData = Body(...)):
    """
    Store a channel message and metadata into Pinecone with embeddings.
    """
    try:
        # Generate unique ID
        vector_id = str(uuid.uuid4())

        # Generate 384-dim embedding from content using OpenAI
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=data.content,
            dimensions=384  # ✅ request reduced dimension
        )
        embedding = response.data[0].embedding

        # Validate embedding
        if not any(embedding):
            raise HTTPException(status_code=400, detail="Generated embedding is invalid (all zeros).")

        # Upsert into Pinecone
        index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": data.dict(),
                }
            ]
        )

        return {
            "status": "success",
            "id": vector_id,
            "stored_data": data.dict()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pinecone error: {str(e)}")
