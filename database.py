import psycopg2
from dotenv import dotenv_values



env_config = dotenv_values(".env")


def connect_db():
    # Create and return connection object to postgres data
    try:
        conn = psycopg2.connect(
            database=env_config['DB_NAME'],
            user=env_config['DB_USERNAME'],
            password=env_config['DB_PASSWORD'],
            host=env_config['DB_HOST'],
            port=env_config['DB_PORT'],
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        print("error:", e)
        return None
    
