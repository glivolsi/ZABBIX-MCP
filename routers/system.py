"""
System endpoints - Health check, version, authentication
"""
from fastapi import APIRouter, HTTPException, Depends
from zabbix_client import ZabbixClient, ZabbixAPIError

router = APIRouter(tags=["System"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "zabbix-mcp-server"}


@router.get("/api/version")
async def get_api_version(client: ZabbixClient = Depends(get_zabbix_client)):
    """
    Get Zabbix API version

    Returns the version of the connected Zabbix API server.
    """
    try:
        version = await client.get_api_version()
        return {"version": version}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/auth")
async def authenticate(client: ZabbixClient = Depends(get_zabbix_client)):
    """
    Authenticate with Zabbix server

    Establishes an authenticated session with the Zabbix server using configured credentials.
    """
    try:
        await client.authenticate()
        return {"status": "authenticated", "message": "Successfully authenticated with Zabbix"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=401, detail=str(e))
