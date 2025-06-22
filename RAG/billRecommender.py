import os
from typing import List, Dict
from dotenv import load_dotenv
from pinecone import Pinecone
from groq import Groq
from concurrent.futures import ThreadPoolExecutor

class BillRecommender:
    """Generates recommendations for users based on their profile and interests"""
    
    def __init__(self, pinecone_api_key: str, index_name: str = "bills-index", user_profile: Dict = None):
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index = self.pc.Index(index_name)
        # Initialize Groq client for summary generation
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        # Store user profile for personalization
        self.user_profile = user_profile or {
            "name": "User",
            "age": 30,
            "location": "United States",
            "interests": ["politics", "policy"],
            "occupation": "citizen"
        }

    def generate_embeddings(self, text: str) -> List[float]:
        # Generate embeddings (same as before)
        try:
            import openai
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                client = openai.OpenAI(api_key=openai_api_key)
                response = client.embeddings.create(input=text, model="text-embedding-3-small", dimensions=384)
                return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
        return []

    def generate_summary_with_groq(self, bill_info: Dict) -> str:
        """Generate a personalized summary using Groq when not available in metadata"""
        try:
            # Create a news-style prompt for summary generation
            prompt = f"""
            You are InShort, an AI that creates personalized bill summaries for a {self.user_profile['age']}-year-old {self.user_profile['occupation']} from {self.user_profile['location']} who is interested in {', '.join(self.user_profile['interests'])}.

            BILL INFORMATION:
            Title: {bill_info.get('title', 'Unknown')}
            Sponsor: {bill_info.get('sponsor', 'Unknown')}
            Policy Area: {bill_info.get('policy_area', 'Unknown')}
            Latest Action: {bill_info.get('latest_action', 'Unknown')}

            TASK:
            Create a news-style summary of this bill that:
            1. Explains what the bill does in clear, objective terms
            2. Describes why this bill is relevant to someone who is {self.user_profile['age']} years old, works as a {self.user_profile['occupation']}, lives in {self.user_profile['location']}, and cares about {', '.join(self.user_profile['interests'])}
            3. Uses a professional, news-like tone (no "Hey" or direct addressing)
            4. Keeps it to 2-3 sentences maximum
            5. Focuses on impact and relevance to the user's demographic and interests

            EXAMPLE STYLE:
            "This bill expands Medicare coverage for occupational therapy services, which could benefit seniors and individuals with disabilities. For residents of [state] working in [occupation], this legislation may impact healthcare accessibility and costs in the region. The bill aligns with broader healthcare policy discussions that affect [demographic]."

            NEWS-STYLE SUMMARY:
            """
            
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": f"You are InShort, a news-style AI that creates personalized bill summaries. Focus on explaining relevance to the user's demographic and interests without directly addressing them."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating personalized summary with Groq: {e}")
            return f"Unable to generate summary at this time."

    def recommend_bills(self, user_interests: List[str], top_k: int = 5, min_score: float = 0.5) -> str:
        """Generate bill recommendations based on user's interests"""
        recommendations = []
        for interest in user_interests:
            # Generate embedding for each interest
            interest_embedding = self.generate_embeddings(interest)
            if interest_embedding:
                # Search Pinecone for bills matching this interest
                results = self.index.query(
                    vector=interest_embedding,
                    top_k=top_k,
                    include_metadata=True,
                    include_values=False
                )
                # Filter results by minimum score
                filtered_results = [
                    match for match in results['matches'] if match['score'] >= min_score
                ]
                recommendations.extend(filtered_results)
        
        # Return a formatted string of recommendations
        return self.format_recommendations(recommendations)

    def recommend_bills_json(self, user_interests: List[str], top_k: int = 5, min_score: float = 0.5) -> List[Dict]:
        """Generate bill recommendations based on user's interests and return as JSON"""
        
        # Combine user interests and profile information into a focused keyword string
        profile_keywords = [
            self.user_profile.get('occupation', ''),
            self.user_profile.get('location', '')
        ]
        # Filter out any empty strings from the profile keywords
        profile_keywords = [keyword for keyword in profile_keywords if keyword]

        # Join interests and profile keywords to form a powerful query
        query_text = ' '.join(user_interests + profile_keywords)

        # Generate a single embedding for the combined query
        query_embedding = self.generate_embeddings(query_text)

        if not query_embedding:
            return []

        # Search Pinecone for bills matching the combined query
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            include_values=False
        )

        # Filter results by minimum score
        recommendations = [
            match for match in results['matches'] if match['score'] >= min_score
        ]
        
        # Return a list of recommendation dictionaries, sorted by score
        return self.format_recommendations_json(recommendations)
    
    def format_recommendations_json(self, recommendations: List[Dict]) -> List[Dict]:
        """Format recommendations as a list of JSON objects with personalized summaries, generated in parallel."""
        if not recommendations:
            return []

        def process_match(match):
            """Processes a single bill, generating a summary if needed."""
            metadata = match.get("metadata", {})
            summary = metadata.get("summary", "")
            if not summary or summary == "No summary available.":
                summary = self.generate_summary_with_groq(metadata)
            
            return {
                "id": match.get("id"),
                "score": match.get("score", 0),
                "title": metadata.get("title", "Unknown Title"),
                "bill_number": metadata.get("bill_number", "N/A"),
                "bill_type": metadata.get("type", "N/A"),
                "sponsor": metadata.get("sponsor", "N/A"),
                "congress": metadata.get("congress", "N/A"),
                "policy_area": metadata.get("policy_area", "N/A"),
                "latest_action": metadata.get("latest_action", "N/A"),
                "summary": summary
            }

        # Use a thread pool to process all recommendations concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            output = list(executor.map(process_match, recommendations))

        # Sort the final list by score in descending order
        output.sort(key=lambda x: x.get('score', 0), reverse=True)

        return output

    def format_recommendations(self, recommendations: List[Dict]) -> str:
        """Format recommendations for display with personalized summaries"""
        if not recommendations:
            return f"No relevant bills found for the specified interests."

        output = f"Recommended bills based on interests in {', '.join(self.user_profile['interests'])}:\n\n"
        for i, match in enumerate(recommendations, 1):
            metadata = match.get("metadata", {})
            score = match.get("score", 0)
            title = metadata.get("title", "Unknown Title")
            bill_number = metadata.get("bill_number", "N/A")
            bill_type = metadata.get("type", "N/A")
            sponsor = metadata.get("sponsor", "N/A")
            congress = metadata.get("congress", "N/A")
            summary = metadata.get("summary", "")
            
            # If no summary in metadata, generate one with Groq
            if not summary or summary == "No summary available.":
                summary = self.generate_summary_with_groq(metadata)
            
            output += f"#{i} - {bill_type.upper()}{bill_number} (Relevance: {score:.1%})\n"
            output += f"📋 {title}\n"
            output += f"👤 {sponsor}\n"
            output += f"🏛️ {congress}th Congress\n"
            output += f"📰 {summary}\n"
            output += "-" * 50 + "\n"

        return output

    def get_chat_response(self, user_question: str, bill_info: Dict) -> str:
        """Generate a contextual chat response using Groq"""
        try:
            # Create a detailed, persona-driven prompt for Groq
            prompt = f"""
            You are InShort, a highly knowledgeable and professional AI legislative assistant. Your user is a {self.user_profile['age']}-year-old {self.user_profile.get('occupation', 'citizen')} from {self.user_profile['location']}, who is interested in {', '.join(self.user_profile['interests'])}.

            You are discussing the following bill:
            - **Title**: {bill_info.get('title', 'N/A')}
            - **Bill Number**: {bill_info.get('bill_type', '')}{bill_info.get('bill_number', 'N/A')}
            - **Sponsor**: {bill_info.get('sponsor', 'N/A')}
            - **Policy Area**: {bill_info.get('policy_area', 'N/A')}
            - **Summary**: {bill_info.get('summary', 'No summary available.')}
            - **Latest Action**: {bill_info.get('latest_action', 'N/A')}

            The user has asked the following question:
            "{user_question}"

            Your task is to provide a clear, concise, and helpful answer that directly addresses the user's question while keeping their profile in mind.
            - If the question is about the bill's impact, relate it to their age, location, or interests.
            - If the question is technical, explain it in simple terms.
            - Maintain a professional, objective, and news-like tone. Do not be overly conversational.
            - Base your answer *only* on the provided bill information. Do not invent details. If the information is not available, state that clearly.

            Provide a direct answer to the user's question.
            """

            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": "You are InShort, an expert AI legislative assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating chat response with Groq: {e}")
            return "I am sorry, but I encountered an error trying to process your request."


# Example usage

def main():
    # Load environment variables
    load_dotenv()
    
    # Sample user profiles for demonstration
    user_profiles = [
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
        }
    ]

    # Get API key from environment
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_api_key:
        print("Error: PINECONE_API_KEY not found in environment variables")
        return

    # Test with different user profiles
    for user_profile in user_profiles:
        print(f"\n{'='*60}")
        print(f"🧑‍💼 Testing for {user_profile['name']} ({user_profile['age']}yo, {user_profile['location']}, {user_profile['occupation']})")
        print(f"{'='*60}")
        
        # Initialize recommender with user profile
        recommender = BillRecommender(pinecone_api_key, index_name="bills-index", user_profile=user_profile)

        # Get recommendations based on user's interests
        recommendations = recommender.recommend_bills(user_profile['interests'], top_k=3, min_score=0.1)
        print(recommendations)
        
        # Get JSON recommendations
        json_recommendations = recommender.recommend_bills_json(user_profile['interests'], top_k=3, min_score=0.1)
        import json
        print(json.dumps(json_recommendations, indent=2))

        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()