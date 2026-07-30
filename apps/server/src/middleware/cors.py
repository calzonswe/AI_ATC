from fastapi.middleware.cors import CORSMiddleware

from ..settings import settings


def setup_cors(app):
    origins = [
        o.strip()
        for o in settings.cors_allow_origins.split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
