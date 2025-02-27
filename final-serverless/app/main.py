from flask import Flask, request
import json
import os
import base64
import sqlalchemy
import logging
from decimal import Decimal
from google.cloud import pubsub_v1
from sqlalchemy import text

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable for the SQLAlchemy engine
db_engine = None

def connect_to_db():
    global db_engine

    if db_engine is None:  # Only create the engine ONCE
        try:
            db_host = os.environ.get("DB_HOST")
            db_user = os.environ.get("DB_USER")
            db_password = os.environ.get("DB_PASSWORD")
            db_name = os.environ.get("DB_NAME")
            db_port = os.environ.get("DB_PORT", 5432)

            logging.info(f"Connecting to DB: Host={db_host}, User={db_user}, Database={db_name}, Port={db_port}")

            if not all([db_host, db_user, db_password, db_name]):
                logging.error("Error: Missing database environment variables.")
                return False

            db_engine = sqlalchemy.create_engine(
                sqlalchemy.engine.url.URL.create(
                    drivername="postgresql+pg8000",
                    username=db_user,
                    password=db_password,
                    host=db_host,
                    port=db_port,
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
                        raise Exception("Database connection test failed") # Raise exception if test fails
            except Exception as e:
                logging.exception("Database connection test failed:")
                return False  # Return False only if the test or engine creation fails

            logging.info("Database connection established")
            return True

        except Exception as e:
            logging.exception("Error connecting to database:")
            return False

    return True  # Return True if engine exists

@app.route('/', methods=['POST'])
def process_message():
    if not connect_to_db():
        return 'Error: Database connection failed', 500

    pubsub_message = request.get_json()

    if pubsub_message and 'message' in pubsub_message and 'data' in pubsub_message['message']:
        data = pubsub_message['message']['data']
        message = base64.b64decode(data).decode('utf-8')

        try:
            device_data = json.loads(message)
            logging.info(f"Received data: {device_data}")

            temperature = Decimal(0)
            humidity = Decimal(0)

            temperature_str = device_data.get('temperature')
            humidity_str = device_data.get('humidity')

            if temperature_str is not None:
                try:
                    temperature = Decimal(temperature_str)
                except (TypeError, ValueError):
                    logging.error(f"Invalid temperature value: {temperature_str}")
                    temperature = None
            else:
                logging.error("Temperature missing in data.")

            if humidity_str is not None:
                try:
                    humidity = Decimal(humidity_str)
                except (TypeError, ValueError):
                    logging.error(f"Invalid humidity value: {humidity_str}")
                    humidity = None 
            else:
                logging.error("Humidity missing in data.")

            if temperature is None or humidity is None:
                return "Error: Invalid or missing temperature/humidity data", 400

            with db_engine.connect() as conn:
                with conn.begin():
                    try:
                        sql = text("INSERT INTO device_data (temperature, humidity) VALUES (:temperature, :humidity)")
                        conn.execute(sql, {"temperature": temperature, "humidity": humidity})
                        logging.info("Data inserted into the database")

                        if 'ackId' in pubsub_message['message']:
                            ack_id = pubsub_message['message']['ackId']
                            subscriber = pubsub_v1.SubscriberClient()
                            subscription_path = os.environ.get("PUBSUB_SUBSCRIPTION_PATH")
                            if not subscription_path:
                                logging.error("PUBSUB_SUBSCRIPTION_PATH env var is missing")
                                return "Error: Missing Pub/Sub subscription path", 500

                            subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": [ack_id]})
                            logging.info(f"Acknowledged message: {ack_id}")

                        return 'OK', 200

                    except sqlalchemy.exc.IntegrityError as e:
                        logging.error(f"Integrity Error inserting data: {e}")
                        return "Error inserting data", 500
                    except Exception as e:
                        logging.exception("Database error during insert:")
                        return "Error inserting data", 500

            return 'OK', 200

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON message: {message}")
            return 'Error', 500

    else:
        logging.info("No message to process")
        return 'OK', 200

@app.teardown_appcontext
def close_db_connection(exception):
    global db_engine
    if db_engine:
        db_engine.dispose()
        logging.info("Database connection closed")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
