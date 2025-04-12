# Migration Plan: TypeScript Edge Function to Python FastAPI Backend

This plan outlines the steps to migrate backend logic from the TypeScript Supabase Edge Function (`supabase/functions/analyze-apartment`) to the Python FastAPI application (`src/app`).

**Phase 1: Refactor Python Core Components**

1.  **Database Repository:**
    *   Create `src/app/repositories/listing_repository.py`.
    *   Implement `ListingRepository` class using `src/app/lib/supabase_client.py` (async).
    *   Implement methods: `find_by_normalized_url`, `create_listing`, `update_status`, `set_error_status`, `save_analysis_result`, `update_listing_metadata`.
    *   Define `AnalysisStatus` Enum in `src/app/schemas/status.py` mirroring TS version (`pending`, `queued`, `fetching_html`, `parsing_data`, `preparing_analysis`, `generating_insights`, `finalizing`, `completed`, `error`, `invalid_url`, `timeout`, `cancelled`).

2.  **Analysis Service Orchestration:**
    *   Refactor `src/app/services/analysis_service.py`.
    *   Inject `ListingRepository`.
    *   Use repository for DB operations in `start_analysis_task`.
    *   Implement granular status updates using `AnalysisStatus`.
    *   Add logic for secondary source handling (fetch, parse, combine text).
    *   Call `repository.update_listing_metadata`.
    *   Implement robust error handling (`set_error_status`).

**Phase 2: Implement AI Tool Calling (DST Only)**

3.  **Tooling Infrastructure:**
    *   Create `BaseTool` (`src/app/services/tools/base_tool.py`).
    *   Create `ToolRegistryService` (`src/app/services/tool_registry.py`).
    *   Define Pydantic models for tool calling (`src/app/schemas/tool_calling.py`).

4.  **Implement DST Tools:**
    *   Create Python implementations for `GetSubjectsTool`, `GetTablesTool`, `GetTableInfoTool`, `GetDataTool` in `src/app/services/tools/dst_api_tools.py` using `httpx`.
    *   Register only DST tools in `ToolRegistryService`.

5.  **AI Analyzer Service Enhancement:**
    *   Refactor `src/app/services/ai_analyzer.py`.
    *   Inject `ToolRegistryService`.
    *   Implement `analyze_with_tools` method (Claude API calls using `anthropic` library, tool use/result loop).
    *   Implement `make_claude_request` (headers, retries).
    *   Implement `extract_json_from_response`.
    *   Implement `analyze_multiple_texts`.
    *   Port the detailed analysis prompt from TS `ai-analyzer.ts`.

**Phase 3: Providers and Finalization**

6.  **Provider Review & Update:**
    *   Review Python providers (`src/app/lib/providers/`) against TS versions.
    *   Ensure accuracy (Boligsiden redirect, Danbolig cleaning).
    *   Update `provider_registry.py`.

7.  **Code Quality & Dependencies:**
    *   Apply PEP 8 and type hints.
    *   Ensure `requirements.txt` includes `anthropic`.
    *   Verify `config.py` has necessary API keys.

**Target Architecture Diagram:**

```mermaid
graph TD
    A[FastAPI Router: /analyze] --> B(Analysis Service);
    B -- Calls --> C{Listing Repository};
    B -- Calls --> D[Provider Registry];
    B -- Calls --> E(AI Analyzer Service);
    C -- Interacts with --> F[(Supabase DB: private.apartment_listings)];
    D -- Selects --> G[Provider Implementation];
    G -- Uses --> H{HTML Utils / Firecrawl};
    E -- Calls --> I{Tool Registry};
    E -- Interacts with --> J[(Claude API)];
    I -- Selects --> K[DST Tool Implementation]; // Only DST Tools
    K -- Calls --> L[External API: DST]; // Only DST API

    subgraph "src/app/routers"
        A
    end
    subgraph "src/app/services"
        B
        E
        I
        K
    end
    subgraph "src/app/repositories"
        C
    end
    subgraph "src/app/lib/providers"
        D
        G
    end
     subgraph "src/app/lib"
        H
    end
    subgraph "External"
        F
        J
        L
    end