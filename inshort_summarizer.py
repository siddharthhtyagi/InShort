#!/usr/bin/env python3
"""
InShort Bill Summarizer using Groq

This script takes the collected bill data and uses Groq to generate
personalized summaries for different user profiles.

Usage:
    python3 inshort_summarizer.py
"""

import json
import os
import time
from typing import List, Dict, Optional
from groq import Groq

# Initialize Groq client
# You'll need to set your GROQ_API_KEY environment variable
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def load_bills(filename: str = "inshort_bills.json") -> List[Dict]:
    """Load bills from JSON file"""
    try:
        with open(filename, 'r') as f:
            bills = json.load(f)
        print(f"Loaded {len(bills)} bills from {filename}")
        return bills
    except FileNotFoundError:
        print(f"Error: {filename} not found. Please run the bill scraper first.")
        return []
    except Exception as e:
        print(f"Error loading bills: {e}")
        return []

def extract_bill_text(bill_data: Dict) -> str:
    """Extract relevant text from bill data for summarization"""
    bill = bill_data.get('bill', {})
    
    # Get basic info
    title = bill.get('title', 'N/A')
    bill_type = bill.get('type', 'N/A')
    bill_number = bill.get('number', 'N/A')
    congress = bill.get('congress', 'N/A')
    
    # Get summary if available
    summary = ""
    if 'summaries_details' in bill_data:
        summaries = bill_data['summaries_details'].get('summaries', [])
        if summaries:
            summary = summaries[0].get('text', '')
    
    # Get latest action
    latest_action = bill.get('latestAction', {})
    action_text = latest_action.get('text', '')
    action_date = latest_action.get('actionDate', '')
    
    # Get policy area
    policy_area = bill.get('policyArea', {}).get('name', 'N/A')
    
    # Get sponsors info
    sponsors_info = ""
    if 'sponsors_details' in bill_data:
        sponsors = bill_data['sponsors_details'].get('sponsors', [])
        if sponsors:
            sponsor = sponsors[0]
            sponsors_info = f"Sponsored by {sponsor.get('fullName', 'Unknown')} ({sponsor.get('party', 'Unknown')}-{sponsor.get('state', 'Unknown')})"
    
    # Get subjects
    subjects = []
    if 'subjects_details' in bill_data:
        subjects_data = bill_data['subjects_details'].get('subjects', [])
        if isinstance(subjects_data, list):
            subjects = [subject.get('name', '') for subject in subjects_data if isinstance(subject, dict)]
        elif isinstance(subjects_data, str):
            subjects = [subjects_data]
    
    # Compile all text
    text_parts = [
        f"Bill: {bill_type}{bill_number} ({congress}th Congress)",
        f"Title: {title}",
        f"Policy Area: {policy_area}",
        f"Subjects: {', '.join(subjects)}",
        f"Sponsor: {sponsors_info}",
        f"Latest Action: {action_text} (Date: {action_date})",
        f"Summary: {summary}"
    ]
    
    return "\n".join(text_parts)

def generate_personalized_summary(bill_text: str, user_profile: Dict) -> str:
    """Generate personalized summary using Groq"""
    
    prompt = f"""
You are InShort, an AI that turns complex government bills into personalized, easy-to-understand summaries.

BILL INFORMATION:
{bill_text}

USER PROFILE:
- Age: {user_profile['age']}
- Location: {user_profile['location']}
- Interests: {', '.join(user_profile['interests'])}
- Occupation: {user_profile['occupation']}

TASK:
Create a personalized summary of this bill that answers:
1. What does this bill do in plain English? (2-3 sentences)
2. How does it specifically affect this user? (1-2 sentences)
3. When do the changes take effect? (if mentioned)
4. Should they care? (Yes/No and why)

FORMAT:
- Keep it conversational and friendly
- Use "you" to address the user directly
- If the bill doesn't affect them, explain why they might still care
- Maximum 4 sentences total
- End with a simple "This affects you" or "This doesn't affect you directly"

EXAMPLE:
"This bill lowers insulin prices for Medicare recipients. If you're over 65, it could save you $200/month starting next year. This affects you."

RESPONSE:
"""
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",  # Fast and effective for this task
            messages=[
                {"role": "system", "content": "You are InShort, a helpful AI that explains government bills in simple terms."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "Unable to generate summary at this time."

def create_user_profiles() -> List[Dict]:
    """Create sample user profiles for testing"""
    return [
        {
            "name": "Sarah",
            "age": 25,
            "location": "Texas",
            "interests": ["student loans", "healthcare", "climate change"],
            "occupation": "recent graduate"
        },
        {
            "name": "Robert",
            "age": 65,
            "location": "Florida",
            "interests": ["medicare", "social security", "veterans"],
            "occupation": "retired"
        },
        {
            "name": "Maria",
            "age": 35,
            "location": "California",
            "interests": ["housing", "education", "immigration"],
            "occupation": "teacher"
        },
        {
            "name": "David",
            "age": 45,
            "location": "New York",
            "interests": ["taxes", "business", "finance"],
            "occupation": "small business owner"
        }
    ]

def main():
    """Main function to process bills and generate summaries"""
    
    # Check if GROQ_API_KEY is set
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY environment variable not set.")
        print("Please set it with: export GROQ_API_KEY='your_api_key_here'")
        return
    
    # Load bills
    bills = load_bills()
    if not bills:
        return
    
    # Create user profiles
    user_profiles = create_user_profiles()
    
    print(f"\nGenerating personalized summaries for {len(user_profiles)} user profiles...")
    print("=" * 60)
    
    # Process first 5 bills for each user profile
    for i, user_profile in enumerate(user_profiles):
        print(f"\n📱 {user_profile['name']} ({user_profile['age']}yo, {user_profile['location']}, {user_profile['occupation']})")
        print("-" * 50)
        
        for j, bill in enumerate(bills[:5]):  # Process first 5 bills
            bill_text = extract_bill_text(bill)
            bill_info = bill.get('bill', {})
            bill_title = bill_info.get('title', 'Unknown Bill')
            
            print(f"\n📋 Bill {j+1}: {bill_title}")
            
            # Generate personalized summary
            summary = generate_personalized_summary(bill_text, user_profile)
            print(f"💬 {summary}")
            
            # Rate limiting
            time.sleep(1)
        
        print(f"\n✅ Completed summaries for {user_profile['name']}")
    
    print(f"\n🎉 Generated personalized summaries for {len(user_profiles)} users!")
    print("This demonstrates how InShort can provide different perspectives on the same bills.")

if __name__ == "__main__":
    main() 