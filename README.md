# FastAPI Gemini Server

A FastAPI server that integrates with Google's Gemini API.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your environment variables:
   - Copy `.env.example` to `.env` if needed
   - Add your Gemini API key to the `.env` file:
     ```
     GEMINI_API_KEY=your_actual_api_key_here
     ```

3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints

- `POST /generate` - Send a prompt to Gemini and get a response
  - Request body: `{"prompt": "your prompt here"}`
  - Response: `{"response": "gemini's response"}`

## Getting a Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy it to your `.env` file
