# Ensure PyMySQL can act as MySQLdb if mysqlclient is not installed
try:
    import MySQLdb  # type: ignore
except Exception:  # ModuleNotFoundError or similar
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except Exception:
        # If PyMySQL isn't available either, leave import errors to Django
        pass
