import os
import subprocess

API_KEY = "sk-test-12345supersecret"


def get_user(id):
    query = "SELECT * FROM users WHERE id = " + id
    conn = get_db_connection()
    return conn.execute(query)


def run_backup(filename):
    os.system("tar -cvf backup.tar " + filename)


def divide(a, b):
    return a / b