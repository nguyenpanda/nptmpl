from fastapi import APIRouter

from nptmpl.server.routes.public import router as public_router
from nptmpl.server.routes.admin import router as admin_router


router = APIRouter()

router.include_router(public_router)
router.include_router(admin_router)
