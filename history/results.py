import uuid
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Literal
from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME

router = APIRouter()

# -------------------- Setup Pinecone -------------------- #
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure index exists
if PINECONE_INDEX_NAME not in [i["name"] for i in pc.list_indexes()]:
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=384,  # adjust if you embed content
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(PINECONE_INDEX_NAME)

# -------------------- Request Schema -------------------- #
class ChannelData(BaseModel):
    verdict: Literal[0, 1] = Field(..., description="0 = non-misleading, 1 = misleading")
    platform: str = Field(..., description="Platform name (e.g., Telegram, Twitter)")
    channel_link: str = Field(..., description="Link to the channel")
    content: str = Field(..., description="Message or content text")
    input: str = Field(..., description="Optional input text for context")

# -------------------- API Endpoint -------------------- #
@router.post("/store")
async def store_channel_data(data: ChannelData = Body(...)):
    """
    Store a channel message and metadata into Pinecone.
    """
    try:
        # Generate unique ID
        vector_id = str(uuid.uuid4())

        # (Optional) Embed content for semantic search
        # For now using dummy embedding (zeros) - replace with real embedding later
        embedding = [0.0] * 384

        # Upsert into Pinecone
        index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "verdict": data.verdict,
                        "platform": data.platform,
                        "channel_link": data.channel_link,
                        "content": data.content,
                        "input": data.input,
                    },
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
