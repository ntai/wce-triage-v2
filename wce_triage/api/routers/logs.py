from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...lib.log_store import LogEventType, get_log_store

router = APIRouter()


class LogEntry(BaseModel):
  id: int
  timestamp: str
  type: LogEventType
  level: Optional[str] = None
  source: Optional[str] = None
  message: Optional[str] = None
  data: Optional[Dict[str, Any]] = None
  pass


class LogsResponse(BaseModel):
  start: int
  count: int
  total: int
  logs: List[LogEntry]
  pass


class LogFacets(BaseModel):
  """Distinct values seen in the log so far, for populating filter dropdown
  options client-side. type/level are fixed/known sets (LogEventType, Python
  logging levelnames) so only source - open-ended, e.g. logger names or
  runner ids - actually needs to be queried."""
  sources: List[str]
  pass


@router.get("/logs", operation_id="route_logs")
def route_logs(
    start: int = Query(default=0, ge=0),
    count: int = Query(default=100, ge=1, le=1000),
    type_: List[LogEventType] = Query(default=[], alias="type"),
    level: List[str] = Query(default=[]),
    source: List[str] = Query(default=[]),
    q: Optional[str] = Query(default=None, description="substring filter on message text"),
    sort: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> LogsResponse:
  """Browse the sqlite-backed operational log: generic log lines, user
  messages/errors, progress reports, task plans, and command start/end."""
  rows, total = get_log_store().query(
    start=start, count=count,
    event_types=type_ or None, levels=level or None, sources=source or None,
    q=q, sort_desc=(sort == "desc"))
  return LogsResponse(start=start, count=count, total=total, logs=[LogEntry(**row) for row in rows])


@router.get("/logs/facets", operation_id="route_logs_facets")
def route_logs_facets() -> LogFacets:
  return LogFacets(sources=get_log_store().distinct_sources())
