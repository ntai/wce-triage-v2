"""sqlite3-backed store for operational history: generic log lines (tlog),
user messages/errors, progress reports, task plans, and subprocess command
start/end. Adds a second, queryable, timestamped destination alongside the
existing plain-text rotating log file and in-memory message list - tlog.*
calls still land in the text file too, sqlite is additive, not a
replacement.

Only the main FastAPI server process is expected to write here (see
install_sqlite_log_handler() and the callers of LogStore.log() in
api/server.py and api/internal/process_runner.py) - subprocess runners keep
using their existing NDJSON-over-stdout-pipe mechanism back to the parent.
"""
import atexit
import json
import logging
import os
import queue
import sqlite3
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class LogEventType(str, Enum):
  LOG = "LOG"                        # generic tlog.* call, via SQLiteLogHandler
  MESSAGE = "MESSAGE"                 # UserMessages.note()
  ERROR = "ERROR"                     # ErrorMessages.error() / severity==2 messages
  PROGRESS = "PROGRESS"               # task_progress/task_success/task_failure/run_progress
  PLAN = "PLAN"                       # report=="tasks" - the one-shot flight plan at preflight
  COMMAND_START = "COMMAND_START"     # subprocess launched
  COMMAND_END = "COMMAND_END"         # subprocess exited (returncode carried in `data`)
  pass


DEFAULT_MAX_BYTES = 512 * 1024 * 1024
WRITER_POLL_INTERVAL = 0.2
# Start pruning before the file actually hits the cap, since a prune cycle
# doesn't happen on every drain - leaves headroom for the WAL file to grow
# between checks without ever exceeding the cap in practice.
PRUNE_THRESHOLD = 0.9


def _default_db_path() -> str:
  # Mirrors lib/util.py's setup_triage_logger() root-vs-non-root convention,
  # independently (this module intentionally doesn't import from util.py).
  if os.getuid() == 0:
    return '/tmp/triage.db'
  return '/tmp/development.db'


class LogStore:
  """Owns one persistent writer connection (WAL mode) drained by a
  dedicated background thread, mirroring the writer-thread-+-queue pattern
  in bin/process_driver.py's DriverEmitter: log() never blocks the caller,
  writes are batched (one executemany + commit per drain cycle, not one
  commit per row), and callers should never touch the writer connection
  directly. Reads (query()) open their own short-lived connection per call -
  WAL mode's whole point is that readers don't block the writer and vice
  versa, so there's no need to share or lock the writer connection for reads.
  """

  def __init__(self, db_path: Optional[str] = None, max_bytes: int = DEFAULT_MAX_BYTES):
    self.db_path = db_path or _default_db_path()
    self.max_bytes = max_bytes
    self._queue: "queue.Queue[tuple]" = queue.Queue()
    self._wake = threading.Event()
    self._stop = threading.Event()
    self._ready = threading.Event()
    # Created inside _writer_loop(), not here - sqlite3 connections are
    # only usable from the thread that created them, and the writer thread
    # (not __init__'s caller) is the only thread ever allowed to touch it.
    self._conn: Optional[sqlite3.Connection] = None

    self._thread = threading.Thread(target=self._writer_loop, daemon=True, name="LogStore")
    self._thread.start()
    # Block until the writer thread has actually created the schema, so
    # query() (called from other threads) never races table creation - it
    # never needs to touch schema-modifying statements itself.
    self._ready.wait(timeout=10)
    atexit.register(self.close)
    pass

  @staticmethod
  def _configure_writer(conn: sqlite3.Connection) -> None:
    # journal_mode is persisted in the database file itself - setting it
    # here (once, on the writer's connection) is enough for every future
    # connection, including read connections, to use WAL automatically.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    pass

  @staticmethod
  def _configure_reader(conn: sqlite3.Connection) -> None:
    # Do NOT re-issue "PRAGMA journal_mode=WAL" here: it's a no-op once
    # already set, but re-asserting it while the writer thread is mid-
    # transaction can itself briefly need a lock and raise "database is
    # locked" - busy_timeout (not persisted, must be set per connection) is
    # all a short-lived reader connection actually needs.
    conn.execute("PRAGMA busy_timeout=5000")
    pass

  @staticmethod
  def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
      CREATE TABLE IF NOT EXISTS event_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        type TEXT NOT NULL,
        level TEXT,
        source TEXT,
        message TEXT,
        data TEXT
      )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(type)")
    conn.commit()
    pass

  def log(self, event_type: LogEventType, message: str, level: Optional[str] = None,
          source: Optional[str] = None, data: Optional[dict] = None) -> None:
    row = (
      datetime.now(timezone.utc).isoformat(),
      event_type.value if isinstance(event_type, LogEventType) else str(event_type),
      level,
      source,
      message,
      json.dumps(data) if data is not None else None,
    )
    self._queue.put(row)
    self._wake.set()
    pass

  def close(self) -> None:
    if self._stop.is_set():
      return
    self._stop.set()
    self._wake.set()
    self._thread.join()
    pass

  def _writer_loop(self) -> None:
    self._conn = sqlite3.connect(self.db_path)
    self._configure_writer(self._conn)
    self._create_schema(self._conn)
    self._ready.set()
    while True:
      self._wake.wait(timeout=WRITER_POLL_INTERVAL)
      self._wake.clear()
      self._drain()
      if self._stop.is_set() and self._queue.empty():
        break
      pass
    self._conn.close()
    pass

  def _drain(self) -> None:
    rows = []
    while True:
      try:
        rows.append(self._queue.get_nowait())
      except queue.Empty:
        break
      pass
    if not rows:
      return
    self._conn.executemany(
      "INSERT INTO event_log (timestamp, type, level, source, message, data) VALUES (?, ?, ?, ?, ?, ?)",
      rows)
    self._conn.commit()
    self._prune_if_needed()
    pass

  def _current_size_bytes(self) -> int:
    page_count = self._conn.execute("PRAGMA page_count").fetchone()[0]
    page_size = self._conn.execute("PRAGMA page_size").fetchone()[0]
    size = page_count * page_size
    wal_path = self.db_path + "-wal"
    if os.path.isfile(wal_path):
      size += os.path.getsize(wal_path)
      pass
    return size

  def _prune_if_needed(self) -> None:
    if self._current_size_bytes() < self.max_bytes * PRUNE_THRESHOLD:
      return
    total = self._conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    if total == 0:
      return
    to_delete = max(1, total // 5)
    # No VACUUM/wal_checkpoint(TRUNCATE) here - both need an exclusive lock
    # and would stall concurrent /logs reads and the writer itself. Deleted
    # pages go on sqlite's internal freelist and get reused by future
    # inserts, which is all the size cap actually needs.
    self._conn.execute(
      "DELETE FROM event_log WHERE id IN (SELECT id FROM event_log ORDER BY id ASC LIMIT ?)",
      (to_delete,))
    self._conn.commit()
    self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    pass

  @staticmethod
  def _in_clause(column: str, values: list) -> tuple[str, list]:
    placeholders = ", ".join(["?"] * len(values))
    return "%s IN (%s)" % (column, placeholders), list(values)

  def query(self, start: int = 0, count: int = 100,
            event_types: Optional[list] = None, levels: Optional[list] = None,
            sources: Optional[list] = None, q: Optional[str] = None,
            sort_desc: bool = True) -> tuple[list[dict[str, Any]], int]:
    conn = sqlite3.connect(self.db_path)
    try:
      self._configure_reader(conn)
      conn.row_factory = sqlite3.Row

      where = []
      params: list = []
      if event_types:
        clause, values = self._in_clause("type", [
          t.value if isinstance(t, LogEventType) else str(t) for t in event_types])
        where.append(clause)
        params.extend(values)
        pass
      if levels:
        clause, values = self._in_clause("level", list(levels))
        where.append(clause)
        params.extend(values)
        pass
      if sources:
        clause, values = self._in_clause("source", list(sources))
        where.append(clause)
        params.extend(values)
        pass
      if q:
        where.append("message LIKE ?")
        params.append("%" + q + "%")
        pass
      where_clause = ("WHERE " + " AND ".join(where)) if where else ""

      total = conn.execute("SELECT COUNT(*) FROM event_log " + where_clause, params).fetchone()[0]
      cursor = conn.execute(
        "SELECT id, timestamp, type, level, source, message, data FROM event_log "
        + where_clause + " ORDER BY id " + ("DESC" if sort_desc else "ASC") + " LIMIT ? OFFSET ?",
        params + [count, start])

      results = []
      for row in cursor.fetchall():
        entry = dict(row)
        if entry.get("data"):
          try:
            entry["data"] = json.loads(entry["data"])
          except (TypeError, ValueError):
            pass
          pass
        results.append(entry)
        pass
      return results, total
    finally:
      conn.close()
      pass
    pass

  def distinct_sources(self) -> list[str]:
    conn = sqlite3.connect(self.db_path)
    try:
      self._configure_reader(conn)
      rows = conn.execute(
        "SELECT DISTINCT source FROM event_log WHERE source IS NOT NULL ORDER BY source").fetchall()
      return [row[0] for row in rows]
    finally:
      conn.close()
      pass
    pass
  pass


_log_store_: Optional[LogStore] = None
_log_store_lock = threading.Lock()


def get_log_store() -> LogStore:
  global _log_store_
  if _log_store_ is None:
    with _log_store_lock:
      if _log_store_ is None:
        _log_store_ = LogStore()
        pass
      pass
    pass
  return _log_store_


class SQLiteLogHandler(logging.Handler):
  """logging.Handler that routes records into the LogStore as LogEventType.LOG
  rows instead of a text file."""

  def emit(self, record: logging.LogRecord) -> None:
    try:
      get_log_store().log(
        LogEventType.LOG,
        record.getMessage(),
        level=record.levelname,
        source=record.name,
        data={"processName": record.processName, "threadName": record.threadName})
    except Exception:
      self.handleError(record)
      pass
    pass
  pass


def install_sqlite_log_handler(logger: logging.Logger) -> None:
  """Adds a SQLiteLogHandler alongside logger's existing handlers - the
  RotatingFileHandler from setup_triage_logger() keeps writing the text log
  exactly as before, sqlite is an additional destination, not a replacement.
  Call this exactly once, only in the main server process (see module
  docstring) - every tlog.* call already routes through `logger`
  (get_triage_logger()'s process-wide singleton), so this alone captures
  them all without touching any of the ~166 existing call sites.

  Also sets logger.propagate = False: setup_triage_logger() attaches its
  RotatingFileHandler both directly (logger.addHandler) and via
  logging.basicConfig's root handlers, and with the default propagate=True
  every record was being emitted twice through that same file handler (once
  here, once via bubbling to root). Scoped to whichever logger this is
  called on, so it only changes behavior where this function is actually
  used, and doesn't affect the sqlite write (which comes from this logger's
  own handler list, not from propagation).
  """
  logger.propagate = False
  logger.addHandler(SQLiteLogHandler())
  pass
