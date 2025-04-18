# tests/repositories/test_listing_repository.py
import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
import os
from typing import AsyncGenerator, List, Dict, Any, Generator, Optional

# Ensure dotenv is loaded before other imports (if pytest-dotenv is used, this might be redundant but safe)
# from dotenv import load_dotenv
# load_dotenv() # pytest-dotenv plugin handles this automatically if installed

# --- Imports of code under test and dependencies ---
from supabase import Client, create_client, AsyncClient
from postgrest import APIResponse
# Commented out as CountMethod might not exist in postgrest.utils
# from postgrest.utils import CountMethod
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.status import AnalysisStatus
from src.app.schemas.database import Listing
from src.app.lib.supabase_client import get_supabase_admin_client

# --- Constants ---
TEST_SCHEMA = "private" # Using private schema
TEST_TABLE = "apartment_listings"

# --- Fixtures ---

@pytest_asyncio.fixture(scope="session")
async def db_client() -> AsyncClient:
    """Provides a session-scoped Supabase async admin client instance."""
    try:
        client: AsyncClient = await get_supabase_admin_client()

        # Perform a simple check against the correct schema and table
        # Remove the count parameter which is causing type errors
        response = await client.schema(TEST_SCHEMA).table(TEST_TABLE).select("id").limit(0).execute()

        if isinstance(response, APIResponse) and response.data is not None:
             return client
        else:
            # Make error message slightly more specific if connection check fails
            error_detail = getattr(response, 'error', 'Unknown error')
            raise Exception(f"Supabase connection check failed for {TEST_SCHEMA}.{TEST_TABLE}: {error_detail}")
    except Exception as e:
        pytest.fail(f"Supabase client could not be initialized for tests: {e}. Check .env/credentials.", pytrace=False)

@pytest.fixture(scope="function")
def listing_repo(db_client: AsyncClient) -> ListingRepository:
    """
    Provides a ListingRepository instance initialized with a client for each test function.
    """
    # Pass the async-obtained client. The repo's constructor expects AsyncClient | None
    return ListingRepository(supabase_client=db_client)

@pytest.fixture(scope="function", autouse=True)
async def cleanup_listings(db_client: AsyncClient) -> AsyncGenerator[List[uuid.UUID], None]:
    """
    Auto-used async fixture to clean up listings created during a test function.
    Yields a list to which test functions can append the IDs of created listings.
    Now async and targets the correct schema.
    """
    created_listing_ids: List[uuid.UUID] = []
    yield created_listing_ids # Hand control to the test

    # --- Teardown ---
    if not created_listing_ids:
        return

    print(f"\nCleaning up {len(created_listing_ids)} test listings from schema '{TEST_SCHEMA}'...")
    try:
        # Use await and specify the correct schema for cleanup
        delete_op: APIResponse = await db_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
            .delete()\
            .in_("id", [str(uid) for uid in created_listing_ids])\
            .execute()

        # Response handling might vary slightly with async client, adjust if needed
        if hasattr(delete_op, 'data') and delete_op.data is not None:
            # Supabase delete often returns the deleted records
            print(f"Cleaned up {len(delete_op.data)} listings.")
        elif hasattr(delete_op, 'error') and delete_op.error:
             print(f"Warning: Error during cleanup: {delete_op.error}")
        else:
             print(f"Cleanup operation executed for IDs: {created_listing_ids}. Check response manually if needed.")

    except Exception as e:
        print(f"ERROR during listing cleanup: {e}")
        # Consider failing the test if cleanup fails critically
        # pytest.fail(f"Listing cleanup failed: {e}")

# --- Helper Function ---
def generate_unique_url(base="https://test.example.com/listing/") -> str:
    return f"{base}{uuid.uuid4()}"

def normalize_test_url(url: str) -> str:
    # Simple normalization for tests, align with your actual logic if different
    return url.replace("https://", "").replace("http://", "").rstrip('/')

# --- Test Cases ---

@pytest.mark.asyncio
async def test_create_or_get_listing_creation(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test create_or_get_listing when the listing does not exist (creation path)."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)

    # Call the method under test
    created_listing = await listing_repo.create_or_get_listing(test_url, normalized_url)

    assert created_listing is not None
    assert isinstance(created_listing, Listing)
    assert created_listing.id is not None
    assert isinstance(created_listing.id, uuid.UUID)
    assert created_listing.url == test_url
    assert created_listing.normalized_url == normalized_url
    assert created_listing.status == AnalysisStatus.PENDING
    assert created_listing.analysis_result is None
    assert created_listing.error_message is None
    # Removed metadata assertion
    assert created_listing.created_at is not None
    assert created_listing.updated_at is not None
    assert isinstance(created_listing.created_at, datetime)
    assert isinstance(created_listing.updated_at, datetime)

    # Add ID to cleanup list
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)

@pytest.mark.asyncio
async def test_create_or_get_listing_existing(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test create_or_get_listing when the listing already exists (get path)."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)

    # 1. Create the listing first directly using create()
    initial_listing = Listing(url=test_url, normalized_url=normalized_url, status=AnalysisStatus.PENDING)
    created_listing = await listing_repo.create(initial_listing)
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)

    # 2. Call create_or_get_listing with the same normalized_url
    retrieved_listing = await listing_repo.create_or_get_listing(test_url, normalized_url)

    assert retrieved_listing is not None
    assert isinstance(retrieved_listing, Listing)
    assert retrieved_listing.id == created_listing.id # Should be the same listing
    assert retrieved_listing.url == test_url
    assert retrieved_listing.normalized_url == normalized_url

@pytest.mark.asyncio
async def test_find_by_normalized_url_found(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test finding a listing by normalized URL when it exists."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)

    # 1. Create the listing first
    initial_listing = Listing(url=test_url, normalized_url=normalized_url, status=AnalysisStatus.PENDING)
    created_listing = await listing_repo.create(initial_listing)
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)

    # 2. Try to find it
    found_listing = await listing_repo.find_by_normalized_url(normalized_url)

    assert found_listing is not None
    assert isinstance(found_listing, Listing)
    assert found_listing.id == created_listing.id
    assert found_listing.url == test_url
    assert found_listing.normalized_url == normalized_url

@pytest.mark.asyncio
async def test_find_by_normalized_url_not_found(listing_repo: ListingRepository):
    """Test finding a listing by normalized URL when it does not exist."""
    non_existent_normalized_url = f"nonexistent.example.com/listing/{uuid.uuid4()}"

    found_listing = await listing_repo.find_by_normalized_url(non_existent_normalized_url)

    assert found_listing is None

@pytest.mark.asyncio
async def test_find_by_id_found(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test finding a listing by ID when it exists."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)
    initial_listing = Listing(url=test_url, normalized_url=normalized_url, status=AnalysisStatus.PENDING)
    created_listing = await listing_repo.create(initial_listing)
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)

    # Try to find it by ID
    found_listing = await listing_repo.find_by_id(created_listing.id)

    assert found_listing is not None
    assert isinstance(found_listing, Listing)
    assert found_listing.id == created_listing.id
    assert found_listing.url == test_url

@pytest.mark.asyncio
async def test_find_by_id_not_found(listing_repo: ListingRepository):
    """Test finding a listing by ID when it does not exist."""
    non_existent_id = uuid.uuid4() # Generate a random UUID unlikely to exist

    found_listing = await listing_repo.find_by_id(non_existent_id)

    assert found_listing is None

@pytest.mark.asyncio
async def test_update_status(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test updating the status of a listing."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)
    initial_listing = Listing(url=test_url, normalized_url=normalized_url, status=AnalysisStatus.PENDING)
    created_listing = await listing_repo.create(initial_listing)
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)
    original_updated_at = created_listing.updated_at
    assert original_updated_at is not None

    new_status = AnalysisStatus.ERROR # Use existing ERROR status instead of PROCESSING

    # Update the status
    updated_listing = await listing_repo.update_status(created_listing.id, new_status)

    assert updated_listing is not None
    assert isinstance(updated_listing, Listing)
    assert updated_listing.id == created_listing.id
    assert updated_listing.status == new_status
    # Check timestamp was updated (allow for small clock differences if needed)
    assert updated_listing.updated_at is not None
    assert updated_listing.updated_at > original_updated_at

    # Verify by fetching again (optional but good practice)
    fetched_listing = await listing_repo.find_by_id(created_listing.id)
    assert fetched_listing is not None
    assert fetched_listing.status == new_status

@pytest.mark.asyncio
async def test_update_listing_full(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test updating multiple fields of a listing using the update method."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)
    initial_listing = Listing(url=test_url, normalized_url=normalized_url, status=AnalysisStatus.PENDING)
    created_listing = await listing_repo.create(initial_listing)
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)
    original_created_at = created_listing.created_at
    original_updated_at = created_listing.updated_at
    assert original_updated_at is not None

    # Get the listing to modify
    listing_to_update = await listing_repo.find_by_id(created_listing.id)
    assert listing_to_update is not None
    
    # Modify the listing and update it
    listing_to_update.status = AnalysisStatus.COMPLETED
    listing_to_update.analysis_result = {"score": 0.85, "summary": "Looks good"}
    listing_to_update.error_message = None
    listing_to_update.url_redirect = "https://new.example.com/listing/123"

    # Call update method with the listing object
    updated_listing = await listing_repo.update(listing_to_update)

    assert updated_listing is not None
    assert isinstance(updated_listing, Listing)
    assert updated_listing.id == created_listing.id
    assert updated_listing.status == AnalysisStatus.COMPLETED
    assert updated_listing.analysis_result == {"score": 0.85, "summary": "Looks good"}
    assert updated_listing.error_message is None
    assert updated_listing.url_redirect == "https://new.example.com/listing/123"
    # Removed metadata assertion
    assert updated_listing.created_at == original_created_at # Created timestamp should not change
    assert updated_listing.updated_at is not None # Assert datetime not None
    assert updated_listing.updated_at > original_updated_at # Updated timestamp should change

    # Verify by fetching again
    fetched_listing = await listing_repo.find_by_id(created_listing.id)
    assert fetched_listing is not None
    assert fetched_listing.status == AnalysisStatus.COMPLETED
    # Removed metadata assertion

@pytest.mark.asyncio
async def test_save_new(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test saving a new listing using the save method."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)
    new_listing = Listing(
        url=test_url,
        normalized_url=normalized_url,
        status=AnalysisStatus.PENDING
        # Removed metadata
    )
    assert new_listing.id is None # Ensure it's new

    saved_listing = await listing_repo.save(new_listing)

    assert saved_listing is not None
    assert saved_listing.id is not None # Should have an ID now
    assert isinstance(saved_listing.id, uuid.UUID)
    assert saved_listing.url == test_url
    assert saved_listing.normalized_url == normalized_url
    assert saved_listing.status == AnalysisStatus.PENDING
    # Removed metadata assertion
    assert saved_listing.created_at is not None
    assert saved_listing.updated_at is not None

    assert saved_listing.id is not None
    cleanup_listings.append(saved_listing.id)

@pytest.mark.asyncio
async def test_save_existing(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test saving an existing listing using the save method (should perform an update)."""
    test_url = generate_unique_url()
    normalized_url = normalize_test_url(test_url)

    # 1. Create initial listing
    initial_listing = Listing(url=test_url, normalized_url=normalized_url, status=AnalysisStatus.PENDING)
    created_listing = await listing_repo.create(initial_listing)
    assert created_listing.id is not None
    cleanup_listings.append(created_listing.id)
    original_updated_at = created_listing.updated_at
    assert original_updated_at is not None

    # 2. Modify the listing object
    created_listing.status = AnalysisStatus.ERROR # Use ERROR instead of PROCESSING
    # Removed metadata update

    # 3. Save the modified listing object
    saved_listing = await listing_repo.save(created_listing)

    assert saved_listing is not None
    assert saved_listing.id == created_listing.id # ID should remain the same
    assert saved_listing.status == AnalysisStatus.ERROR
    # Removed metadata assertion
    assert saved_listing.updated_at is not None # Assert datetime not None
    assert saved_listing.updated_at > original_updated_at # Timestamp should update

    # 4. Verify by fetching again
    fetched_listing = await listing_repo.find_by_id(created_listing.id)
    assert fetched_listing is not None
    assert fetched_listing.status == AnalysisStatus.ERROR
    # Removed metadata assertion

# Potential test for unique constraint (requires constraint in DB)
# @pytest.mark.asyncio
# async def test_create_listing_duplicate_normalized_url_fails(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID], db_client: Client):
#     """ ... (similar structure, use await, check for specific DB error) ... """
#     pass # Implementation requires knowing the exact exception

# Note: The db_client fixture setup might need refinement based on how async
# initialization and potential test isolation (e.g., transactions) are handled.