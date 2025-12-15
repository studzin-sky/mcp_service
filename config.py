"""
MCP Service Configuration

Environment-based configuration for the MCP service.
"""

import os
from enum import Enum
from typing import Optional


class ValidationLevel(str, Enum):
    """Validation strictness levels"""
    STRICT = "strict"
    NORMAL = "normal"
    LENIENT = "lenient"


class MCPConfig:
    """MCP Service configuration"""
    
    # Service info
    SERVICE_NAME = "MCP (Model Context Protocol)"
    SERVICE_VERSION = "2.0.0"
    
    # Bielik service connection
    BIELIK_APP_URL = os.getenv("BIELIK_APP_URL", "http://localhost:8001")
    BIELIK_ENDPOINT = os.getenv("BIELIK_ENDPOINT", "/infill")
    BIELIK_TIMEOUT = int(os.getenv("BIELIK_TIMEOUT", "60"))
    
    # Server config
    HOST = os.getenv("MCP_HOST", "0.0.0.0")
    PORT = int(os.getenv("MCP_PORT", "8002"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Validation
    VALIDATION_LEVEL = ValidationLevel(os.getenv("VALIDATION_LEVEL", "normal"))
    
    # Content constraints
    MIN_DESCRIPTION_LENGTH = int(os.getenv("MIN_DESC_LENGTH", "50"))
    MAX_DESCRIPTION_LENGTH = int(os.getenv("MAX_DESC_LENGTH", "2000"))
    MAX_GAP_FILL_LENGTH = int(os.getenv("MAX_GAP_FILL", "100"))
    
    # Processing
    MAX_ALTERNATIVES_PER_GAP = int(os.getenv("MAX_ALTS", "5"))
    ENABLE_GRAMMAR_FIX = os.getenv("ENABLE_GRAMMAR_FIX", "true").lower() == "true"
    ENABLE_GUARDRAILS = os.getenv("ENABLE_GUARDRAILS", "true").lower() == "true"
    
    # Domain-specific config
    SUPPORTED_DOMAINS = ["cars", "products", "real_estate"]
    DEFAULT_DOMAIN = "cars"
    
    # Logging
    LOG_REQUESTS = os.getenv("LOG_REQUESTS", "true").lower() == "true"
    LOG_RESPONSES = os.getenv("LOG_RESPONSES", "false").lower() == "true"
    
    # Performance
    ENABLE_CACHING = os.getenv("ENABLE_CACHING", "false").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    
    @classmethod
    def get_bielik_url(cls, endpoint: Optional[str] = None) -> str:
        """Get full Bielik service URL"""
        ep = endpoint or cls.BIELIK_ENDPOINT
        base = cls.BIELIK_APP_URL.rstrip('/')
        return f"{base}{ep}"
    
    @classmethod
    def is_valid_domain(cls, domain: str) -> bool:
        """Check if domain is supported"""
        return domain.lower() in cls.SUPPORTED_DOMAINS
    
    @classmethod
    def to_dict(cls) -> dict:
        """Export config as dictionary"""
        return {
            "service_name": cls.SERVICE_NAME,
            "service_version": cls.SERVICE_VERSION,
            "bielik_url": cls.BIELIK_APP_URL,
            "bielik_endpoint": cls.BIELIK_ENDPOINT,
            "server": {
                "host": cls.HOST,
                "port": cls.PORT,
                "log_level": cls.LOG_LEVEL
            },
            "validation": {
                "level": cls.VALIDATION_LEVEL.value,
                "min_length": cls.MIN_DESCRIPTION_LENGTH,
                "max_length": cls.MAX_DESCRIPTION_LENGTH
            },
            "features": {
                "grammar_fix": cls.ENABLE_GRAMMAR_FIX,
                "guardrails": cls.ENABLE_GUARDRAILS,
                "caching": cls.ENABLE_CACHING
            }
        }


# Example environment file (.env)
"""
# Bielik Service Connection
BIELIK_APP_URL=http://bielik_app_service:8001
BIELIK_ENDPOINT=/infill
BIELIK_TIMEOUT=60

# MCP Service
MCP_HOST=0.0.0.0
MCP_PORT=8002
LOG_LEVEL=INFO

# Validation (strict|normal|lenient)
VALIDATION_LEVEL=normal

# Content Constraints
MIN_DESC_LENGTH=50
MAX_DESC_LENGTH=2000
MAX_GAP_FILL=100

# Features
ENABLE_GRAMMAR_FIX=true
ENABLE_GUARDRAILS=true
ENABLE_CACHING=false
CACHE_TTL=3600

# Logging
LOG_REQUESTS=true
LOG_RESPONSES=false
"""
