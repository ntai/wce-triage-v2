import logging
import os
import tempfile
import threading
import time
import unittest

from wce_triage.lib.log_store import LogEventType, LogStore, install_sqlite_log_handler


def _cleanup_db_files(path):
  for ext in ("", "-wal", "-shm"):
    candidate = path + ext
    if os.path.exists(candidate):
      os.unlink(candidate)
      pass
    pass
  pass


class Test_log_store(unittest.TestCase):

  def setUp(self):
    self.db_path = tempfile.mktemp(suffix=".db")
    self.store = LogStore(db_path=self.db_path)
    pass

  def tearDown(self):
    self.store.close()
    _cleanup_db_files(self.db_path)
    pass

  def _wait_for(self, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
      if predicate():
        return True
      time.sleep(0.05)
      pass
    return False

  def test_log_and_query_round_trip(self):
    self.store.log(LogEventType.LOG, "hello world", level="INFO", source="test", data={"x": 1, "y": "z"})
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 1))

    rows, total = self.store.query()
    self.assertEqual(total, 1)
    self.assertEqual(len(rows), 1)
    row = rows[0]
    self.assertEqual(row["type"], "LOG")
    self.assertEqual(row["level"], "INFO")
    self.assertEqual(row["source"], "test")
    self.assertEqual(row["message"], "hello world")
    self.assertEqual(row["data"], {"x": 1, "y": "z"})
    self.assertIsInstance(row["id"], int)
    self.assertTrue(row["timestamp"])
    pass

  def test_data_is_none_when_not_provided(self):
    self.store.log(LogEventType.MESSAGE, "no data here")
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 1))
    rows, _ = self.store.query()
    self.assertIsNone(rows[0]["data"])
    pass

  def test_filter_by_type_and_level(self):
    self.store.log(LogEventType.LOG, "debug line", level="DEBUG")
    self.store.log(LogEventType.ERROR, "an error", level="ERROR")
    self.store.log(LogEventType.MESSAGE, "a note")
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 3))

    rows, total = self.store.query(event_types=[LogEventType.ERROR])
    self.assertEqual(total, 1)
    self.assertEqual(rows[0]["message"], "an error")

    rows, total = self.store.query(levels=["DEBUG"])
    self.assertEqual(total, 1)
    self.assertEqual(rows[0]["message"], "debug line")
    pass

  def test_filter_by_multiple_types_and_sources(self):
    self.store.log(LogEventType.LOG, "a log line", source="proc-a")
    self.store.log(LogEventType.ERROR, "an error", source="proc-b")
    self.store.log(LogEventType.MESSAGE, "a note", source="proc-c")
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 3))

    rows, total = self.store.query(event_types=[LogEventType.LOG, LogEventType.ERROR])
    self.assertEqual(total, 2)
    self.assertEqual({r["message"] for r in rows}, {"a log line", "an error"})

    rows, total = self.store.query(sources=["proc-a", "proc-c"])
    self.assertEqual(total, 2)
    self.assertEqual({r["message"] for r in rows}, {"a log line", "a note"})
    pass

  def test_distinct_sources(self):
    self.store.log(LogEventType.LOG, "one", source="proc-a")
    self.store.log(LogEventType.LOG, "two", source="proc-b")
    self.store.log(LogEventType.LOG, "three", source="proc-a")
    self.store.log(LogEventType.LOG, "no source")
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 4))

    self.assertEqual(self.store.distinct_sources(), ["proc-a", "proc-b"])
    pass

  def test_sort_direction(self):
    for i in range(5):
      self.store.log(LogEventType.LOG, "line %d" % i)
      pass
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 5))

    rows, _ = self.store.query(sort_desc=True)
    self.assertEqual([r["message"] for r in rows], ["line 4", "line 3", "line 2", "line 1", "line 0"])

    rows, _ = self.store.query(sort_desc=False)
    self.assertEqual([r["message"] for r in rows], ["line 0", "line 1", "line 2", "line 3", "line 4"])
    pass

  def test_filter_by_substring(self):
    self.store.log(LogEventType.LOG, "restore volume finished")
    self.store.log(LogEventType.LOG, "save volume finished")
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 2))

    rows, total = self.store.query(q="restore")
    self.assertEqual(total, 1)
    self.assertEqual(rows[0]["message"], "restore volume finished")
    pass

  def test_pagination_matches_insertion_order(self):
    for i in range(10):
      self.store.log(LogEventType.LOG, "line %d" % i)
      pass
    self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 10))

    rows, total = self.store.query(start=3, count=4, sort_desc=False)
    self.assertEqual(total, 10)
    self.assertEqual([r["message"] for r in rows], ["line 3", "line 4", "line 5", "line 6"])
    pass

  def test_concurrent_writes_and_reads_do_not_error(self):
    errors = []
    stop = threading.Event()

    def reader():
      while not stop.is_set():
        try:
          self.store.query(count=50)
        except Exception as exc:
          errors.append(exc)
          pass
        pass
      pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()
    try:
      for i in range(300):
        self.store.log(LogEventType.LOG, "concurrent %d" % i)
        pass
      self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 300))
    finally:
      stop.set()
      reader_thread.join(timeout=5)
      pass
    self.assertEqual(errors, [])
    pass

  def test_pruning_keeps_size_bounded_and_recent_rows(self):
    # Tiny cap forces pruning well before 500 rows accumulate.
    small_store = LogStore(db_path=tempfile.mktemp(suffix=".db"), max_bytes=20 * 1024)
    try:
      for i in range(500):
        small_store.log(LogEventType.LOG, "line %d" % i, source="pruning-test")
        pass
      def _settled():
        rows, total = small_store.query(count=1000, sort_desc=False)
        # Wait for all 500 writes to have landed (last row present) and for
        # that to have crossed the prune threshold (fewer than 500 survive).
        return 0 < total < 500 and rows and rows[-1]["message"] == "line 499"

      self.assertTrue(self._wait_for(_settled, timeout=10))

      rows, total = small_store.query(count=1000, sort_desc=False)
      self.assertLess(total, 500)
      # Oldest surviving row should be newer than "line 0" - confirms the
      # deletion targeted the oldest rows, not an arbitrary subset.
      self.assertNotEqual(rows[0]["message"], "line 0")
      self.assertEqual(rows[-1]["message"], "line 499")
      pass
    finally:
      db_path = small_store.db_path
      small_store.close()
      _cleanup_db_files(db_path)
      pass
    pass

  def test_install_sqlite_log_handler_emits_exactly_once(self):
    logger = logging.getLogger("test_log_store.no_double_emit")
    logger.setLevel(logging.DEBUG)
    install_sqlite_log_handler(logger)
    self.assertFalse(logger.propagate)
    self.assertEqual(len(logger.handlers), 1)

    # install_sqlite_log_handler routes into the process-wide get_log_store()
    # singleton, not self.store - point that singleton at this test's store
    # so we can assert against it directly.
    import wce_triage.lib.log_store as log_store_module
    original = log_store_module._log_store_
    log_store_module._log_store_ = self.store
    try:
      logger.info("single emit test")
      self.assertTrue(self._wait_for(lambda: self.store.query()[1] == 1))
      rows, total = self.store.query()
      self.assertEqual(total, 1)
      self.assertEqual(rows[0]["type"], "LOG")
      self.assertEqual(rows[0]["message"], "single emit test")
    finally:
      log_store_module._log_store_ = original
      pass
    pass


if __name__ == "__main__":
  unittest.main()
