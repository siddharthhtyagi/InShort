import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import fetch_bills as fb
from RAG.billRecommender import BillRecommender
import inShort_agent as agent

#── Load env ────────────────────────────────────────────────────────────────
load_dotenv()
pinecone_api_key = os.getenv("PINECONE_API_KEY")
if not pinecone_api_key:
    raise RuntimeError("PINECONE_API_KEY not found in environment variables")

app = FastAPI()
agent_graph = agent.create_agent_graph()

#── Models ─────────────────────────────────────────────────────────────────
class UserProfile(BaseModel):
    name: str = "User"
    age: int = 30
    location: str = "United States"
    interests: List[str] = Field(..., example=["student loans", "healthcare"])
    occupation: str = "citizen"
    id: str = "default-user-id"
    friends: List[Dict[str, Any]] = []
    subscriptions: List[Dict[str, Any]] = []

class ChatRequest(BaseModel):
    user_input: str
    session_id: str
    user_profile: Dict[str, Any]

class Bill(BaseModel):
    id: str
    title: str
    summary: str
    fullText: Optional[str] = None
    sponsor: str
    relevanceScore: Optional[float] = None
    isLiked: bool = False
    isDisliked: bool = False
    isSubscribed: bool = False
    dateIntroduced: Optional[str] = None
    lastUpdated: Optional[str] = None
    billNumber: Optional[str] = None
    billType: Optional[str] = None
    congress: Optional[str] = None
    policyArea: Optional[str] = None
    latestAction: Optional[str] = None

#── Fixture loader ─────────────────────────────────────────────────────────
def load_bills() -> Dict[str, Bill]:
    BASE_DIR = os.path.dirname(__file__)
    path = os.path.join(BASE_DIR, "inshort_bills.json")
    try:
        with open(path, "r") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"Error loading inshort_bills.json: {e}")
        return {}
    out: Dict[str, Bill] = {}
    for bd in raw:
        cong  = str(bd.get("congress", ""))
        typ   = bd.get("type", "")
        num   = bd.get("number", "")
        key   = f"{cong}-{typ}-{num}"
        out[key] = Bill(
            id=key,
            title=bd.get("title",""),
            summary=bd.get("summary",""),
            sponsor=bd.get("sponsor",""),
            billNumber=num,
            billType=typ,
            congress=cong,
            policyArea=bd.get("policyArea"),
            latestAction=bd.get("latestAction"),
            dateIntroduced=bd.get("introducedDate"),
            isLiked=False,
            isDisliked=False,
            isSubscribed=False
        )
    return out

BILLS: Dict[str, Bill] = load_bills()

#── Helpers ────────────────────────────────────────────────────────────────
def normalize_bill_id(bill_id: str) -> (str,str,str):
    """
    Accept either "119-HR-3076" or "bill_119_HR-3076" or "bill_119_HRHR-785",
    return (congress, bill_type, bill_number).
    """
    if bill_id.startswith("bill_"):
        # bill_<congress>_<type>-<number>
        try:
            _, cong, tail = bill_id.split("_", 2)
            typ, num = tail.split("-",1)
        except ValueError:
            raise HTTPException(status_code=404, detail="Bill not found")
    else:
        parts = bill_id.split("-")
        if len(parts) != 3:
            raise HTTPException(status_code=404, detail="Bill not found")
        cong, typ, num = parts
    return cong, typ.lower(), num

async def fetch_and_cache(cong: str, typ: str, num: str) -> Bill:
    key = f"{cong}-{typ}-{num}"
    # 1) try cache
    if key in BILLS:
        return BILLS[key]

    # 2) call LangChain tool with single-dict or .invoke
    payload = {"congress": cong, "bill_type": typ, "bill_number": num}
    try:
        if hasattr(fb.get_bill_details, "invoke"):
            raw = fb.get_bill_details.invoke(payload)
        else:
            raw = fb.get_bill_details(payload)
        details = raw if isinstance(raw, dict) else json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Bill not found ({e})")
    if not details or "error" in details:
        raise HTTPException(status_code=404, detail="Bill not found")

    # 3) override id, cache, and return
    details["id"] = key
    bill = Bill(**details)
    BILLS[key] = bill
    return bill

#── Bill endpoints ─────────────────────────────────────────────────────────
@app.get("/bills/", response_model=List[Bill])
async def get_bills():
    return list(BILLS.values())

@app.get("/bills/details/{bill_id}", response_model=Bill)
async def get_bill_details(bill_id: str):
    cong, typ, num = normalize_bill_id(bill_id)
    return await fetch_and_cache(cong, typ, num)

@app.post("/bills/like/{bill_id}", response_model=Bill)
async def like_bill(bill_id: str):
    bill_id = bill_id.replace("HRHR", "HR")  # Normalize input
    cong, typ, num = normalize_bill_id(bill_id)
    bill = await fetch_and_cache(cong, typ, num)
    bill.isLiked = True
    bill.isDisliked = False
    return bill

@app.post("/bills/dislike/{bill_id}", response_model=Bill)
async def dislike_bill(bill_id: str):
    bill_id = bill_id.replace("HRHR", "HR")  # Normalize input
    cong, typ, num = normalize_bill_id(bill_id)
    bill = await fetch_and_cache(cong, typ, num)
    bill.isLiked = False
    bill.isDisliked = True
    return bill

@app.post("/bills/subscribe/{bill_id}", response_model=Bill)
async def subscribe_to_bill(bill_id: str):
    bill_id = bill_id.replace("HRHR", "HR")  # Normalize input

    cong, typ, num = normalize_bill_id(bill_id)
    bill = await fetch_and_cache(cong, typ, num)
    bill.isSubscribed = True
    return bill

@app.post("/bills/unsubscribe/{bill_id}", response_model=Bill)
async def unsubscribe_from_bill(bill_id: str):
    bill_id = bill_id.replace("HRHR", "HR")  # Normalize input

    cong, typ, num = normalize_bill_id(bill_id)
    bill = await fetch_and_cache(cong, typ, num)
    bill.isSubscribed = False
    return bill

#── Recommendations ────────────────────────────────────────────────────────
@app.post("/recommendations/", response_model=List[Dict[str,Any]])
async def get_recommendations(user_profile: UserProfile):
    try:
        recommender = BillRecommender(
            pinecone_api_key=pinecone_api_key,
            index_name="bills-index",
            user_profile=user_profile.model_dump()
        )
        return recommender.recommend_bills_json(
            user_interests=user_profile.interests,
            top_k=5,
            min_score=0.1
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#── Chat agent ────────────────────────────────────────────────────────────
@app.post("/chat/")
async def chat_with_agent(request: ChatRequest):
    try:
        global agent_graph
        if not agent_graph:
            agent_graph = agent.create_agent_graph()
        resp = agent.run_agent(
            graph=agent_graph,
            config={"configurable": {"thread_id": request.session_id}},
            user_input=request.user_input,
            user_profile=request.user_profile
        )
        return {"response": resp or "I couldn't process that."}
    except Exception as e:
        return {"response": f"Error: {e}"}

#── Root ──────────────────────────────────────────────────────────────────
@app.get("/")
def read_root():
    return {"message": "Welcome to the InShort Bill Recommender API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
