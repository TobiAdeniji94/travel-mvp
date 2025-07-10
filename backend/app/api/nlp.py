from fastapi import APIRouter
from app.core.nlp.parser import parse_travel_request

router = APIRouter(tags=["nlp"])

@router.get("/parse-test")
def parse_test():
    sample = "Plan a trip to Paris next month with a budget of $2000. Include sightseeing and local cuisine."
    result = parse_travel_request(sample)
    return result