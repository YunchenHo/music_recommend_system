"""讓 Django 使用 PyMySQL 作為 MySQLdb（免編譯 mysqlclient）。"""

import pymysql

pymysql.install_as_MySQLdb()

# Django 6 要求 mysqlclient>=2.2.1；PyMySQL 假冒的 version_info 較舊，僅用於通過版本檢查（行為仍以 PyMySQL 為準）。
import MySQLdb

if MySQLdb.version_info < (2, 2, 1):
    MySQLdb.version_info = (2, 2, 1, "final", 0)
