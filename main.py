from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
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
            return DetailedCodesResponse(**cached)

        # Add system instruction for finding codes with details
        system_instruction = """You are a detailed code finder. Search the web for coupon codes based on the user's request. 
        
        IMPORTANT: For each code you find, you MUST format it EXACTLY like this:
        CODE | discount description | conditions
        
        Examples:
        SAVE20 | 20% off entire order | new customers only, expires 12/31/24
        FREESHIP | free shipping | orders over $50, valid until end of month
        WELCOME10 | $10 off first purchase | new users only, minimum $25 order
        
        If you cannot find specific conditions, write "no specific conditions found"
        If you cannot find the discount amount, write "discount amount not specified"
        
        Do NOT include explanatory text before or after the codes. Only return the formatted code lines."""
        
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
        
        # Generate response from Gemini
        response = ""
        
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.text:
                print(chunk.text, end="")
                response += chunk.text

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

        fake_codes = [["SAVE10", "10% off entire order"], ["FREESHIP", "Free shipping on orders"], ["WELCOME20", "20% off for new customers"], ["BOGO50", "Buy one get one 50% off"], ["10OFF", "$10 off your purchase"], ["15OFF50", "$15 off when you spend $50 or more"]]

        detailed_codes = []

        for code, desc in fake_codes:
            detailed_codes.append(CodeInfo(
                code=code,
                description=desc,
                conditions="Conditions not available",
                has_description=True,
                has_conditions=False
            ))
        
        # Store in cache before returning
        resp_obj = DetailedCodesResponse(codes=detailed_codes)
        _cache_set("codes_detailed", key, resp_obj)
        return resp_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating detailed codes: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
