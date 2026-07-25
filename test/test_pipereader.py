import os
import unittest

from wce_triage.lib.pipereader import PipeReader


class Test_pipereader(unittest.TestCase):

  def setUp(self):
    read_fd, write_fd = os.pipe()
    self.reader_file = os.fdopen(read_fd, 'rb')
    self.writer_fd = write_fd
    self.reader = PipeReader(self.reader_file)
    pass

  def tearDown(self):
    if self.writer_fd is not None:
      try:
        os.close(self.writer_fd)
      except OSError:
        pass
      pass
    self.reader_file.close()
    pass

  def write(self, data: bytes):
    os.write(self.writer_fd, data)
    pass

  def read_line(self):
    """Loop readline() until it returns an actual line, regardless of how
    many underlying reads that takes - readline() only reads 1 byte per
    call, so a multi-byte line legitimately needs several calls."""
    for _ in range(100000):
      result = self.reader.readline()
      if result is not None:
        return result
      pass
    self.fail("readline() never produced a result")
    pass

  def test_single_byte_trickle_newline(self):
    # Slow, one-byte-at-a-time producer (matches partclone/wget-style status
    # lines).
    for byte in b'hello\n':
      self.write(bytes([byte]))
      pass
    self.assertEqual(self.read_line(), "hello\n")
    pass

  def test_many_lines_in_one_write(self):
    payload = (b'line one\n' * 600) + b'line two\n'
    self.write(payload)

    lines = [self.read_line() for _ in range(601)]
    self.assertEqual(lines[:600], ["line one\n"] * 600)
    self.assertEqual(lines[600], "line two\n")
    pass

  def test_mixed_cr_and_lf_terminators(self):
    # rsync's --info=progress2 uses bare \r for in-place progress updates,
    # occasional \n for real newlines.
    self.write(b'progress 10%\rprogress 20%\rdone\n')
    self.assertEqual(self.read_line(), "progress 10%\n")
    self.assertEqual(self.read_line(), "progress 20%\n")
    self.assertEqual(self.read_line(), "done\n")
    pass

  def test_eof_flushes_trailing_fragment_then_signals_closed(self):
    self.write(b'no terminator here')
    os.close(self.writer_fd)
    self.writer_fd = None

    # Once the pipe is drained and the write end is closed, the next read
    # flushes whatever fragment was pending.
    self.assertEqual(self.read_line(), "no terminator here\n")
    # The following read signals true closure to the caller
    # (process_driver.py relies on this exact b'' sentinel to unregister
    # the fd).
    self.assertEqual(self.reader.readline(), b'')
    self.assertFalse(self.reader.alive)
    pass

  def test_eof_with_no_pending_fragment(self):
    self.write(b'complete line\n')
    self.assertEqual(self.read_line(), "complete line\n")

    os.close(self.writer_fd)
    self.writer_fd = None

    # Nothing was pending, so the EOF flush is just the terminator marker,
    # then closure.
    self.assertEqual(self.reader.readline(), "\n")
    self.assertEqual(self.reader.readline(), b'')
    pass


if __name__ == '__main__':
  unittest.main()