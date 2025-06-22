import os
import json
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
from dotenv import load_dotenv
import openai
from tqdm import tqdm

# --- Configuration ---
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INDEX_NAME = "bills-index"
MODEL_DIMENSIONS = 384  # For text-embedding-3-small with dimensions=384

# --- Helper Functions ---

def generate_embedding(text: str, model: str = "text-embedding-3-small", dimensions: int = MODEL_DIMENSIONS) -> list[float]:
    """Generate embedding for a given text using OpenAI."""
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(input=text, model=model, dimensions=dimensions)
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return []

# --- Main Script ---

def main():
    """Main function to upsert bill data into Pinecone."""
    if not PINECONE_API_KEY or not OPENAI_API_KEY:
        print("Error: API keys for Pinecone or OpenAI not found in environment variables.")
        return

    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Create index if it doesn't exist
    if INDEX_NAME not in pc.list_indexes().names():
        print(f"Creating index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=MODEL_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print("Index created successfully.")
    else:
        print(f"Index '{INDEX_NAME}' already exists.")

    index = pc.Index(INDEX_NAME)

    # Load bill data
    try:
        with open("inshort_bills.json", 'r') as f:
            bills = json.load(f)
    except FileNotFoundError:
        print("Error: 'inshort_bills.json' not found. Please run the scraper first.")
        return

    # Prepare data for upsert
    print(f"Preparing {len(bills)} bills for upsert...")
    vectors_to_upsert = []
    for bill in tqdm(bills, desc="Generating embeddings"):
        # Combine relevant text fields for a comprehensive embedding
        content_to_embed = f"{bill.get('title', '')} {bill.get('summary', '')}"
        
        # Generate embedding
        embedding = generate_embedding(content_to_embed)
        if not embedding:
            print(f"Skipping bill {bill.get('id', 'N/A')} due to embedding generation failure.")
            continue

        # Prepare metadata
        metadata = {
            "title": bill.get("title", "N/A"),
            "summary": bill.get("summary", "No summary available."),
            "sponsor": bill.get("sponsor", {}).get("fullName", "N/A"),
            "congress": bill.get("congress", "N/A"),
            "bill_number": bill.get("number", "N/A"),
            "type": bill.get("type", "N/A"),
            "latest_action": bill.get("latestAction", {}).get("text", "N/A")
        }
        
        vectors_to_upsert.append({
            "id": bill["id"],
            "values": embedding,
            "metadata": metadata
        })

    # Batch upsert to Pinecone
    if not vectors_to_upsert:
        print("No vectors to upsert.")
        return
        
    print(f"Upserting {len(vectors_to_upsert)} vectors to Pinecone in batches...")
    batch_size = 100
    for i in tqdm(range(0, len(vectors_to_upsert), batch_size), desc="Upserting batches"):
        batch = vectors_to_upsert[i:i + batch_size]
        try:
            index.upsert(vectors=batch)
        except Exception as e:
            print(f"Error upserting batch {i//batch_size + 1}: {e}")

    print("\nUpsert complete!")
    print(index.describe_index_stats())

if __name__ == "__main__":
    main()
