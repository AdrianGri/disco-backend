import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
import redis

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Gemini API Server",
    description="A FastAPI server that integrates with Google's Gemini API",
    version="1.0.0"
)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

client = genai.Client(
        api_key=GEMINI_API_KEY,
    )

# Configure OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is not set")
redis_client = redis.Redis.from_url(REDIS_URL)

# Initialize the Gemini model
model = "gemini-2.5-flash"

# Request/Response models
class PromptRequest(BaseModel):
    prompt: str

class PromptResponse(BaseModel):
    response: str

# Structured output model for codes
class CodesList(BaseModel):
    codes: List[str]

class CodeInfo(BaseModel):
    code: str
    description: str = ""
    conditions: str = ""
    has_description: bool = False  # True if we found actual description data
    has_conditions: bool = False   # True if we found actual condition data

class CodesResponse(BaseModel):
    codes: List[str]
    
class DetailedCodesResponse(BaseModel):
    codes: List[CodeInfo]

# Redis-based cache with TTL
CACHE_TTL_SECONDS = 60 * 60

def _cache_get(cache_prefix: str, key: str):
    """Get value from Redis cache"""
    try:
        cache_key = f"{cache_prefix}:{key}"
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print(f"Cache HIT for key: {cache_key}")
            return json.loads(cached_data)
        print(f"Cache MISS for key: {cache_key}")
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None

def _cache_set(cache_prefix: str, key: str, value, ttl: int = CACHE_TTL_SECONDS):
    """Set value in Redis cache with TTL"""
    try:
        cache_key = f"{cache_prefix}:{key}"
        # Convert Pydantic models to dict for JSON serialization
        if hasattr(value, 'dict'):
            serialized_value = value.dict()
        else:
            serialized_value = value
        redis_client.setex(cache_key, ttl, json.dumps(serialized_value))
    except Exception as e:
        print(f"Cache set error: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Gemini API Server is running"}

@app.post("/codes-detailed", response_model=DetailedCodesResponse)
async def get_detailed_codes(request: PromptRequest):
    """
    Get codes with detailed information about conditions and applicability
    
    Args:
        request: PromptRequest containing the prompt string
        
    Returns:
        DetailedCodesResponse containing a list of codes with details
    """
    try:
        # Cache check (MVP)
        key = request.prompt.strip()
        cached = _cache_get("codes_detailed", key)
        if cached is not None:
            # Wait 1 second
            await asyncio.sleep(1)

            return DetailedCodesResponse(**cached)

        # Add system instruction for finding codes with details
        system_instruction = """
            You are a high-precision coupon code finder. Search the entire web for coupon codes that match the user's request.

            Only return codes that you are at least 50% confident will work. If you are unsure about a code's validity, do not include it.

            Prioritize the most reliable codes first — list codes in order of highest confidence of working.

            When searching, prioritize codes found on credible coupon sources such as Honey, Coupert, RetailMeNot, official store websites, or other reputable platforms. If you find valid codes elsewhere that you are confident will work, include them as well, but they must meet the same quality and confidence standards.

            For each valid code, format it EXACTLY like this:
            CODE | discount description | conditions

            Examples:
            SAVE20 | 20% off entire order | new customers only, expires 12/31/24
            FREESHIP | free shipping | orders over $50, valid until end of month
            WELCOME10 | $10 off first purchase | new users only, minimum $25 order

            If conditions are not found, write “no specific conditions found”.
            If the discount amount is not found, write “discount amount not specified”.
            Keep descriptions short, clear, and in proper English. Do not include random phrases, spammy text, or run-on sentences.
            Do not include irrelevant codes (e.g., unrelated brands, expired offers, or fake generators).
            Do not include any explanatory text before or after the code list. Only return the formatted code lines."""
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"{system_instruction}\n\nUser request: {request.prompt}"),
                ],
            )
        ]
        
        tools = [
            types.Tool(googleSearch=types.GoogleSearch()),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            tools=tools,
            response_mime_type="text/plain",
        )
        
        # Generate response from Gemini with retry logic for 503 errors
        response = ""
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                for chunk in client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                ):
                    if chunk.text:
                        print(chunk.text, end="")
                        response += chunk.text
                
                # If we got here without exception, break out of retry loop
                break
                
            except Exception as api_error:
                # Check if it's a 503 error
                error_message = str(api_error)
                is_503_error = "503" in error_message or "Service Unavailable" in error_message
                
                if is_503_error and retry_count < max_retries:
                    retry_count += 1
                    print(f"\n503 error encountered. Retrying ({retry_count}/{max_retries})...")
                    # Wait a bit before retrying (exponential backoff)
                    await asyncio.sleep(2 ** retry_count)
                    response = ""  # Reset response for retry
                    continue
                else:
                    # If it's not a 503 error, or we've exhausted retries, re-raise
                    raise

        if not response:
            raise HTTPException(status_code=500, detail="No response generated from Gemini")

        # Parse the response to extract detailed codes
        detailed_codes = []
        
        # Clean up response first
        response = response.strip()
        
        # Enhanced list of words that are not codes
        excluded_words = {
            'FOUND', 'SEVERAL', 'TYPES', 'BUT', 'SPECIFIC', 'UNIVERSALLY', 'APPLICABLE', 
            'ARE', 'LESS', 'COMMON', 'MANY', 'ACTIVATED', 'THROUGH', 'MEMBERSHIP',
            'VERIFICATION', 'AUTOMATICALLY', 'APPLIED', 'DURING', 'SALES', 'BASED',
            'THE', 'SEARCH', 'RESULTS', 'HERE', 'SOME', 'GENERAL', 'DISCOUNT',
            'CATEGORIES', 'AND', 'OFFERS', 'THAT', 'FUNCTION', 'LIKE', 'CODES',
            'WIDELY', 'OFF', 'REQUIRES', 'OFTEN', 'FOR', 'MEMBERS', 'APP',
            'ORDER', 'FREE', 'SHIPPING', 'EARLY', 'ACCESS', 'EXCLUSIVE', 'CODE',
            'SIGNING', 'MENTIONED', 'SNIPPETS', 'TIME', 'SENSITIVE', 'REQUIRE',
            'CONDITIONS', 'BUYING', 'MULTIPLE', 'ITEMS', 'CANNOT', 'PROVIDE',
            'ACTUAL', 'VALID', 'CURRENTLY', 'ACTIVE', 'ALPHANUMERIC', 'WITHOUT',
            'ONGOING', 'PROMOTION', 'INDICATE', 'PROCESSES', 'RATHER', 'THAN',
            'SIMPLE', 'PUBLIC', 'THEREFORE', 'THERE', 'LIST', 'DIRECTLY',
            'REQUESTED', 'FORMAT', 'DIFFERENT', 'VERIFY', 'WITH', 'BIRTHDAY',
            'NIKE', 'AMAZON', 'WALMART', 'MCDONALDS', 'MCDONALD', 'DISCOUNT',
            'COUPON', 'PROMO', 'DEAL', 'SALE', 'SAVE', 'PERCENT', 'DOLLAR',
            'UNFORTUNATELY', 'DEALS', 'SPECIFIC', 'FOLLOWING', 'AVAILABLE',
            'CURRENTLY', 'WEBSITE', 'ONLINE', 'STORE', 'PURCHASE', 'CHECKOUT',
            'WHEN', 'YOUR', 'YOU', 'CAN', 'GET', 'USE', 'HAVE', 'WILL', 'THIS',
            'FROM', 'WITH', 'THEIR', 'THEY', 'ALSO', 'MORE', 'SOME', 'ALL',
            'EACH', 'ONLY', 'FIRST', 'LAST', 'NEXT', 'MAKE', 'GOOD', 'NEW',
            'USED', 'WAY', 'MAY', 'TAKE', 'COME', 'ITS', 'NOW', 'FIND', 'LONG',
            'DOWN', 'DAY', 'DID', 'GET', 'HAS', 'HER', 'HIM', 'HIS', 'HOW',
            'MAN', 'OLD', 'SEE', 'TWO', 'WHO', 'BOY', 'CAME', 'ITS', 'LET',
            'PUT', 'SAY', 'SHE', 'TOO', 'USE', 'COMPILATION', 'DETAILS',
            'RESTRICTIONS', 'EXPIRATION', 'DATES', 'MINIMUM', 'MAXIMUM',
            'USERS', 'CUSTOMERS', 'ORDERS', 'ITEMS', 'PRODUCTS', 'SELECTION',
            'POPULAR', 'DEVICES', 'BOOKS', 'HOME', 'KITCHEN', 'BEAUTY',
            'FASHION', 'DELIVERY', 'TRIAL', 'MONTH', 'STUDENT', 'PRIME',
            'CARDS', 'FIRE', 'STICK', 'RING', 'CAMERA', 'AUDIO', 'SMART',
            'WIRELESS', 'KINDLE', 'AUDIBLE', 'AUDIOBOOKS', 'COMPUTER',
            'MOUNTS', 'CABLES', 'TOTAL', 'SELECTED', 'GRAPHIC', 'COMIC',
            'LIGHTNING', 'SUBSCRIBE', 'OVER', 'SPEND', 'SELECT', 'ADDITIONALLY',
            'PLEASE', 'NOTE', 'CHANGE', 'FREQUENTLY', 'ALWAYS', 'IDEA',
            'TERMS', 'SITE', 'BEFORE', 'MAKING', 'PROMOTIONS', 'OTHER',
            'WAYS', 'STILL', 'HOWEVER', 'TRADITIONAL', 'UNIVERSALLY',
            'PROVIDES', 'VARIOUS', 'COMPILATION', 'USING'
        }
        
        # Split by lines and parse each code entry
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or len(line) < 3:
                continue
                
            # Try to parse format: CODE | description | conditions
            if '|' in line:
                parts = [part.strip() for part in line.split('|')]
                if len(parts) >= 2:
                    code = parts[0].upper().strip()
                    description = parts[1] if len(parts) > 1 else ""
                    conditions = parts[2] if len(parts) > 2 else "no specific conditions mentioned"
                    
                    # Check if we have meaningful data
                    has_description = (description and 
                                     description.lower() not in ["discount amount not specified", "discount not specified", "amount not specified", ""]) 
                    has_conditions = (conditions and 
                                    conditions.lower() not in ["no specific conditions mentioned", "no specific conditions found", 
                                                              "conditions not specified", "no conditions", ""]) 
                    
                    # Set placeholders if no meaningful data
                    if not has_description:
                        description = "Discount amount not available"
                    if not has_conditions:
                        conditions = "Conditions not available"
                    
                    # Validate code format - more strict validation
                    if (code and len(code) >= 3 and len(code) <= 20 and 
                        code.replace('-', '').replace('_', '').replace('%', '').isalnum() and
                        code not in excluded_words and
                        # Additional check: code should contain some numbers or be mostly uppercase
                        (any(c.isdigit() for c in code) or code.isupper())):
                        detailed_codes.append(CodeInfo(
                            code=code,
                            description=description,
                            conditions=conditions,
                            has_description=has_description,
                            has_conditions=has_conditions
                        ))
            else:
                # Look for patterns that clearly indicate codes with conditions
                # e.g., "SAVE20 - 20% off orders over $50"
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    if len(parts) == 2:
                        code = parts[0].strip().upper()
                        description = parts[1].strip()
                        
                        # Check if we have meaningful description
                        has_description = (description and 
                                         description.lower() not in ["discount amount not specified", "discount not specified", "amount not specified"]) 
                        has_conditions = False  # No conditions in dash format
                        
                        # Set placeholder if no meaningful data
                        if not has_description:
                            description = "Discount amount not available"
                        
                        if (code and len(code) >= 3 and len(code) <= 20 and 
                            code.replace('-', '').replace('_', '').isalnum() and
                            code not in excluded_words and
                            (any(c.isdigit() for c in code) or code.isupper())):
                            detailed_codes.append(CodeInfo(
                                code=code,
                                description=description,
                                conditions="Conditions not available",
                                has_description=has_description,
                                has_conditions=has_conditions
                            ))
        
        # Remove duplicate codes
        unique_codes = {}

        for code_info in detailed_codes:
            if code_info.code not in unique_codes:
                unique_codes[code_info.code] = code_info
            else:
                # If duplicate, prefer the one with more info
                existing = unique_codes[code_info.code]
                if (code_info.has_description and not existing.has_description) or \
                   (code_info.has_conditions and not existing.has_conditions):
                    unique_codes[code_info.code] = code_info
        
        # Store in cache before returning
        resp_obj = DetailedCodesResponse(codes=list(unique_codes.values()))
        _cache_set("codes_detailed", key, resp_obj)
        return resp_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating detailed codes: {str(e)}")

@app.post("/codes-detailed-chatgpt", response_model=DetailedCodesResponse)
async def get_detailed_codes_chatgpt(request: PromptRequest):
    """
    Get codes with detailed information using ChatGPT with Search
    
    Args:
        request: PromptRequest containing the prompt string
        
    Returns:
        DetailedCodesResponse containing a list of codes with details
    """
    try:
        # Cache check
        key = request.prompt.strip()
        cached = _cache_get("codes_detailed_chatgpt", key)
        if cached is not None:
            # Wait 1 second
            await asyncio.sleep(1)
            return DetailedCodesResponse(**cached)

        # System instruction for finding codes with details
        system_instruction = """
You are a high-precision coupon code finder. Search the entire web for coupon codes that match the user's request.

Only return codes that you are at least 50% confident will work. If you are unsure about a code's validity, do not include it.

Prioritize the most reliable codes first — list codes in order of highest confidence of working.

When searching, prioritize codes found on credible coupon sources such as Honey, Coupert, RetailMeNot, official store websites, or other reputable platforms. If you find valid codes elsewhere that you are confident will work, include them as well, but they must meet the same quality and confidence standards.

For each valid code, format it EXACTLY like this:
CODE | discount description | conditions

Examples:
SAVE20 | 20% off entire order | new customers only, expires 12/31/24
FREESHIP | free shipping | orders over $50, valid until end of month
WELCOME10 | $10 off first purchase | new users only, minimum $25 order

If conditions are not found, write "no specific conditions found".
If the discount amount is not found, write "discount amount not specified".
Keep descriptions short, clear, and in proper English. Do not include random phrases, spammy text, or run-on sentences.
Do not include irrelevant codes (e.g., unrelated brands, expired offers, or fake generators).
Do not include any explanatory text before or after the code list. Only return the formatted code lines."""

        # Use ChatGPT Responses API with web search
        # Using low reasoning effort for faster responses (better for quick coupon lookups)
        response = openai_client.responses.create(
            model="gpt-5",
            reasoning={"effort": "low"},  # Faster searches, less deep reasoning
            tools=[{
                "type": "web_search",
                "external_web_access": True
            }],
            input=f"{system_instruction}\n\nUser request: {request.prompt}"
        )
        
        # Extract the output text from the response
        output_text = response.output_text
        
        if not output_text:
            raise HTTPException(status_code=500, detail="No response generated from ChatGPT")

        # Log the raw output before cleaning
        print("\n" + "="*80)
        print("[ChatGPT Raw Output - Before Cleaning]")
        print("="*80)
        print(output_text)
        print("="*80 + "\n")

        # Parse the response to extract detailed codes (same parsing logic as Gemini)
        detailed_codes = []
        
        # Clean up response first
        output_text = output_text.strip()
        
        # Function to clean source references from text
        def clean_source_references(text: str) -> str:
            """Remove source citations like ([joinhoney.com]) or (https://...) from text"""
            import re
            # Remove parenthetical source citations
            text = re.sub(r'\s*\([^)]*(?:\.com|\.org|\.net|https?://)[^)]*\)', '', text)
            # Remove bracketed URLs
            text = re.sub(r'\s*\[[^\]]*(?:\.com|\.org|\.net|https?://)[^\]]*\]', '', text)
            # Clean up extra spaces
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        
        # Enhanced list of words that are not codes
        excluded_words = {
            'FOUND', 'SEVERAL', 'TYPES', 'BUT', 'SPECIFIC', 'UNIVERSALLY', 'APPLICABLE', 
            'ARE', 'LESS', 'COMMON', 'MANY', 'ACTIVATED', 'THROUGH', 'MEMBERSHIP',
            'VERIFICATION', 'AUTOMATICALLY', 'APPLIED', 'DURING', 'SALES', 'BASED',
            'THE', 'SEARCH', 'RESULTS', 'HERE', 'SOME', 'GENERAL', 'DISCOUNT',
            'CATEGORIES', 'AND', 'OFFERS', 'THAT', 'FUNCTION', 'LIKE', 'CODES',
            'WIDELY', 'OFF', 'REQUIRES', 'OFTEN', 'FOR', 'MEMBERS', 'APP',
            'ORDER', 'FREE', 'SHIPPING', 'EARLY', 'ACCESS', 'EXCLUSIVE', 'CODE',
            'SIGNING', 'MENTIONED', 'SNIPPETS', 'TIME', 'SENSITIVE', 'REQUIRE',
            'CONDITIONS', 'BUYING', 'MULTIPLE', 'ITEMS', 'CANNOT', 'PROVIDE',
            'ACTUAL', 'VALID', 'CURRENTLY', 'ACTIVE', 'ALPHANUMERIC', 'WITHOUT',
            'ONGOING', 'PROMOTION', 'INDICATE', 'PROCESSES', 'RATHER', 'THAN',
            'SIMPLE', 'PUBLIC', 'THEREFORE', 'THERE', 'LIST', 'DIRECTLY',
            'REQUESTED', 'FORMAT', 'DIFFERENT', 'VERIFY', 'WITH', 'BIRTHDAY',
            'NIKE', 'AMAZON', 'WALMART', 'MCDONALDS', 'MCDONALD', 'DISCOUNT',
            'COUPON', 'PROMO', 'DEAL', 'SALE', 'SAVE', 'PERCENT', 'DOLLAR',
            'UNFORTUNATELY', 'DEALS', 'SPECIFIC', 'FOLLOWING', 'AVAILABLE',
            'CURRENTLY', 'WEBSITE', 'ONLINE', 'STORE', 'PURCHASE', 'CHECKOUT',
            'WHEN', 'YOUR', 'YOU', 'CAN', 'GET', 'USE', 'HAVE', 'WILL', 'THIS',
            'FROM', 'WITH', 'THEIR', 'THEY', 'ALSO', 'MORE', 'SOME', 'ALL',
            'EACH', 'ONLY', 'FIRST', 'LAST', 'NEXT', 'MAKE', 'GOOD', 'NEW',
            'USED', 'WAY', 'MAY', 'TAKE', 'COME', 'ITS', 'NOW', 'FIND', 'LONG',
            'DOWN', 'DAY', 'DID', 'GET', 'HAS', 'HER', 'HIM', 'HIS', 'HOW',
            'MAN', 'OLD', 'SEE', 'TWO', 'WHO', 'BOY', 'CAME', 'ITS', 'LET',
            'PUT', 'SAY', 'SHE', 'TOO', 'USE', 'COMPILATION', 'DETAILS',
            'RESTRICTIONS', 'EXPIRATION', 'DATES', 'MINIMUM', 'MAXIMUM',
            'USERS', 'CUSTOMERS', 'ORDERS', 'ITEMS', 'PRODUCTS', 'SELECTION',
            'POPULAR', 'DEVICES', 'BOOKS', 'HOME', 'KITCHEN', 'BEAUTY',
            'FASHION', 'DELIVERY', 'TRIAL', 'MONTH', 'STUDENT', 'PRIME',
            'CARDS', 'FIRE', 'STICK', 'RING', 'CAMERA', 'AUDIO', 'SMART',
            'WIRELESS', 'KINDLE', 'AUDIBLE', 'AUDIOBOOKS', 'COMPUTER',
            'MOUNTS', 'CABLES', 'TOTAL', 'SELECTED', 'GRAPHIC', 'COMIC',
            'LIGHTNING', 'SUBSCRIBE', 'OVER', 'SPEND', 'SELECT', 'ADDITIONALLY',
            'PLEASE', 'NOTE', 'CHANGE', 'FREQUENTLY', 'ALWAYS', 'IDEA',
            'TERMS', 'SITE', 'BEFORE', 'MAKING', 'PROMOTIONS', 'OTHER',
            'WAYS', 'STILL', 'HOWEVER', 'TRADITIONAL', 'UNIVERSALLY',
            'PROVIDES', 'VARIOUS', 'COMPILATION', 'USING'
        }
        
        # Split by lines and parse each code entry
        lines = output_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or len(line) < 3:
                continue
                
            # Try to parse format: CODE | description | conditions
            if '|' in line:
                parts = [part.strip() for part in line.split('|')]
                if len(parts) >= 2:
                    code = parts[0].upper().strip()
                    description = parts[1] if len(parts) > 1 else ""
                    conditions = parts[2] if len(parts) > 2 else "no specific conditions mentioned"
                    
                    # Clean source references from description and conditions
                    description = clean_source_references(description)
                    conditions = clean_source_references(conditions)
                    
                    # Check if we have meaningful data
                    has_description = (description and 
                                     description.lower() not in ["discount amount not specified", "discount not specified", "amount not specified", ""]) 
                    has_conditions = (conditions and 
                                    conditions.lower() not in ["no specific conditions mentioned", "no specific conditions found", 
                                                              "conditions not specified", "no conditions", ""]) 
                    
                    # Set placeholders if no meaningful data
                    if not has_description:
                        description = "Discount amount not available"
                    if not has_conditions:
                        conditions = "Conditions not available"
                    
                    # Validate code format - more strict validation
                    if (code and len(code) >= 3 and len(code) <= 20 and 
                        code.replace('-', '').replace('_', '').replace('%', '').isalnum() and
                        code not in excluded_words and
                        # Additional check: code should contain some numbers or be mostly uppercase
                        (any(c.isdigit() for c in code) or code.isupper())):
                        detailed_codes.append(CodeInfo(
                            code=code,
                            description=description,
                            conditions=conditions,
                            has_description=has_description,
                            has_conditions=has_conditions
                        ))
            else:
                # Look for patterns that clearly indicate codes with conditions
                # e.g., "SAVE20 - 20% off orders over $50"
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    if len(parts) == 2:
                        code = parts[0].strip().upper()
                        description = parts[1].strip()
                        
                        # Check if we have meaningful description
                        has_description = (description and 
                                         description.lower() not in ["discount amount not specified", "discount not specified", "amount not specified"]) 
                        has_conditions = False  # No conditions in dash format
                        
                        # Set placeholder if no meaningful data
                        if not has_description:
                            description = "Discount amount not available"
                        
                        if (code and len(code) >= 3 and len(code) <= 20 and 
                            code.replace('-', '').replace('_', '').isalnum() and
                            code not in excluded_words and
                            (any(c.isdigit() for c in code) or code.isupper())):
                            detailed_codes.append(CodeInfo(
                                code=code,
                                description=description,
                                conditions="Conditions not available",
                                has_description=has_description,
                                has_conditions=has_conditions
                            ))
        
        # Remove duplicate codes
        unique_codes = {}

        for code_info in detailed_codes:
            if code_info.code not in unique_codes:
                unique_codes[code_info.code] = code_info
            else:
                # If duplicate, prefer the one with more info
                existing = unique_codes[code_info.code]
                if (code_info.has_description and not existing.has_description) or \
                   (code_info.has_conditions and not existing.has_conditions):
                    unique_codes[code_info.code] = code_info
        
        # Store in cache before returning
        resp_obj = DetailedCodesResponse(codes=list(unique_codes.values()))
        _cache_set("codes_detailed_chatgpt", key, resp_obj)
        return resp_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating detailed codes with ChatGPT: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        timeout_keep_alive=120  # Increase timeout to prevent connection drops during long searches
    )
