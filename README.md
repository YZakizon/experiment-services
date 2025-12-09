# A/B Testing Experiment

This code demonstrated the API to create A/B Testing Experiment

This demo uses sqlite, for production you may use Postgresql or hybrid Postgres and ClickHouse. 
ClickHouse may be use to store the events and use Postgres for everythin else.

# Running this demo in development

## Running with docker compose (recommened)
docker compose up -d

## Running API service
uv run uvicorn main:app --reload --port 9000

## Curl Example:

Set header
```
export AUTH_HEADER="Authorization: Bearer my_secret_api_key_123"
```

### Create a New Experiment:
```
curl -L -X POST 'http://localhost:9000/experiments' \
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
curl -L -X POST 'http://localhost:9000/events' \
-H 'Content-Type: application/json' \
-H "$AUTH_HEADER" \
-d '{
  "user_id": "user_A_123",
  "type": "purchase",
  "properties": {"order_value": 49.99}
}'
```

### Retrieve Experiment Results
```
# Retrieve results for Experiment ID 1, focusing on "purchase" events.

curl -L -X GET 'http://localhost:9000/experiments/1/results?event_type=purchase' \
-H "$AUTH_HEADER"
```

## Unit test

```
uv run pytest
```