"""
BielikClient - Wrapper for Bielik LLM Service API calls

Provides clean interface to call Bielik's simplified endpoints:
- /generate: Raw text generation
- /chat: Chat completion (OpenAI compatible)
- /health: Service health check
"""

import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BielikClient:
    """Client for communicating with Bielik inference service."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 600):
        """
        Initialize Bielik client.
        
        Args:
            base_url: Base URL of Bielik service (e.g., http://localhost:8000)
            timeout: Request timeout in seconds (default 600 for GPU inference)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
    
    async def health_check(self) -> bool:
        """
        Check if Bielik service is healthy.
        
        Returns:
            True if service is running, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Bielik health check failed: {e}")
            return False
    
    async def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """
        Call Bielik /generate endpoint for raw text generation.
        
        Args:
            model: Model name (e.g., 'bielik-1.5b-transformer')
            prompt: Text prompt to continue
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            top_p: Nucleus sampling parameter (0.0-1.0)
            
        Returns:
            Generated text
            
        Raises:
            Exception: If request fails
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/generate",
                    json=payload
                )
                
                if response.status_code != 200:
                    raise Exception(f"Bielik error {response.status_code}: {response.text}")
                
                data = response.json()
                return data.get("text", "")
        
        except httpx.TimeoutException:
            raise Exception(f"Bielik request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Bielik /generate error: {e}")
            raise
    
    async def chat(
        self,
        model: str,
        messages: list,
        max_tokens: int = 150,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """
        Call Bielik /chat endpoint for chat completion.
        
        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            
        Returns:
            Assistant's response text
            
        Raises:
            Exception: If request fails
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat",
                    json=payload
                )
                
                if response.status_code != 200:
                    raise Exception(f"Bielik error {response.status_code}: {response.text}")
                
                data = response.json()
                # Extract message content from OpenAI-compatible response
                choices = data.get("choices", [])
                if choices and len(choices) > 0:
                    message = choices[0].get("message", {})
                    return message.get("content", "")
                return ""
        
        except httpx.TimeoutException:
            raise Exception(f"Bielik request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Bielik /chat error: {e}")
            raise
    
    async def get_models(self) -> list:
        """
        Get list of available models.
        
        Returns:
            List of model dicts with 'name', 'type', 'device'
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/models")
                
                if response.status_code != 200:
                    logger.warning(f"Failed to get models: {response.status_code}")
                    return []
                
                data = response.json()
                return data.get("models", [])
        
        except Exception as e:
            logger.warning(f"Failed to get models: {e}")
            return []
