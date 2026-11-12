from fastapi import APIRouter

from .v1 import agents, analytics, auth, conversations, hr_agent, marketplace, organizations, rentals

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(hr_agent.router)
api_router.include_router(marketplace.router)
api_router.include_router(rentals.router)
api_router.include_router(conversations.router)
api_router.include_router(analytics.router)
api_router.include_router(agents.router)
