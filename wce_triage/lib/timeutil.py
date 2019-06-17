import datetime

def in_seconds(seconds):
  if isinstance(seconds, datetime.timedelta):
    return seconds.total_seconds()
  return seconds
