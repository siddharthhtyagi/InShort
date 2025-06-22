# InShort: Personalized Bill Recommendations

InShort is a mobile application designed to help users discover and understand legislative bills that are relevant to their personal interests and location. Using a powerful AI backend, the app delivers personalized bill recommendations and custom-tailored summaries, making complex legislation accessible and engaging.

![Architecture Diagram](https://mermaid.ink/svg/eyJjb2RlIjoiZ3JhcGggVERcbiAgICBzdWJncmFwaCBGcm9udGVuZCAtIGlPUyBBcHBcbiAgICAgICAgQVtTd2lmdFVJIFZpZXdzXSAtLT4gQltWaWV3TW9kZWxzXTtcbiAgICAgICAgQiAtLT4gQ1tTZXJ2aWNlcyAtIEJpbGxTZXJ2aWNlLCBVc2VyU2VydmljZV07XG4gICAgZW5kXG5cbiAgICBzdWJncmFwaCBCYWNrZW5kIC0gUHl0aG9uIFNlcnZlclxuICAgICAgICBFW0Zhc3RBUEkgRW5kcG9pbnQgL3JlY29tbWVuZGF0aW9ucy9dIC0tPiBGW0JpbGxSZWNvbW1lbmRlcl07XG4gICAgICAgIEYgLS0-IEdbUGluZWNvbmUgVmVjdG9yIERCXTtcbiAgICAgICAgRiAtLT4gSFtPcGVuQUkgZm9yIEVtYmVkZGluZ3NdO1xuICAgICAgICBGIC0tPiBJW0dyb3EgZm9yIFN1bW1hcmllc107XG4gICAgZW5kXG5cbiAgICBzdWJncmFwaCBEYXRhIEZsb3dcbiAgICAgICAgSltVc2VyIFByb2ZpbGUgQ2hhbmdlc10gLS0-IEI7XG4gICAgICAgIEMgLS0gSFRUUCBSZXF1ZXN0IC0tPiBFO1xuICAgICAgICBFIC0tIEpTT04gUmVzcG9uc2UgLS0-IEM7XG4gICAgZW5kXG5cbiAgICBzdHlsZSBGcm9udGVuZCBmaWxsOiNFNkY3RkYsc3Ryb2tlOiNCM0Q5RkYsc3Ryb2tlLXdpZHRoOjJweFxuICAgIHN0eWxlIEJhY2tlbmQgZmlsbDojRThGNUU5LHN0cm9rZTojQTVENkE3LHN0cm9rZS13aWR0aDoycHhcbiAgICBzdHlsZSBEYXRhIEZsb3cgZmlsbDojRkZGOEUxLHN0cm9rZTojRkZFQ0IzLHN0cm9rZS13aWR0aDoycHgiLCJtZXJtYWlkIjp7InRoZW1lIjoiZGVmYXVsdCJ9LCJ1cGRhdGVFZGl0b3IiOmZhbHNlLCJhdXRvU3luYyI6dHJ1ZSwidXBkYXRlRGlhZ3JhbSI6ZmFsc2V9)

---

## Features

-   **Personalized Recommendations**: Leverages a vector database (Pinecone) to find bills that semantically match a user's unique profile, including their interests, location, and occupation.
-   **AI-Generated Summaries**: Uses a Large Language Model (Groq) to generate concise, easy-to-understand summaries of bills, personalized to be relevant to the user.
-   **Dynamic Profile Updates**: Seamlessly updates recommendations when a user changes their profile interests.
-   **SwiftUI Frontend**: A modern, reactive iOS application built with SwiftUI and the MVVM pattern.
-   **FastAPI Backend**: A robust and efficient Python backend serving the recommendation engine.

---

## Architecture

The project is a monorepo containing two main components: a SwiftUI frontend and a Python backend.

### Frontend (iOS App)

-   **Language**: Swift
-   **UI Framework**: SwiftUI
-   **Architecture**: Model-View-ViewModel (MVVM)
    -   **Views**: SwiftUI views define the UI and bind to ViewModel properties.
    -   **ViewModels**: Contain the presentation logic and state for the views.
    -   **Models**: Represent the data structures of the app (e.g., `Bill`, `UserProfile`).
    -   **Services**: Handle networking (`BillService`, `UserService`) and other shared logic (`NotificationService`).
-   **Data Persistence**: `UserDefaults` is used to persist the user's profile locally.
-   **Concurrency**: `Combine` and `async/await` are used for managing asynchronous operations and state updates.

### Backend (Python Server)

-   **Framework**: FastAPI
-   **Database**: Pinecone (Vector Database for semantic search)
-   **AI Services**:
    -   **OpenAI**: Used to generate vector embeddings for text data.
    -   **Groq**: Used to generate personalized bill summaries with a fast LLM.
-   **Core Logic**: The `BillRecommender` class in `RAG/` encapsulates the logic for querying the vector database and formatting results.

---

## Getting Started

### Prerequisites

-   macOS with Xcode installed.
-   Python 3.8+
-   `pip` for Python package management.

### 1. Backend Setup

First, set up and run the Python server.

1.  **Navigate to the Backend Directory**:
    ```bash
    cd InShort
    ```

2.  **Create an Environment File**:
    Create a file named `.env` in the `InShort/` directory and add your API keys:
    ```
    PINECONE_API_KEY="YOUR_PINECONE_KEY"
    OPENAI_API_KEY="YOUR_OPENAI_KEY"
    GROQ_API_KEY="YOUR_GROQ_KEY"
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Populate the Database**:
    Run the upsert script to populate your Pinecone index with bill data. Make sure your Pinecone index is configured for 384 dimensions to match the `text-embedding-3-small` model.
    ```bash
    python3 RAG/pcupsert.py
    ```

5.  **Run the Server**:
    ```bash
    uvicorn api:app --reload
    ```
    The server will be running at `http://127.0.0.1:8000`.

### 2. Frontend Setup

With the backend running, you can now launch the iOS application.

1.  **Navigate to the Frontend Project**:
    ```bash
    cd ../InShortFrontEnd
    ```

2.  **Open in Xcode**:
    Open the `InShort.xcodeproj` file in Xcode.
    ```bash
    open InShort.xcodeproj
    ```

3.  **Build and Run**:
    Select an iOS Simulator (e.g., iPhone 15 Pro) or a physical device and press the "Run" button (or `Cmd+R`). The app will launch and connect to your local backend.

---

## Project Structure

```
.
├── InShort/                  # Python Backend
│   ├── api.py                # FastAPI application endpoints
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Example environment file
│   └── RAG/
│       ├── billRecommender.py  # Core recommendation logic
│       └── pcupsert.py         # Script to populate Pinecone
│
└── InShortFrontEnd/          # iOS Frontend
    └── InShort/
        ├── InShort.xcodeproj   # Xcode Project
        └── InShort/
            ├── Models/         # Data models (Bill, UserProfile)
            ├── ViewModels/     # ViewModel layer (NewsViewModel, etc.)
            ├── Views/          # SwiftUI views
            └── Services/       # Networking and data services
```

## Prerequisites

1. **Congress.gov API Key**: Get a free API key from [Congress.gov API](https://api.congress.gov/)
   - Visit https://api.congress.gov/
   - Sign up for a free account
   - Generate your API key
   - Already there in google docs file

2. **Groq API Key**: Get an API key from [Groq](https://console.groq.com/)
   - Visit https://console.groq.com/
   - Sign up for an account
   - Generate your API key
   - Already there in google docs file

3. **Python Dependencies**: Install the required packages
   ```bash
   pip install -r requirements.txt
   ```

## Project Structure

- `full_bill_scraper.py` - Scrapes comprehensive bill data from Congress.gov
- `inshort_summarizer.py` - Generates personalized AI summaries using Groq
- `inshort_bills.json` - Bill data (generated by scraper)
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Quick Start

### Step 1: Set up API Keys

Set your API keys as environment variables:

```bash
# Set Congress.gov API key
export CONGRESS_API_KEY="your_congress_api_key_here"

# Set Groq API key
export GROQ_API_KEY="your_groq_api_key_here"
```

### Step 2: Scrape Bill Data

Run the bill scraper to collect comprehensive bill data:

```bash
python3 full_bill_scraper.py
```

This will:
- Fetch the most recent 100 bills from Congress.gov
- Collect full details including sponsors, actions, amendments, text, and more
- Save the data to `inshort_bills.json`

### Step 3: Generate AI Summaries

Run the AI summarizer to create personalized summaries:

```bash
python3 inshort_summarizer.py
```

This will:
- Load the bill data from `inshort_bills.json`
- Generate personalized summaries for different user profiles
- Show how the same bill affects different users differently

## Detailed Usage

### Bill Scraper Options

The `full_bill_scraper.py` script collects comprehensive bill data:

```bash
# Basic usage (collects 100 bills)
python3 full_bill_scraper.py

# The script automatically:
# - Fetches bills from the 119th Congress
# - Collects full details for each bill
# - Saves data to inshort_bills.json
```

### AI Summarizer Features

The `inshort_summarizer.py` script generates personalized summaries for:

1. **Sarah (25yo, Texas, recent graduate)** - Focus on student loans, job market, housing
2. **Mike (45yo, California, small business owner)** - Focus on business regulations, taxes, healthcare
3. **Lisa (62yo, Florida, retired teacher)** - Focus on Medicare, Social Security, education
4. **David (35yo, New York, tech worker)** - Focus on tech regulations, privacy, immigration

Each summary is tailored to show how the bill specifically impacts that user's situation.

## Example Output

### Bill Scraper Output
```
Fetching bills 0 to 10...
  Getting full details for HR1234 (119th Congress)...
    Title: Homebuyers Privacy Protection Act...
    ✓ Successfully collected full details (1/100)
  
Total bills with full details collected: 100
Saved 100 bills with full details to inshort_bills.json
```

### AI Summarizer Output
```
📱 Sarah (25yo, Texas, recent graduate)
--------------------------------------------------

📋 Bill 1: Homebuyers Privacy Protection Act
💡 This bill directly impacts your ability to buy a home! It protects your personal 
financial information when applying for mortgages, preventing lenders from sharing 
your sensitive data without permission. As a recent graduate looking to buy your 
first home, this gives you more control over your financial privacy and could 
help you avoid predatory lending practices.

📋 Bill 2: Student Loan Forgiveness Act
💡 Great news for your student debt! This bill expands loan forgiveness programs 
for recent graduates working in public service or low-income areas. You could 
qualify for partial or full forgiveness of your student loans if you work in 
education, healthcare, or government for 10 years.
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Congress.gov API
CONGRESS_API_KEY=your_congress_api_key

# Groq API
GROQ_API_KEY=your_groq_api_key
```

### Customizing User Profiles

Edit the user profiles in `inshort_summarizer.py` to match your target audience:

```python
USER_PROFILES = [
    {
        "name": "Your Custom Profile",
        "age": 30,
        "location": "Your State",
        "occupation": "Your Job",
        "interests": ["relevant", "topics", "here"]
    }
]
```

## API Rate Limits

- **Congress.gov**: 1,000 requests per hour (free tier)
- **Groq**: Varies by plan, typically 100+ requests per minute

The scripts include rate limiting to stay within these limits.

## Troubleshooting

### Common Issues

1. **Invalid API Keys**: Make sure your API keys are correct and active
2. **Rate Limit Exceeded**: Wait before making more requests
3. **Python Command Not Found**: Use `python3` instead of `python`
4. **Environment Variable Not Set**: Export your API keys in the terminal

### Error Messages

- `Invalid API Key`: Check your API key is correct
- `Rate Limit Exceeded`: Wait before retrying
- `File Not Found`: Make sure `inshort_bills.json` exists

## Data Privacy

- API keys are stored as environment variables (not in code)
- Bill data is public information from Congress.gov
- User profiles are fictional examples for demonstration

## Legal Notice

This tool is for educational and research purposes. Please respect the Congress.gov and Groq API terms of service and rate limits. The bill data is provided by the United States Congress and is in the public domain.

## RAG System and Bill Recommender

InShort now includes a RAG (Retrieval-Augmented Generation) system that uses Pinecone for vector storage and Groq for generating summaries.

### Prerequisites for RAG System

1. **Pinecone API Key**: Get a free API key from [Pinecone](https://www.pinecone.io/)
   - Visit https://www.pinecone.io/
   - Sign up for a free account
   - Generate your API key

2. **OpenAI API Key**: For generating embeddings
   - Visit https://platform.openai.com/
   - Generate your API key

Set your additional API keys:

```bash
# Set Pinecone API key
export PINECONE_API_KEY="your_pinecone_api_key_here"

# Set OpenAI API key (for embeddings)
export OPENAI_API_KEY="your_openai_api_key_here"
```

### Step 4: Store Bills in Vector Database

First, update the bills in Pinecone with summaries:

```bash
python3 upsert_bills.py
```

This will:
- Read the bill data from `inshort_bills.json`
- Extract summaries from the bill data
- Generate embeddings for each bill
- Store everything in Pinecone with metadata including summaries

### Step 5: Test Bill Recommender

Test the bill recommender with Groq integration:

```bash
python3 test_bill_recommender.py
```

Or run the recommender directly:

```bash
python3 RAG/billRecommender.py
```

### Bill Recommender Features

The updated `BillRecommender` class provides:

1. **Vector Search**: Uses embeddings to find relevant bills based on user interests
2. **Groq Integration**: Automatically generates summaries using Groq when not available in metadata
3. **Personalized Recommendations**: Returns bills ranked by relevance to user interests
4. **Comprehensive Metadata**: Includes bill title, sponsor, congress, and summary

### Example RAG Output

```
Based on your interests, we recommend the following bills:

#1 - HR1234 (Score: 0.856)
📋 Title: Student Loan Forgiveness Act
👤 Sponsor: Sponsored by John Smith
🏛️ Congress: 119
📖 Summary: This bill expands student loan forgiveness programs for graduates working in public service. It could save you thousands of dollars on your student debt if you work in education, healthcare, or government for 10 years. This affects you.
--------------------------------------------------
```

### RAG System Architecture

- **Vector Storage**: Pinecone stores bill embeddings and metadata
- **Embedding Generation**: OpenAI's text-embedding-3-small model
- **Summary Generation**: Groq's llama3-8b-8192 model
- **Retrieval**: Semantic search based on user interests
- **Generation**: AI-generated summaries when not available in metadata

### Customizing the RAG System

You can modify the `BillRecommender` class to:

1. **Change Search Parameters**: Adjust `top_k` and `min_score` thresholds
2. **Customize Summaries**: Modify the Groq prompt for different summary styles
3. **Add User Profiles**: Integrate with the personalized summarizer
4. **Filter Results**: Add additional filtering based on bill status, date, etc. 