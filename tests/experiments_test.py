from fastapi import status
from data.database import get_db, Experiment, Variant
from sqlalchemy.orm import Session
# from tests.conftest import db_session

def test_create_experiment(client, db_session):
    payload = {
        "name": "Homepage Test",
        "description": "A/B test on homepage",
        "variants": [
            {"name": "Control", "allocation_percent": 0.5},
            {"name": "Treatment", "allocation_percent": 0.5}
        ]
    
    }
    headers = {"Authorization": "Bearer fake-client-token"}
    response = client.post("/experiments", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Homepage Test"
    assert data["is_active"] == True

    experiment_id = data["id"]
    
    variants = db_session.query(Variant).filter(Variant.experiment_id == experiment_id).all()
    assert variants is not None
    assert len(variants) == 2
    print(f"variants {variants}")
    # Compare names instead of raw objects vs dicts
    response_names = [v.name for v in variants]
    db_names = [v.name for v in variants]
    assert set(response_names) == set(db_names)



def test_get_assignment(client):
    # First create experiment
    exp_payload = {
        "name": "Homepage Test",
        "description": "A/B test",
        "variants": [
            {"name": "Control", "allocation_percent": 0.5},
            {"name": "Treatment", "allocation_percent": 0.5}
        ]
    }

    headers = {"Authorization": "Bearer fake-client-token"}
    exp_resp = client.post("/experiments", json=exp_payload, headers=headers)
    exp_id = exp_resp.json()["id"]

    # Request assignment
    response = client.get(f"/experiments/{exp_id}/assignment/user123", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["experiment_id"] == exp_id
    
    variants_name = [v["name"] for v in exp_payload["variants"]]
    assert "variant_name" in data
    assert data["variant_name"] in variants_name

def test_record_event(client):
    payload = {
        "user_id": "user123",
        "type": "purchase",
        "timestamp": "2025-12-08T21:00:00Z",
        "properties": {"amount": 100}
    }

    headers = {"Authorization": "Bearer fake-client-token"}
    response = client.post("/events", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["user_id"] == "user123"
    assert data["type"] == "purchase"

