"""
Routers package - Modular endpoint organization
"""
from .system import router as system_router
from .hosts import router as hosts_router
from .items import router as items_router
from .triggers import router as triggers_router
from .problems import router as problems_router
from .history import router as history_router
from .other import all_routers as other_routers

# Export all routers for easy import
__all__ = [
    'system_router',
    'hosts_router',
    'items_router',
    'triggers_router',
    'problems_router',
    'history_router',
    'other_routers'
]
