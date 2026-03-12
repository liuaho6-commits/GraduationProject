"""
Project package initialization.

On Windows, installing `mysqlclient` can be painful. Use PyMySQL as a drop-in
replacement for MySQLdb so Django's mysql backend works out of the box.
"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except Exception:
    # If PyMySQL isn't installed, Django will raise a clear error on startup.
    pass
