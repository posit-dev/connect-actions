from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root() -> dict:
    return {"message": "connect-actions e2e test app"}
