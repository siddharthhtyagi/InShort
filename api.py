import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from dotenv import load_dotenv
from RAG.billRecommender import BillRecommender
import inShort_agent as agent

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Initialize the agent graph
agent_graph = agent.create_agent_graph()

# Pydantic model for user profile
class UserProfile(BaseModel):
    name: str = "User"
    age: int = 30
    location: str = "United States"
    interests: List[str] = Field(..., example=["student loans", "healthcare"])
    occupation: str = "citizen"

class ChatRequest(BaseModel):
    user_input: str
    session_id: str
    user_profile: Dict[str, Any]

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
            top_k=5,
            min_score=0.1
        )
        
        return recommendations

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/")
async def chat_with_agent(request: ChatRequest):
    """
    Have a conversation with the bill agent.
    """
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        response = agent.run_agent(
            graph=agent_graph,
            config=config,
            user_input=request.user_input,
            user_profile=request.user_profile
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Welcome to the InShort Bill Recommender API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)