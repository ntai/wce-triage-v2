#!/usr/bin/env python3
#

import sqlite3

class sqlite3_db:
  def __init__(self, db_file=None):
    self.db_file = db_file
    self._is_open = False
    pass

  def open(self):
    if not self._is_open:
      self.db = sqlite3.connect(self.db_file)
      self._is_open = True
      pass
    return self
  
  @property
  def is_open(self):
    return self._is_open

  pass


class sqlite3_table(object):

  def __init__(self, db, table_name):
    self.db = db # sqlite3_db
    self.table_name = table_name
    self._is_open = False
    self.tables = {}
    if db.is_open:
      self.open()
      pass
    pass

  def cursor(self):
    return self.db.db.cursor()

  def execute(self, statement):
    try:
      cursor = self.db.db.cursor()
      cursor.execute(statement)
    except sqlite3.OperationalError as exc:
      print(statement + "\n" + str(exc))
      pass

    return cursor

  def commit(self):
    self.db.db.commit()
    pass
  
  def open(self):
    raise Exception("So, this shouldn't be called.")

  def register_table(self, table):
    self.tables[table.table_name] = table
    pass

  @property
  def is_open(self):
    return self._is_open

  pass


class tag_value_table(sqlite3_table):
  def __init__(self, db, table_name, **kwargs):
    super().__init__(db, table_name, **kwargs)
    pass

  def open(self):
    if self.is_open:
      return
    try:
      self.execute("create table if not exists {} (tag varchar primary key, value varchar) ".format(self.table_name))
      self._is_open = True
      self.db.register_table(self)
    except:
      raise
    pass

  
  def get(self, tag, default_value=None):
    if not self.is_open:
      raise Exception("Table is not open.")
    cursor = self.execute("select value from {} where tag = '{}'".format(self.table_name, tag))
    for row in cursor.fetchall():
      return row[0]
    return default_value


  def set(self, tag, value):
    if not self.is_open:
      raise Exception("Table is not open.")
    cursor = self.execute("insert or replace into {table} (tag, value) values('{tag}', '{value}')".format(table=self.table_name, tag=tag, value=value))
    cursor.fetchall()
    self.commit()
    return
    
  pass
  

class config_base(tag_value_table):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    pass


  def provision(self):
    """To deploy the settings to host"""
    raise Exception("provisioning is not implemented")
    pass

  pass


class triage_config_db(sqlite3_db):
  def __init__(self):
    super().__init__("/var/lib/wce_triage/config.db")
    self.open()
    pass

  def provision(self):
    for config_name, config in self.tables:
      config.provision()
      pass
    pass
  pass
  



triage_config = triage_config_db()


if __name__ == "__main__":
  tiny = sqlite3_db(db_file = "/tmp/test.db")
  tiny.open()
  test_table = tag_value_table(tiny, "settings")
  
  test_table.set("foo", "bar")
  print(test_table.get("foo"))

  test_table.set("baz", "quux")
  print(test_table.get("baz"))
  
  test_table.set("foo", "foo")
  print(test_table.get("foo"))
  
  print(test_table.get("monkey", "banana"))
  
  print(test_table.get("fish"))

  pass
