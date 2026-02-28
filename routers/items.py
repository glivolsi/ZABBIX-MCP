"""
Item management endpoints - Monitoring metrics
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional
from zabbix_client import ZabbixClient, ZabbixAPIError, ReadOnlyModeError
from config import settings

router = APIRouter(prefix="/api/items", tags=["Items"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


class ItemCreateRequest(BaseModel):
    """Request to create a monitoring item"""
    hostid: str = Field(..., description="ID of the host")
    name: str = Field(..., description="Display name of the item")
    key: str = Field(..., description="Item key (e.g., 'system.cpu.load[,avg1]')")
    type: int = Field(..., description="Item type: 0=Zabbix agent, 2=Trapper, 3=Simple check")
    value_type: int = Field(..., description="Value type: 0=float, 1=char, 2=log, 3=unsigned, 4=text")
    delay: Optional[str] = Field("1m", description="Update interval (e.g., '30s', '1m', '1h')")


@router.get("", summary="List monitoring items")
async def get_items(
    hostids: Optional[str] = Query(None, description="Comma-separated host IDs"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get monitoring items (metrics)**

    Use this to:
    - See what metrics are being collected
    - Find items by host
    - Check item configuration and keys

    Items are individual metrics like CPU load, memory usage, disk space, etc.
    """
    try:
        params = {}
        if hostids:
            params["hostids"] = hostids.split(",")

        items = await client.get_items(**params)
        return {"items": items, "count": len(items)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", summary="Create a new monitoring item", include_in_schema=not settings.zabbix_readonly)
async def create_item(
    request: ItemCreateRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Create a new monitoring item**

    Use this to:
    - Add a new metric to collect from a host
    - Set up custom monitoring for specific data points
    - Configure trapper items for external data

    Common item keys:
    - system.cpu.load[,avg1] - CPU load
    - vm.memory.size[available] - Available memory
    - vfs.fs.size[/,used] - Disk usage
    """
    try:
        result = await client.create_item(
            hostid=request.hostid,
            name=request.name,
            key=request.key,
            item_type=request.type,
            value_type=request.value_type,
            delay=request.delay
        )
        return {"success": True, "itemid": result["itemids"][0], "message": "Item created successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{itemid}", summary="Delete a monitoring item", include_in_schema=not settings.zabbix_readonly)
async def delete_item(
    itemid: str,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Delete a monitoring item**

    Use this to:
    - Remove metrics that are no longer needed
    - Clean up unused items

    Warning: Historical data for this item will be deleted.
    """
    try:
        await client.delete_item([itemid])
        return {"success": True, "message": "Item deleted successfully"}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
