import json
import logging
from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="RSscraper")


@app.get("/")
def root():
    return {"Hello": "World"}
