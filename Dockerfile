FROM python:3.12-slim

WORKDIR /app
# Intentionally left minimal for the initial setup.
# In the future, install dependencies and run uvicorn.
