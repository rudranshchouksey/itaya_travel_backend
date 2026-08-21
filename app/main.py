from fastapi import FastAPI

app = FastAPI(title="Itvaya Travel Backend")

@app.get("/health")
def health_check():
    return {"status": "ok"}
