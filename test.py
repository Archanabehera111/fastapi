import psycopg2
from psycopg2 import sql

# Define your PostgreSQL credentials
# hostname = 'localhost'  # Change to your host if different (e.g., Docker container IP)
hostname = 'postgres-container'  # Change to your host if different (e.g., Docker container IP)
port = '5432'           # Default PostgreSQL port
database = 'mydatabase' # Your database name
username = 'admin'      # Your PostgreSQL username
password = 'secret'     # Your PostgreSQL password

# Create a connection to the PostgreSQL database
try:
    connection = psycopg2.connect(
        host=hostname,
        port=port,
        database=database,
        user=username,
        password=password
    )
    print("Successfully connected to the database!")

    # Create a cursor to execute SQL commands
    cursor = connection.cursor()

    # Example query: Fetch all rows from a table
    cursor.execute("SELECT * FROM users;")
    
    # Fetch all results
    rows = cursor.fetchall()
    
    # Print results
    for row in rows:
        print(row)

    # Close the cursor
    cursor.close()

except Exception as error:
    print(f"Error while connecting to PostgreSQL: {error}")

finally:
    # Close the connection
    if connection:
        connection.close()
        print("Connection closed.")
