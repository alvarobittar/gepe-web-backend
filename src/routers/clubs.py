from fastapi import APIRouter

router = APIRouter(prefix="/clubs", tags=["clubs"])

@router.get("/")
async def list_clubs():
    return [
        {"id": 1, "name": "Club Central"},
        {"id": 2, "name": "Club Norte"},
    ]
