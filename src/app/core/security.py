from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError
import logging
from typing import Optional

# Import Supabase client and settings
from src.app.lib.supabase_client import get_supabase_user_client # We might need user client later
from src.app.core.config import settings
from supabase_py_async import AsyncClient # Import AsyncClient for type hinting

logger = logging.getLogger(__name__)

# This scheme expects the token to be sent in the Authorization header as "Bearer <token>"
# The tokenUrl is not actually used for validation here, but FastAPI requires it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token") # Example token URL

class TokenData(BaseModel):
    # Define the expected structure of your JWT payload if needed
    # Example: sub: Optional[str] = None
    #          exp: Optional[int] = None
    pass # Add fields based on Supabase JWT structure if manual validation is done

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    # supabase: AsyncClient = Depends(get_supabase_user_client) # Inject user client if needed
) -> dict: # Return type can be more specific, e.g., a Pydantic model for User
    """
    Dependency function to verify Supabase JWT token and return user data.
    Currently uses Supabase's built-in verification via get_user().
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Use the admin client to verify the token against Supabase Auth
    # This is generally more reliable than manual JWT verification unless specific claims are needed
    try:
        # Need an admin client instance to call auth functions securely
        # Note: get_supabase_user_client requires the token itself, creating a circular dependency here.
        # We need a way to get an admin client instance without a token first.
        # Let's assume we have an admin client available (e.g., via another dependency or global)
        # For now, we'll placeholder this - requires adjustment in supabase_client or here.

        # --- Placeholder for getting admin client ---
        # This part needs refinement. Typically, you'd use the service role key
        # to create an admin client instance specifically for auth checks,
        # or rely on Supabase client library's internal handling if possible.
        # The `supabase-py-async` library's `auth.get_user(token)` handles verification.

        # Let's simulate getting an admin client for the auth call
        # In a real scenario, you might inject this differently.
        from src.app.lib.supabase_client import get_supabase_admin_client
        admin_client = await get_supabase_admin_client() # Use admin client for auth verification

        user_response = await admin_client.auth.get_user(token)
        user = user_response.user

        if not user:
            logger.warning("Token validation failed: No user returned by Supabase.")
            raise credentials_exception

        logger.info(f"Token validated successfully for user ID: {user.id}")
        # Return user data (e.g., as a dictionary or Pydantic model)
        # Be careful not to expose sensitive info if returning the whole user object
        return user.dict() # Convert UserResponse object to dict

    except JWTError as e:
        logger.error(f"JWT decoding error: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        # Catch potential errors during Supabase client interaction or get_user call
        logger.error(f"Error during token validation: {e}", exc_info=True)
        raise credentials_exception

# --- Manual JWT Verification (Alternative - Less Recommended with Supabase) ---
# Keep this commented out unless you have a specific reason to manually verify
# Requires SUPABASE_JWT_SECRET to be set correctly.

# ALGORITHM = "HS256"
#
# async def get_current_user_manual(token: str = Depends(oauth2_scheme)) -> TokenData:
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     if not settings.SUPABASE_JWT_SECRET:
#         logger.error("JWT Secret not configured for manual validation.")
#         raise HTTPException(status_code=500, detail="Auth configuration error")
#
#     try:
#         payload = jwt.decode(
#             token,
#             settings.SUPABASE_JWT_SECRET,
#             algorithms=[ALGORITHM],
#             # Add audience/issuer validation if needed
#             # options={"verify_aud": False} # Adjust based on Supabase token settings
#         )
#         # Extract relevant data from payload
#         # Example: username: str = payload.get("sub")
#         # if username is None:
#         #     raise credentials_exception
#         token_data = TokenData(**payload) # Validate payload structure
#     except JWTError as e:
#         logger.error(f"JWT Validation Error: {e}")
#         raise credentials_exception
#     except ValidationError as e:
#          logger.error(f"Token payload validation error: {e}")
#          raise credentials_exception
#     return token_data