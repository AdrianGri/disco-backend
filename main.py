from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
import os
import json
import time
from dotenv import load_dotenv
from threading import RLock

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

# Simple in-memory caches (MVP)
cache_generate = {}
cache_codes = {}
cache_detailed_codes = {}
cache_lock = RLock()

# Add a 1-hour TTL and simple cache helpers
CACHE_TTL_SECONDS = 60 * 60

def _cache_get(cache: dict, key: str):
    now = time.time()
    with cache_lock:
        entry = cache.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at is None or now < expires_at:
            return value
        # Expired: remove and miss
        try:
            del cache[key]
        except KeyError:
            pass
        return None

def _cache_set(cache: dict, key: str, value, ttl: int = CACHE_TTL_SECONDS):
    expires_at = (time.time() + ttl) if ttl else None
    with cache_lock:
        cache[key] = (value, expires_at)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Gemini API Server is running"}

@app.post("/generate", response_model=PromptResponse)
async def generate_response(request: PromptRequest):
    """
    Generate a response using Gemini API
    
    Args:
        request: PromptRequest containing the prompt string
        
    Returns:
        PromptResponse containing Gemini's response
    """
    try:
        # Cache check (MVP)
        key = request.prompt.strip()
        cached = _cache_get(cache_generate, key)
        if cached is not None:
            return cached

        # Add system instruction for concise responses
        system_instruction = "You are a concise assistant. Provide direct, brief answers without explanations, duplications, or additional context. When asked for codes or specific information, output only what was requested in a clean format, nothing more."
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"{system_instruction}\n\nUser request: {request.prompt}"),
                ],
            )
        ]
        tools = [
        types.Tool(googleSearch=types.GoogleSearch(
        )),
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
            print(chunk.text, end="")
            response += chunk.text

        # Clean up response - remove duplications and extra whitespace
        response = response.strip()
        
        # Remove obvious duplications (if the same text appears twice)
        lines = response.split('\n')
        seen = set()
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                cleaned_lines.append(line)
        
        if cleaned_lines:
            response = '\n'.join(cleaned_lines)

        if not response:
            raise HTTPException(status_code=500, detail="No response generated from Gemini")

        # Store in cache before returning
        resp_obj = PromptResponse(response=response)
        _cache_set(cache_generate, key, resp_obj)
        return resp_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.post("/codes", response_model=CodesResponse)
async def get_codes(request: PromptRequest):
    """
    Get codes using web search and parse into structured format
    
    Args:
        request: PromptRequest containing the prompt string
        
    Returns:
        CodesResponse containing a list of codes
    """
    try:
        # Cache check (MVP)
        key = request.prompt.strip()
        cached = _cache_get(cache_codes, key)
        if cached is not None:
            return cached

        # Add system instruction for finding codes
        system_instruction = "You are a code finder. Search the web for coupon codes based on the user's request. Return only the actual codes you find, separated by commas or on new lines. Include any conditions or restrictions if mentioned (e.g., minimum purchase, new customers only, expiration dates). Format: CODE - description/conditions. Do not include long explanations."
        
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

        # Parse the response to extract codes
        codes = []
        
        # Clean up response first
        response = response.strip()
        
        # Common words that are not codes
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
            'CURRENTLY', 'WEBSITE', 'ONLINE', 'STORE', 'PURCHASE', 'CHECKOUT'
        }
        
        # Split by common separators and clean each part
        for separator in [',', '\n', ';']:
            if separator in response:
                parts = response.split(separator)
                for part in parts:
                    code = part.strip().upper()
                    # Enhanced validation: codes are usually alphanumeric, reasonable length, and not common words
                    if (code and len(code) >= 3 and len(code) <= 20 and 
                        code.replace('-', '').replace('_', '').isalnum() and
                        code not in excluded_words and
                        code not in codes):
                        codes.append(code)
                break
        
        # If no separators found, try to extract individual words that look like codes
        if not codes:
            words = response.split()
            for word in words:
                word = word.strip('.,!?()[]{}').upper()
                if (word and len(word) >= 3 and len(word) <= 20 and 
                    word.replace('-', '').replace('_', '').isalnum() and
                    word not in excluded_words and
                    word not in codes):
                    codes.append(word)
        
        # Store in cache before returning
        resp_obj = CodesResponse(codes=codes)
        _cache_set(cache_codes, key, resp_obj)
        return resp_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating codes: {str(e)}")

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
        cached = _cache_get(cache_detailed_codes, key)
        if cached is not None:
            return cached

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
        
        # Store in cache before returning
        resp_obj = DetailedCodesResponse(codes=detailed_codes)
        _cache_set(cache_detailed_codes, key, resp_obj)
        return resp_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating detailed codes: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
