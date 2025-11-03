# ChatGPT with Search Integration

## Overview

Added a new endpoint `/codes-detailed-chatgpt` that uses OpenAI's ChatGPT with Search capability to find coupon codes, as an alternative to the existing Gemini-based endpoint.

## Changes Made

### 1. Dependencies

- Added `openai>=1.59.0` to `requirements.txt`
- Installed the OpenAI Python SDK

### 2. Environment Variables

Added a new required environment variable:

- `OPENAI_API_KEY`: Your OpenAI API key

Make sure to add this to your `.env` file:

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. New Endpoint

**POST** `/codes-detailed-chatgpt`

**Request:**

```json
{
  "prompt": "nike discount codes"
}
```

**Response:**

```json
{
  "codes": [
    {
      "code": "SAVE20",
      "description": "20% off entire order",
      "conditions": "new customers only, expires 12/31/24",
      "has_description": true,
      "has_conditions": true
    }
  ]
}
```

### 4. Implementation Details

The endpoint:

- Uses OpenAI's **Responses API** with the `gpt-5` model
- Enables the `web_search` tool for real-time web searching
- Uses the same system instruction as the Gemini endpoint for consistency
- Implements Redis caching with a separate cache key (`codes_detailed_chatgpt`)
- Parses responses using the same logic as the Gemini endpoint
- Returns the same `DetailedCodesResponse` format

### 5. Key Features

- **Web Search Integration**: Uses ChatGPT's built-in web search capability
- **Caching**: Responses are cached in Redis with 1-hour TTL
- **Consistent Format**: Returns the same response structure as the Gemini endpoint
- **Error Handling**: Proper exception handling with descriptive error messages

## Testing

### Manual Testing

1. Start the server:

   ```bash
   uvicorn main:app --reload
   ```

2. Run the test script:

   ```bash
   python test_chatgpt_endpoint.py
   ```

3. Or use curl:
   ```bash
   curl -X POST "http://localhost:8000/codes-detailed-chatgpt" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "nike discount codes"}'
   ```

### Comparison with Gemini Endpoint

Both endpoints use the same:

- Request/response models
- Caching strategy (separate cache keys)
- Code parsing logic
- Validation rules

Differences:

- Gemini: Uses `google-genai` SDK with `googleSearch` tool
- ChatGPT: Uses `openai` SDK with `web_search` tool
- Gemini: Has retry logic for 503 errors
- ChatGPT: Uses standard error handling

## API Model Used

- Model: `gpt-5`
- Tool: `web_search` (enables real-time web search)
- API: Responses API (OpenAI's new API for web search)

## Cost Considerations

- Web search calls incur additional tool call costs
- See [OpenAI Pricing](https://openai.com/pricing) for current rates
- Caching helps reduce API calls for repeated queries

## Future Enhancements

Potential improvements:

- Add domain filtering for specific coupon sites
- Implement user location for geo-specific codes
- Add reasoning effort control (low/medium/high)
- Stream responses for better UX
- Add source citations from web search results
