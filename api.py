import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict
from dotenv import load_dotenv
from RAG.billRecommender import BillRecommender

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Pydantic model for user profile
class UserProfile(BaseModel):
    name: str = "User"
    age: int = 30
    location: str = "United States"
    interests: List[str] = Field(..., example=["student loans", "healthcare"])
    occupation: str = "citizen"

# Initialize BillRecommender
pinecone_api_key = os.getenv("PINECONE_API_KEY")
if not pinecone_api_key:
    raise RuntimeError("PINECONE_API_KEY not found in environment variables")

@app.post("/recommendations/", response_model=List[Dict])
async def get_recommendations(user_profile: UserProfile):
    """
    Get bill recommendations based on user profile.
    """
    try:
        # Initialize recommender with the provided user profile
        recommender = BillRecommender(
            pinecone_api_key=pinecone_api_key,
            index_name="bills-index",
            user_profile=user_profile.dict()
        )

        # Get recommendations
        recommendations = recommender.recommend_bills_json(
            user_interests=user_profile.interests,
            top_k=5,
            min_score=0.1
        )
        
        return recommendations

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Welcome to the InShort Bill Recommender API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 