import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
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

# Initialize BillRecommender
pinecone_api_key = os.getenv("PINECONE_API_KEY")
if not pinecone_api_key:
    raise RuntimeError("PINECONE_API_KEY not found in environment variables")

# Load bills from JSON file
def load_bills():
    try:
        with open("inshort_bills.json", "r") as f:
            bills_data = json.load(f)

        # Transform the data into our Bill model format
        bills = []
        for bill_data in bills_data:
            bill_info = bill_data.get("bill", {})

            # Extract summary from summaries if available
            summary = "No summary available"
            if "summaries" in bill_info and isinstance(bill_info["summaries"], dict) and "text" in bill_info["summaries"]:
                summary = bill_info["summaries"]["text"]

            # Extract sponsor name
            sponsor = "Unknown Sponsor"
            if "sponsors" in bill_info and isinstance(bill_info["sponsors"], list) and len(bill_info["sponsors"]) > 0:
                sponsor = bill_info["sponsors"][0].get("fullName", "Unknown Sponsor")

            # Extract policy area
            policy_area = None
            if "policyArea" in bill_info and isinstance(bill_info["policyArea"], dict):
                policy_area = bill_info["policyArea"].get("name")

            # Extract latest action
            latest_action = None
            if "latestAction" in bill_info and isinstance(bill_info["latestAction"], dict):
                latest_action = bill_info["latestAction"].get("text")

            # Format the bill ID to be consistent with what the agent expects
            congress = str(bill_info.get('congress'))
            bill_type = bill_info.get('type', 'HR')
            bill_number = bill_info.get('number', '0000')

            # Create the bill ID in the format expected by both the API and the agent
            bill_id = f"{congress}-{bill_type}-{bill_number}"

            bill = Bill(
                id=bill_id,
                title=bill_info.get("title", "Untitled Bill"),
                summary=summary,
                sponsor=sponsor,
                billNumber=bill_number,
                billType=bill_type,
                congress=congress,
                policyArea=policy_area,
                latestAction=latest_action,
                dateIntroduced=bill_info.get("introducedDate"),
                isLiked=False,
                isDisliked=False,
                isSubscribed=False
            )
            bills.append(bill)

        # If no bills were loaded, create some sample bills
        if not bills:
            bills = [
                Bill(
                    id="119-HR-1234",  # Format: {congress}-{bill_type}-{bill_number}
                    title="Sample Bill 1",
                    summary="This is a sample bill for testing purposes.",
                    sponsor="Rep. Sample, Test [D-CA-1]",
                    billNumber="1234",
                    billType="HR",
                    congress="119",
                    policyArea="Health",
                    latestAction="Introduced in House",
                    dateIntroduced="2023-01-01",
                    isLiked=False,
                    isDisliked=False,
                    isSubscribed=False
                ),
                Bill(
                    id="119-S-5678",  # Format: {congress}-{bill_type}-{bill_number}
                    title="Sample Bill 2",
                    summary="Another sample bill for testing purposes.",
                    sponsor="Sen. Test, Sample [R-TX-1]",
                    billNumber="5678",
                    billType="S",
                    congress="119",
                    policyArea="Education",
                    latestAction="Referred to Committee",
                    dateIntroduced="2023-02-01",
                    isLiked=False,
                    isDisliked=False,
                    isSubscribed=False
                )
            ]

        return bills
    except Exception as e:
        print(f"Error loading bills: {e}")
        # Return sample bills if there's an error
        return [
            Bill(
                id="119-HR-1234",  # Format: {congress}-{bill_type}-{bill_number}
                title="Sample Bill 1",
                summary="This is a sample bill for testing purposes.",
                sponsor="Rep. Sample, Test [D-CA-1]",
                billNumber="1234",
                billType="HR",
                congress="119",
                policyArea="Health",
                latestAction="Introduced in House",
                dateIntroduced="2023-01-01",
                isLiked=False,
                isDisliked=False,
                isSubscribed=False
            ),
            Bill(
                id="119-S-5678",  # Format: {congress}-{bill_type}-{bill_number}
                title="Sample Bill 2",
                summary="Another sample bill for testing purposes.",
                sponsor="Sen. Test, Sample [R-TX-1]",
                billNumber="5678",
                billType="S",
                congress="119",
                policyArea="Education",
                latestAction="Referred to Committee",
                dateIntroduced="2023-02-01",
                isLiked=False,
                isDisliked=False,
                isSubscribed=False
            )
        ]

# Global variable to store bills
BILLS = load_bills()

# Mock user data
USERS = {
    "default-user-id": {
        "id": "default-user-id",
        "name": "Default User",
        "age": 30,
        "location": "United States",
        "interests": ["healthcare", "education", "environment"],
        "occupation": "citizen",
        "friends": [],
        "subscriptions": []
    }
}

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
        global agent_graph
        # Ensure the agent graph is initialized
        if not agent_graph:
            agent_graph = agent.create_agent_graph()

        config = {"configurable": {"thread_id": request.session_id}}
        response = agent.run_agent(
            graph=agent_graph,
            config=config,
            user_input=request.user_input,
            user_profile=request.user_profile
        )

        # Log the response for debugging
        print(f"Chat response: {response}")

        # If response is None, return a helpful error message
        if response is None:
            return {"response": "I'm sorry, I couldn't process your request. Please try again with a different question."}

        return {"response": response}
    except Exception as e:
        print(f"Error in chat_with_agent: {str(e)}")
        # Return a more user-friendly error message
        return {"response": f"I'm sorry, I encountered an error: {str(e)}. Please try again with a different question."}
        # Uncomment the line below if you want to return an HTTP error instead
        # raise HTTPException(status_code=500, detail=str(e))

# Bill-related endpoints
@app.get("/bills/", response_model=List[Bill])
async def get_bills():
    """
    Get all bills.
    """
    return BILLS

@app.get("/bills/details/{bill_id}", response_model=Bill)
async def get_bill_details(bill_id: str):
    """
    Get details for a specific bill.
    """
    # First try to find the bill in the BILLS list
    bill = next((b for b in BILLS if b.id == bill_id), None)

    # If not found, try to parse the bill_id to extract congress, type, and number
    if not bill:
        try:
            # Try to parse bill_id in format like "118-HR-3076"
            if '-' in bill_id:
                parts = bill_id.split('-')
                if len(parts) == 3:
                    congress, bill_type, bill_number = parts
                    # Use the fetch_bills.get_bill_details to get the bill from the API
                    import fetch_bills as fb
                    bill_details = fb.get_bill_details(congress=congress, bill_type=bill_type.lower(), bill_number=bill_number)

                    # Check if there was an error
                    if 'error' in bill_details:
                        raise HTTPException(status_code=404, detail=f"Bill not found: {bill_details.get('error')}")

                    # Create a Bill object from the API response
                    bill = Bill(
                        id=bill_id,
                        title=bill_details.get('title', 'Untitled Bill'),
                        summary=bill_details.get('summary', 'No summary available'),
                        sponsor=bill_details.get('sponsors', [{}])[0].get('name', 'Unknown Sponsor') if bill_details.get('sponsors') else 'Unknown Sponsor',
                        billNumber=bill_details.get('bill_number'),
                        billType=bill_details.get('bill_type'),
                        congress=bill_details.get('congress'),
                        policyArea=bill_details.get('policy_area'),
                        latestAction=bill_details.get('latest_action', {}).get('text'),
                        dateIntroduced=bill_details.get('introduced_date'),
                        isLiked=False,
                        isDisliked=False,
                        isSubscribed=False
                    )

                    # Add the bill to the BILLS list for future reference
                    BILLS.append(bill)
            # Try to parse bill_id in format like "bill_119_HRHR-785" or "bill_119_SS-2029"
            elif '_' in bill_id:
                parts = bill_id.split('_')
                if len(parts) >= 3:
                    # Format: bill_119_HRHR-785 or bill_119_SS-2029
                    # parts[0] = "bill", parts[1] = "119", parts[2] = "HRHR-785" or "SS-2029"
                    congress = parts[1]

                    # Handle case where bill type and number are separated by a hyphen
                    if '-' in parts[2]:
                        type_number_parts = parts[2].split('-')
                        bill_type = type_number_parts[0].lower()
                        bill_number = type_number_parts[1]
                    else:
                        # If no hyphen, try to extract type and number based on common patterns
                        # This is a fallback and might need adjustment based on actual data
                        bill_type = parts[2][:2].lower()
                        bill_number = parts[2][2:]

                    # Use the fetch_bills.get_bill_details to get the bill from the API
                    import fetch_bills as fb
                    bill_details = fb.get_bill_details(congress=congress, bill_type=bill_type.lower(), bill_number=bill_number)

                    # Check if there was an error
                    if 'error' in bill_details:
                        raise HTTPException(status_code=404, detail=f"Bill not found: {bill_details.get('error')}")

                    # Create a Bill object from the API response
                    bill = Bill(
                        id=bill_id,
                        title=bill_details.get('title', 'Untitled Bill'),
                        summary=bill_details.get('summary', 'No summary available'),
                        sponsor=bill_details.get('sponsors', [{}])[0].get('name', 'Unknown Sponsor') if bill_details.get('sponsors') else 'Unknown Sponsor',
                        billNumber=bill_details.get('bill_number'),
                        billType=bill_details.get('bill_type'),
                        congress=bill_details.get('congress'),
                        policyArea=bill_details.get('policy_area'),
                        latestAction=bill_details.get('latest_action', {}).get('text'),
                        dateIntroduced=bill_details.get('introduced_date'),
                        isLiked=False,
                        isDisliked=False,
                        isSubscribed=False
                    )

                    # Add the bill to the BILLS list for future reference
                    BILLS.append(bill)
        except Exception as e:
            print(f"Error parsing bill_id or fetching bill details: {e}")
            raise HTTPException(status_code=404, detail="Bill not found")

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    return bill

@app.post("/bills/like/{bill_id}", response_model=Bill)
async def like_bill(bill_id: str):
    """
    Like a bill.
    """
    # First try to find the bill in the BILLS list
    bill = next((b for b in BILLS if b.id == bill_id), None)

    # If not found, try to get the bill details first
    if not bill:
        try:
            # This will parse the bill_id and add it to BILLS if found
            bill = await get_bill_details(bill_id)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Bill not found")

    bill.isLiked = True
    bill.isDisliked = False
    return bill

# Additional endpoint to handle the frontend's bill ID format
@app.post("/bills/like/bill_{congress}_{bill_type}-{bill_number}", response_model=Bill)
async def like_bill_frontend_format(congress: str, bill_type: str, bill_number: str):
    """
    Like a bill using the frontend's bill ID format.
    """
    # Construct the bill_id in the format the frontend is sending
    bill_id = f"bill_{congress}_{bill_type}-{bill_number}"

    # Call the original like_bill function
    return await like_bill(bill_id)

@app.post("/bills/dislike/{bill_id}", response_model=Bill)
async def dislike_bill(bill_id: str):
    """
    Dislike a bill.
    """
    # First try to find the bill in the BILLS list
    bill = next((b for b in BILLS if b.id == bill_id), None)

    # If not found, try to get the bill details first
    if not bill:
        try:
            # This will parse the bill_id and add it to BILLS if found
            bill = await get_bill_details(bill_id)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Bill not found")

    bill.isLiked = False
    bill.isDisliked = True
    return bill

# Additional endpoint to handle the frontend's bill ID format
@app.post("/bills/dislike/bill_{congress}_{bill_type}-{bill_number}", response_model=Bill)
async def dislike_bill_frontend_format(congress: str, bill_type: str, bill_number: str):
    """
    Dislike a bill using the frontend's bill ID format.
    """
    # Construct the bill_id in the format the frontend is sending
    bill_id = f"bill_{congress}_{bill_type}-{bill_number}"

    # Call the original dislike_bill function
    return await dislike_bill(bill_id)

@app.post("/bills/subscribe/{bill_id}", response_model=Bill)
async def subscribe_to_bill(bill_id: str):
    """
    Subscribe to a bill.
    """
    # First try to find the bill in the BILLS list
    bill = next((b for b in BILLS if b.id == bill_id), None)

    # If not found, try to get the bill details first
    if not bill:
        try:
            # This will parse the bill_id and add it to BILLS if found
            bill = await get_bill_details(bill_id)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Bill not found")

    bill.isSubscribed = True

    # Also add to user's subscriptions (using default user for now)
    user = USERS["default-user-id"]
    if bill_id not in [sub.get("id") for sub in user["subscriptions"]]:
        user["subscriptions"].append({"id": bill_id})

    return bill

# Additional endpoint to handle the frontend's bill ID format
@app.post("/bills/subscribe/bill_{congress}_{bill_type}-{bill_number}", response_model=Bill)
async def subscribe_bill_frontend_format(congress: str, bill_type: str, bill_number: str):
    """
    Subscribe to a bill using the frontend's bill ID format.
    """
    # Construct the bill_id in the format the frontend is sending
    bill_id = f"bill_{congress}_{bill_type}-{bill_number}"

    # Call the original subscribe_to_bill function
    return await subscribe_to_bill(bill_id)

@app.post("/bills/unsubscribe/{bill_id}", response_model=Bill)
async def unsubscribe_from_bill(bill_id: str):
    """
    Unsubscribe from a bill.
    """
    # First try to find the bill in the BILLS list
    bill = next((b for b in BILLS if b.id == bill_id), None)

    # If not found, try to get the bill details first
    if not bill:
        try:
            # This will parse the bill_id and add it to BILLS if found
            bill = await get_bill_details(bill_id)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Bill not found")

    bill.isSubscribed = False

    # Also remove from user's subscriptions (using default user for now)
    user = USERS["default-user-id"]
    user["subscriptions"] = [sub for sub in user["subscriptions"] if sub.get("id") != bill_id]

    return bill

# Additional endpoint to handle the frontend's bill ID format
@app.post("/bills/unsubscribe/bill_{congress}_{bill_type}-{bill_number}", response_model=Bill)
async def unsubscribe_bill_frontend_format(congress: str, bill_type: str, bill_number: str):
    """
    Unsubscribe from a bill using the frontend's bill ID format.
    """
    # Construct the bill_id in the format the frontend is sending
    bill_id = f"bill_{congress}_{bill_type}-{bill_number}"

    # Call the original unsubscribe_from_bill function
    return await unsubscribe_from_bill(bill_id)

# Friends-related endpoints
@app.get("/friends/", response_model=List[UserProfile])
async def get_friends():
    """
    Get a user's friends.
    """
    # Using default user for now
    user = USERS["default-user-id"]
    friends = []
    for friend_id in user["friends"]:
        if friend_id in USERS:
            friends.append(UserProfile(**USERS[friend_id]))
    return friends

@app.post("/friends/add/{friend_id}", response_model=UserProfile)
async def add_friend(friend_id: str):
    """
    Add a friend.
    """
    # Check if friend exists
    if friend_id not in USERS:
        # Create a new user if they don't exist
        USERS[friend_id] = {
            "id": friend_id,
            "name": f"Friend {friend_id}",
            "age": 30,
            "location": "United States",
            "interests": ["politics", "legislation"],
            "occupation": "Citizen",
            "friends": [],
            "subscriptions": []
        }

    # Add friend to user's friends list (using default user for now)
    user = USERS["default-user-id"]
    if friend_id not in user["friends"]:
        user["friends"].append(friend_id)

    return UserProfile(**USERS[friend_id])

@app.post("/friends/remove/{friend_id}")
async def remove_friend(friend_id: str):
    """
    Remove a friend.
    """
    # Using default user for now
    user = USERS["default-user-id"]
    user["friends"] = [f for f in user["friends"] if f != friend_id]
    return {"success": True}

@app.get("/")
def read_root():
    return {"message": "Welcome to the InShort Bill Recommender API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
