from fastapi import FastAPI

app = FastAPI(title="Evidence Engine API")


@app.get("/health")
def health_check():
    return {"status": "Engine Running", "layer": "Evidence Engine"}
