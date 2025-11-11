from fastapi import APIRouter

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/ranking")
async def get_ranking():
    # Placeholder ranking; would call services.ranking_service in real app
    return {
        "ranking": [
            {"product_id": 2, "score": 91},
            {"product_id": 1, "score": 75},
        ]
    }
