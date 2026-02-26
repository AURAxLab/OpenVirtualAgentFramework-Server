import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Any

class BaseTransport(ABC):
    """
    Abstract base class for all communication layers in OAF.
    Transports can be ZMQ, WebSockets or mock implementations.
    """
    
    def __init__(self):
        # List of callbacks to run when a message is received
        self._message_callbacks: list[Callable[[str], Awaitable[None]]] = []
        
    def register_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Register an async callback to trigger when messages arrive."""
        self._message_callbacks.append(callback)
        
    async def _dispatch_message(self, raw_message: str):
        """Called internally by implementations to bubble up a received message."""
        tasks = [callback(raw_message) for callback in self._message_callbacks]
        if tasks:
            await asyncio.gather(*tasks)

    @abstractmethod
    async def start(self):
        """Initialize connections and start listening to incoming messages."""
        pass
        
    @abstractmethod
    async def stop(self):
        """Gracefully close connections."""
        pass
        
    @abstractmethod
    async def publish(self, topic: str, message: str):
        """Send a message/command out to connected clients."""
        pass
