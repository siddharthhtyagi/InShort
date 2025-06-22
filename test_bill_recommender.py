#!/usr/bin/env python3
"""
Test script for the updated BillRecommender with Groq integration and personalization
"""

import os
from dotenv import load_dotenv
from RAG.billRecommender import BillRecommender

def test_personalized_bill_recommender():
    """Test the bill recommender with personalized summaries"""
    
    # Load environment variables
    load_dotenv()
    
    # Check for required API keys
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not pinecone_api_key:
        print("Error: PINECONE_API_KEY not found in environment variables")
        return
    
    if not groq_api_key:
        print("Error: GROQ_API_KEY not found in environment variables")
        print("Please set it with: export GROQ_API_KEY='your_api_key_here'")
        return
    
    print("✅ API keys found")
    print("🔍 Testing Personalized BillRecommender with Groq integration...")
    print("=" * 80)
    
    # Define different user profiles to test personalization
    user_profiles = [
        {
            "name": "Alex",
            "age": 28,
            "location": "New York",
            "interests": ["tech policy", "privacy", "startups"],
            "occupation": "software engineer"
        },
        {
            "name": "Jennifer",
            "age": 42,
            "location": "Colorado",
            "interests": ["environmental protection", "renewable energy", "public lands"],
            "occupation": "environmental consultant"
        },
        {
            "name": "David",
            "age": 58,
            "location": "Ohio",
            "interests": ["manufacturing", "trade policy", "infrastructure"],
            "occupation": "factory manager"
        }
    ]
    
    # Test each user profile
    for i, user_profile in enumerate(user_profiles, 1):
        print(f"\n🧑‍💼 Test {i}: Personalized recommendations for {user_profile['name']}")
        print(f"   Age: {user_profile['age']}, Location: {user_profile['location']}")
        print(f"   Occupation: {user_profile['occupation']}")
        print(f"   Interests: {', '.join(user_profile['interests'])}")
        print("-" * 80)
        
        try:
            # Initialize recommender with user profile
            recommender = BillRecommender(
                pinecone_api_key, 
                index_name="bills-index", 
                user_profile=user_profile
            )
            
            # Get personalized recommendations
            recommendations = recommender.recommend_bills(
                user_profile['interests'], 
                top_k=2, 
                min_score=0.1
            )
            print(recommendations)
            
        except Exception as e:
            print(f"❌ Error during test {i}: {e}")
        
        print("\n" + "=" * 80)

if __name__ == "__main__":
    test_personalized_bill_recommender() 