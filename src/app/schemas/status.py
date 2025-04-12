from enum import Enum

class AnalysisStatus(str, Enum):
    """Represents the status of a listing analysis."""
    PENDING = "pending"
    QUEUED = "queued"
    FETCHING_HTML = "fetching_html"
    PARSING_DATA = "parsing_data"
    PREPARING_ANALYSIS = "preparing_analysis"
    GENERATING_INSIGHTS = "generating_insights"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    ERROR = "error"
    INVALID_URL = "invalid_url"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"