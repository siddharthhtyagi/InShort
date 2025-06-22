import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict
from dotenv import load_dotenv
from RAG.billRecommender import BillRecommender

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:8081", "http://127.0.0.1:8080", "http://127.0.0.1:8081"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for user profile
class UserProfile(BaseModel):
    name: str = "User"
    age: int = 30
    location: str = "United States"
    interests: List[str] = Field(..., example=["student loans", "healthcare"])
    occupation: str = "citizen"

# Pydantic model for chat requests
class ChatRequest(BaseModel):
    question: str
    bill: Dict
    user_profile: UserProfile

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
            user_profile=user_profile.model_dump()
        )

        # Get recommendations
        recommendations = recommender.recommend_bills_json(
            user_interests=user_profile.interests,
            top_k=50,
            min_score=0.1
        )
        
        return recommendations

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/")
async def handle_chat(chat_request: ChatRequest):
    """
    Handle a user's chat question about a specific bill.
    """
    try:
        # Initialize recommender with the provided user profile
        recommender = BillRecommender(
            pinecone_api_key=pinecone_api_key,
            index_name="bills-index",
            user_profile=chat_request.user_profile.model_dump()
        )

        # Get chat response
        chat_response = recommender.get_chat_response(
            user_question=chat_request.question,
            bill_info=chat_request.bill
        )
        
        return {"response": chat_response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Welcome to the InShort Bill Recommender API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)