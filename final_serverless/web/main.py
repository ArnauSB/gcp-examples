from flask import Flask, render_template
import os
import sqlalchemy
from sqlalchemy import text
import logging
from google.cloud import secretmanager

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable for the SQLAlchemy engine
db_engine = None

def get_secret(secret_name):
    """Retrieves a secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/<PROJECT-ID>/secrets/{secret_name}/versions/latest"  # Replace with your project ID
    try:
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logging.exception(f"Error accessing secret {secret_name}:")
        return None

def connect_to_db():
    global db_engine

    if db_engine is None:  # Only create the engine ONCE
        try:
            db_user = get_secret("DB-USER")
            db_password = get_secret("DB-PASSWORD")
            db_name = get_secret("DB-NAME")
            db_host = get_secret("DB-HOST")
            db_port = 5432

            if not all([db_host, db_user, db_password, db_name, db_port]):
                logging.error("Error: Missing database credentials from Secret Manager.")
                return False

            try:
                db_port = int(db_port) # Convert to int, handle potential errors
            except ValueError:
                logging.error("Error: DB_PORT must be an integer.")
                return False

            logging.info(f"Connecting to DB: Host={db_host}, User={db_user}, Database={db_name}, Port={db_port}")

            db_engine = sqlalchemy.create_engine(
                sqlalchemy.engine.url.URL.create(
                    drivername="postgresql+pg8000",
                    username=db_user,
                    password=db_password,
                    host=db_host, # Use connection name
                    database=db_name,
                ),
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )

            try:  # Test connection ONCE after engine creation
                with db_engine.connect() as connection:
                    result = connection.execute(text("SELECT 1::int"))
                    row = result.fetchone()
                    if row and row[0] == 1:
                        logging.info("Database connection test successful")
                    else:
                        logging.error("Database connection test failed")
                        raise Exception("Database connection test failed")
            except Exception as e:
                logging.exception("Database connection test failed:")
                return False

            logging.info("Database connection established")
            return True

        except Exception as e:
            logging.exception("Error connecting to database:")
            return False

    return True

@app.route('/')
def view_data():
    if not connect_to_db():
        return 'Error: Database connection failed', 500

    try:
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT temperature, humidity, timestamp FROM device_data ORDER BY timestamp DESC"))
            data = result.fetchall()

        return render_template('index.html', data=data)

    except Exception as e:
        logging.exception("Error fetching data:")
        return 'Error fetching data', 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
