"""
Zabbix MCP Server - FastAPI application for connecting LLM with Zabbix
Supports both OpenAPI REST and MCP (Model Context Protocol) for Claude Desktop
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from contextlib import asynccontextmanager
from typing import Optional
import json
import asyncio

from config import settings
from zabbix_client import ZabbixClient, ZabbixAPIError, ReadOnlyModeError
from mcp_server import MCPServer

# Import all routers
from routers import (
    system_router,
    hosts_router,
    items_router,
    triggers_router,
    problems_router,
    history_router,
    other_routers
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global Zabbix client instance
zabbix_client: Optional[ZabbixClient] = None
mcp_server: Optional[MCPServer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application"""
    global zabbix_client, mcp_server

    # Startup
    logger.info("Starting Zabbix MCP Server...")
    zabbix_client = ZabbixClient(
        url=settings.zabbix_url,
        api_token=settings.zabbix_api_token,
        user=settings.zabbix_user,
        password=settings.zabbix_password
    )
    
    # Initialize MCP Server
    mcp_server = MCPServer(zabbix_client)
    logger.info("MCP Protocol server initialized")

    # Test connection
    try:
        version = await zabbix_client.get_api_version()
        logger.info(f"Connected to Zabbix API version: {version}")
        if zabbix_client.readonly:
            logger.warning("⚠️  Server running in READ-ONLY mode - write operations disabled")
        else:
            logger.info("✅ Server running with full read/write access")
    except Exception as e:
        logger.warning(f"Could not connect to Zabbix on startup: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Zabbix MCP Server...")


# Create FastAPI application
app = FastAPI(
    title="Zabbix MCP Server",
    description="Model Context Protocol server for connecting LLM with Zabbix monitoring system",
    version="1.0.0",
    lifespan=lifespan,
    openapi_version="3.1.0"
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include all routers
app.include_router(system_router)
app.include_router(hosts_router)
app.include_router(items_router)
app.include_router(triggers_router)
app.include_router(problems_router)
app.include_router(history_router)

# Include other routers
for router in other_routers:
    app.include_router(router)


# Exception handlers
@app.exception_handler(ZabbixAPIError)
async def zabbix_api_exception_handler(request, exc):
    """Handle Zabbix API errors"""
    return JSONResponse(
        status_code=500,
        content={"error": "Zabbix API Error", "detail": str(exc)}
    )


@app.exception_handler(ReadOnlyModeError)
async def readonly_mode_exception_handler(request, exc):
    """Handle read-only mode errors"""
    return JSONResponse(
        status_code=403,
        content={"error": "Operation Forbidden", "detail": str(exc)}
    )


# MCP Protocol Endpoint (for Claude Desktop)
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP (Model Context Protocol) endpoint for Claude Desktop and MCP Inspector
    Handles JSON-RPC 2.0 requests according to MCP specification
    """
    try:
        body = await request.json()
        logger.info(f"MCP Request: {body.get('method', 'unknown')} (id: {body.get('id', 'none')})")
        logger.debug(f"MCP Request details: {body}")
        
        response = await mcp_server.handle_request(body)
        logger.debug(f"MCP Response: {response}")
        
        # notifications don't require a response
        if response is None:
            return JSONResponse(content={}, status_code=202)
        
        return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"Error in MCP endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
        )


@app.get("/sse")
async def sse_endpoint(request: Request):
    """
    SSE (Server-Sent Events) endpoint for MCP protocol
    Used by Claude Desktop and MCP Inspector for persistent connection
    
    MCP SSE Transport Specification:
    1. Client connects to SSE endpoint
    2. Server MUST send an 'endpoint' event with the JSON-RPC endpoint URL
    3. Client uses that URL for all JSON-RPC requests (initialize, tools/list, tools/call)
    4. Server can push notifications via SSE when state changes
    5. Connection maintained with periodic keepalive comments
    
    SSE Message Formats:
    - Initial endpoint: 'event: endpoint' followed by 'data: <url>'
    - Notifications: 'event: message' followed by 'data: <json-rpc-notification>'
    - Keepalive: ': keepalive' (comment format, no event)
    """
    async def event_generator():
        try:
            logger.info("SSE connection established")
            
            # REQUIRED: Send endpoint URL as first message
            # This tells the MCP client where to send JSON-RPC requests
            # Build URL from request headers for proper hostname/port
            
            # Get host from request headers (includes port if present)
            host = request.headers.get("host")
            
            if not host:
                # Fallback: construct from request URL or use localhost
                if request.url.hostname:
                    hostname = request.url.hostname
                    port = request.url.port or settings.server_port
                    host = f"{hostname}:{port}" if port != 80 else hostname
                else:
                    # Last resort: use localhost with configured port
                    host = f"localhost:{settings.server_port}"
            
            # Determine scheme (http vs https)
            scheme = "https" if request.url.scheme == "https" else "http"
            
            # Build endpoint URL
            endpoint_url = f"{scheme}://{host}/mcp"
            
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"
            logger.info(f"SSE: Sent endpoint URL: {endpoint_url}")
            
            # Optional: Send server ready notification
            # This is a JSON-RPC notification to inform the client
            ready_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/message",
                "params": {
                    "level": "info",
                    "logger": "mcp-server",
                    "data": "Zabbix MCP server ready"
                }
            }
            yield f"event: message\ndata: {json.dumps(ready_notification)}\n\n"
            logger.info("SSE: Sent ready notification")
            
            # Keep connection alive with periodic pings
            # This maintains the connection for server-to-client notifications
            while True:
                await asyncio.sleep(30)
                # Send SSE comment for keepalive (doesn't trigger events in client)
                yield ": keepalive\n\n"
                
        except asyncio.CancelledError:
            logger.info("SSE connection closed by client")
        except Exception as e:
            logger.error(f"SSE error: {e}", exc_info=True)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept",
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
        log_level="info"
    )
