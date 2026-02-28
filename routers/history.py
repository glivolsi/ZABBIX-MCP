"""
History and trends endpoints - Historical data analysis
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from zabbix_client import ZabbixClient, ZabbixAPIError

router = APIRouter(prefix="/api", tags=["History"])


def get_zabbix_client() -> ZabbixClient:
    """Get the global Zabbix client instance"""
    from main import zabbix_client
    if zabbix_client is None:
        raise HTTPException(status_code=503, detail="Zabbix client not initialized")
    return zabbix_client


class HistoryRequest(BaseModel):
    """Request for history data"""
    itemids: List[str] = Field(..., description="List of item IDs")
    history_type: int = Field(0, description="History type: 0=float, 1=string, 2=log, 3=integer, 4=text")
    limit: int = Field(10, ge=1, le=1000, description="Number of records (1-1000)")


@router.post("/history", summary="Get historical monitoring data")
async def get_history(
    request: HistoryRequest,
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get history data for items (detailed metrics over time)**

    Use this to:
    - Analyze past performance and trends
    - Troubleshoot historical issues
    - Generate reports on metric values
    - See how values changed over time

    History types:
    - 0 = Float (decimal numbers, e.g., CPU load, percentages)
    - 1 = String/Character (text values)
    - 2 = Log (log file entries)
    - 3 = Integer (whole numbers, e.g., counts)
    - 4 = Text (long text values)

    For long-term analysis, consider using /api/trends instead (hourly aggregates).
    """
    try:
        history = await client.get_history(
            itemids=request.itemids,
            history_type=request.history_type,
            limit=request.limit
        )
        return {"history": history, "count": len(history)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends", summary="Get trend data (hourly aggregates)")
async def get_trends(
    itemids: str = Query(..., description="Comma-separated item IDs"),
    time_from: Optional[int] = Query(None, description="Start time (Unix timestamp)"),
    time_till: Optional[int] = Query(None, description="End time (Unix timestamp)"),
    client: ZabbixClient = Depends(get_zabbix_client)
):
    """
    **Get trend data (hourly aggregated statistics)**

    Use this to:
    - Analyze long-term trends efficiently
    - Get min/max/avg values for each hour
    - Generate reports for extended time periods
    - Reduce data volume for long time ranges

    Trends are more efficient than history for analyzing data older than a few days.
    Each record contains hourly min, max, and average values.
    """
    try:
        item_list = itemids.split(",")
        trends = await client.get_trends(
            itemids=item_list,
            time_from=time_from,
            time_till=time_till
        )
        return {"trends": trends, "count": len(trends)}
    except ZabbixAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
