# A/B Testing Experiment

Simple API to create A/B Testing Experiment

This project uses Postgres, for production you may use ClickHouse 
to store the events and use Postgres for everything else.

Features:
- Use Postgres database
- Use celery for high performance events collector

# Running this demo in non production

## Running with docker compose (recommened)
Copy .env.example to .env-docker and modify the hostname if necessary
```
cp .env.example .env-docker
docker compose up -d
```

## Running API service
if you only need to run the api server during development, run:
Copy .env.example to .env and modify the hostname if necessary.
By default .env will be called if you run this not from docker-compose

```
uv run uvicorn main:app --reload --port 9000
```

## Curl Example:

Set AUTH_HEADER with your api key
```
export AUTH_HEADER="Authorization: Bearer my_secret_api_key_123"
```

### Create a New Experiment:
```
curl -X POST 'http://localhost:9000/experiments' \
-H 'Content-Type: application/json' \
-H "$AUTH_HEADER" \
-d '{
  "name": "Button Color Test",
  "description": "Testing red vs blue for purchase button clicks.",
  "variants": [
    {"name": "red_button", "allocation_percent": 50.0},
    {"name": "blue_button", "allocation_percent": 50.0}
  ]
}'
```

### Get User's Variant Assignment
```
# Assigns 'user_A_123' to a variant (e.g., 'red_button')

curl -L -X GET 'http://localhost:9000/experiments/1/assignment/user_A_123' \
-H "$AUTH_HEADER"

```

### Record an Event (Conversion)
```
# Post event for user A_123 on "purchase" event.
curl -L -X POST 'http://localhost:9000/events' \
-H 'Content-Type: application/json' \
-H "$AUTH_HEADER" \
-d '{
  "user_id": "user_A_123",
  "type": "purchase",
  "properties": {"order_value": 49.99}
}'

# Post event for user A_123 on "click" event.
curl -L -X POST 'http://localhost:9000/events' \
-H 'Content-Type: application/json' \
-H "$AUTH_HEADER" \
-d '{
  "user_id": "user_A_123",
  "type": "click",
  "properties": {"button": "buy"}
}'

```

### Retrieve Experiment Results
```
# Retrieve results for Experiment ID 1, focusing on "purchase" events.

curl -L -X GET 'http://localhost:9000/experiments/1/results?event_type=purchase' \
-H "$AUTH_HEADER"

# Retrieve results for last 1 day
curl -L -X GET 'http://localhost:9000/experiments/1/results?event_type=purchase&last_day=1' \
-H "$AUTH_HEADER"

# Retrieve results for Experiment ID 1, focusing on "click" events.
curl -L -X GET 'http://localhost:9000/experiments/1/results?event_type=click' \
-H "$AUTH_HEADER"
```

## Unit test

```
uv run pytest
```