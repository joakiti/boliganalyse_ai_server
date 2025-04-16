# tests/repositories/test_listing_repository.py
import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
import os
from typing import AsyncGenerator, List, Dict, Any

# Ensure dotenv is loaded before other imports (if pytest-dotenv is used, this might be redundant but safe)
# from dotenv import load_dotenv
# load_dotenv() # pytest-dotenv plugin handles this automatically if installed

# --- Imports of code under test and dependencies ---
from supabase import Client, create_client # Import Client for type hinting
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.status import AnalysisStatus
from src.app.core.db import get_supabase_admin_client # The actual function to get the client

# --- Constants ---
TEST_SCHEMA = "private" # Make sure this matches your Supabase setup
TEST_TABLE = "listings" # Make sure this matches your Supabase table name

# --- Fixtures ---

@pytest.fixture(scope="session")
def supabase_client() -> Client:
    """Provides a session-scoped Supabase admin client instance."""
    # Assuming get_supabase_admin_client correctly uses env vars loaded by pytest-dotenv
    client = get_supabase_admin_client()
    # Simple check to see if client seems configured - replace with a more robust check if needed
    if not client or not hasattr(client, 'table'):
         pytest.fail("Supabase client could not be initialized. Check .env file and Supabase URL/Key.", pytrace=False)
    # No yield needed here as the client object itself manages connections usually
    return client

@pytest.fixture(scope="function")
def listing_repo(supabase_client: Client) -> ListingRepository:
    """
    Provides a ListingRepository instance for each test function.
    It implicitly uses the same client logic as the application.
    """
    # The repository likely calls get_supabase_admin_client() internally.
    # We pass the client here mainly for consistency or if we wanted
    # to potentially inject a test-specific client in the future,
    # but the repo itself should fetch its own client via the getter.
    # If ListingRepository takes client in __init__, use:
    # return ListingRepository(db_client=supabase_client)
    # Otherwise, if it uses the getter internally:
    return ListingRepository() # Assuming it calls get_supabase_admin_client()

@pytest.fixture(scope="function", autouse=True)
def cleanup_listings(supabase_client: Client) -> Generator[List[uuid.UUID], None, None]:
    """
    Auto-used fixture to clean up listings created during a test function.
    Yields a list to which test functions can append the IDs of created listings.
    """
    created_listing_ids: List[uuid.UUID] = []
    yield created_listing_ids # Hand control to the test, passing the list

    # --- Teardown ---
    if not created_listing_ids:
        return # Nothing to clean up

    print(f"\nCleaning up {len(created_listing_ids)} test listings...")
    try:
        # Use the direct client for cleanup
        delete_op = supabase_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
            .delete()\
            .in_("id", [str(uid) for uid in created_listing_ids])\
            .execute()

        if hasattr(delete_op, 'error') and delete_op.error:
             print(f"Warning: Error during cleanup: {delete_op.error}")
        elif hasattr(delete_op, 'data') and delete_op.data:
             print(f"Cleaned up {len(delete_op.data)} listings.")
        else:
             # Handle cases where the response structure might differ or be empty on success
             print(f"Cleanup operation executed for IDs: {created_listing_ids}. Response structure might vary.")

    except Exception as e:
        print(f"ERROR during listing cleanup: {e}")
        # Optionally re-raise or handle more gracefully depending on test requirements
        # raise # Uncomment to make cleanup failures fail the test session


# --- Helper Function ---
def generate_unique_url(base="https://test.example.com/listing/") -> str:
    return f"{base}{uuid.uuid4()}"

# --- Test Cases ---

# Removed asyncio marker
def test_create_listing(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test creating a new listing successfully."""
    test_url = generate_unique_url()
    # Assuming your normalize_url logic is tested elsewhere or simple
    normalized_url = test_url.replace("https://", "").replace("http://", "")

    created_listing = listing_repo.create_listing(test_url, normalized_url)

    assert created_listing is not None
    assert "id" in created_listing
    assert isinstance(uuid.UUID(created_listing["id"]), uuid.UUID) # Check if valid UUID
    assert created_listing["url"] == test_url
    assert created_listing["normalized_url"] == normalized_url
    assert created_listing["status"] == AnalysisStatus.PENDING.value
    assert created_listing["analysis_result"] is None
    assert created_listing["error_message"] is None
    assert created_listing["metadata"] is None
    assert "created_at" in created_listing
    assert "updated_at" in created_listing
    assert created_listing["created_at"] is not None
    assert created_listing["updated_at"] is not None

    # Add ID to cleanup list
    cleanup_listings.append(uuid.UUID(created_listing["id"]))

    # Optional: Direct verification (requires supabase_client fixture)
    # verify_client = get_supabase_admin_client() # Or use the fixture
    # result = verify_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
    #     .select("*").eq("id", created_listing["id"]).maybe_single().execute()
    # assert result.data is not None
    # assert result.data["url"] == test_url


# Removed asyncio marker
def test_find_by_normalized_url_found(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID]):
    """Test finding a listing by normalized URL when it exists."""
    test_url = generate_unique_url()
    normalized_url = test_url.replace("https://", "").replace("http://", "")

    # 1. Create the listing first
    created_listing = listing_repo.create_listing(test_url, normalized_url)
    assert created_listing is not None
    created_id = uuid.UUID(created_listing["id"])
    cleanup_listings.append(created_id) # Ensure cleanup

    # 2. Try to find it
    found_listing = listing_repo.find_by_normalized_url(normalized_url)

    assert found_listing is not None
    assert uuid.UUID(found_listing["id"]) == created_id
    assert found_listing["url"] == test_url
    assert found_listing["normalized_url"] == normalized_url


# Removed asyncio marker
def test_find_by_normalized_url_not_found(listing_repo: ListingRepository):
    """Test finding a listing by normalized URL when it does not exist."""
    non_existent_normalized_url = f"nonexistent.example.com/listing/{uuid.uuid4()}"

    found_listing = listing_repo.find_by_normalized_url(non_existent_normalized_url)

    assert found_listing is None


# Removed asyncio marker
def test_update_status(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID], supabase_client: Client):
    """Test updating the status of a listing."""
    test_url = generate_unique_url()
    normalized_url = test_url.replace("https://", "").replace("http://", "")
    created_listing = listing_repo.create_listing(test_url, normalized_url)
    created_id = uuid.UUID(created_listing["id"])
    cleanup_listings.append(created_id)

    new_status = AnalysisStatus.PROCESSING

    listing_repo.update_status(created_id, new_status)

    # Verify directly in DB
    result = supabase_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
        .select("status, updated_at").eq("id", str(created_id)).maybe_single().execute()

    assert result.data is not None
    assert result.data["status"] == new_status.value
    # Check if updated_at timestamp has likely changed (hard to be exact)
    original_updated_at = datetime.fromisoformat(created_listing["updated_at"])
    current_updated_at = datetime.fromisoformat(result.data["updated_at"])
    assert current_updated_at > original_updated_at


# Removed asyncio marker
def test_set_error_status(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID], supabase_client: Client):
    """Test setting an error status and message."""
    test_url = generate_unique_url()
    normalized_url = test_url.replace("https://", "").replace("http://", "")
    created_listing = listing_repo.create_listing(test_url, normalized_url)
    created_id = uuid.UUID(created_listing["id"])
    cleanup_listings.append(created_id)

    error_status = AnalysisStatus.SCRAPING_FAILED
    error_instance = ValueError("Something went wrong during scraping")
    expected_error_message = f"{type(error_instance).__name__}: {error_instance}"

    listing_repo.set_error_status(created_id, error_status, error_instance)

    # Verify directly in DB
    result = supabase_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
        .select("status, error_message, updated_at").eq("id", str(created_id)).maybe_single().execute()

    assert result.data is not None
    assert result.data["status"] == error_status.value
    assert result.data["error_message"] == expected_error_message
    original_updated_at = datetime.fromisoformat(created_listing["updated_at"])
    current_updated_at = datetime.fromisoformat(result.data["updated_at"])
    assert current_updated_at > original_updated_at


# Removed asyncio marker
def test_save_analysis_result(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID], supabase_client: Client):
    """Test saving analysis results."""
    test_url = generate_unique_url()
    normalized_url = test_url.replace("https://", "").replace("http://", "")
    created_listing = listing_repo.create_listing(test_url, normalized_url)
    created_id = uuid.UUID(created_listing["id"])
    cleanup_listings.append(created_id)

    # Set an error first to ensure save_analysis clears it
    listing_repo.set_error_status(created_id, AnalysisStatus.ANALYSIS_FAILED, ValueError("Previous error"))

    analysis_data = {"price": 5000000, "size_m2": 75, "rooms": 3}

    listing_repo.save_analysis_result(created_id, analysis_data)

    # Verify directly in DB
    result = supabase_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
        .select("status, error_message, analysis_result, updated_at").eq("id", str(created_id)).maybe_single().execute()

    assert result.data is not None
    assert result.data["status"] == AnalysisStatus.COMPLETED.value
    assert result.data["error_message"] is None # Error should be cleared
    assert result.data["analysis_result"] == analysis_data
    original_updated_at = datetime.fromisoformat(created_listing["updated_at"]) # This might be inaccurate if set_error_status updated it
    current_updated_at = datetime.fromisoformat(result.data["updated_at"])
    # We can only assert it's a valid timestamp, comparing might be tricky
    assert isinstance(current_updated_at, datetime)


# Removed asyncio marker
def test_update_listing_metadata(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID], supabase_client: Client):
    """Test updating listing metadata."""
    test_url = generate_unique_url()
    normalized_url = test_url.replace("https://", "").replace("http://", "")
    created_listing = listing_repo.create_listing(test_url, normalized_url)
    created_id = uuid.UUID(created_listing["id"])
    cleanup_listings.append(created_id)

    metadata = {"source": "TestSource", "scraped_at": datetime.now(timezone.utc).isoformat(), "version": 1}

    listing_repo.update_listing_metadata(created_id, metadata)

    # Verify directly in DB
    result = supabase_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
        .select("metadata, updated_at").eq("id", str(created_id)).maybe_single().execute()

    assert result.data is not None
    assert result.data["metadata"] == metadata
    original_updated_at = datetime.fromisoformat(created_listing["updated_at"])
    current_updated_at = datetime.fromisoformat(result.data["updated_at"])
    assert current_updated_at > original_updated_at

# --- Optional: Test Database Constraints (Example) ---

# # Removed asyncio marker
# def test_create_listing_duplicate_normalized_url_fails(listing_repo: ListingRepository, cleanup_listings: List[uuid.UUID], supabase_client: Client):
#     """
#     Test that creating a listing with a duplicate normalized_url fails
#     if there's a UNIQUE constraint on the 'normalized_url' column in the database.
#     NOTE: This test assumes such a constraint exists. It might fail otherwise.
#     """
#     test_url = generate_unique_url()
#     normalized_url = test_url.replace("https://", "").replace("http://", "")

#     # 1. Create the first listing
#     created_listing = listing_repo.create_listing(test_url, normalized_url)
#     assert created_listing is not None
#     created_id = uuid.UUID(created_listing["id"])
#     cleanup_listings.append(created_id) # Ensure cleanup

#     # 2. Attempt to create another listing with the *same* normalized_url
#     another_test_url = generate_unique_url("https://another.domain/") # Different URL, same normalized path part if logic is simple
#     # Or just use the exact same URL if normalization is robust:
#     # another_test_url = test_url

#     # We expect a database error (e.g., Supabase specific error or a generic DB error)
#     # The exact exception type might depend on the db driver and Supabase client behavior.
#     # You might need to inspect the actual error raised during a manual test run.
#     # Let's assume it might raise a generic Exception for now, or potentially
#     # something like `postgrest.exceptions.APIError` if using raw postgrest.
#     # The Supabase client might wrap this.
#     with pytest.raises(Exception) as excinfo: # Replace Exception with a more specific error if known
#         listing_repo.create_listing(another_test_url, normalized_url)

#     # Check if the error message indicates a unique constraint violation
#     # This message is specific to PostgreSQL and might change.
#     assert "duplicate key value violates unique constraint" in str(excinfo.value).lower()
#     # Or check for a specific error code if available from the exception object

#     # Verify only one listing exists
#     result = supabase_client.schema(TEST_SCHEMA).table(TEST_TABLE)\
#         .select("id", count='exact').eq("normalized_url", normalized_url).execute()
#     assert result.count == 1