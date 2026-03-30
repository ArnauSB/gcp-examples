from fastapi import FastAPI
import os

app = FastAPI(
    title="GCP Bootcamp Masterclass API",
    description="A simple API to demonstrate Cloud Run Canary Deployments",
    version="1.0.0"
)

@app.get("/")
def read_root():
    """
    Root endpoint returning the current version of the application.
    """
    return {
        "api_version": "v1",
        "message": "Hello from Cloud Run! This is the stable Version 1.",
        "color": "blue"
    }

@app.get("/health")
def health_check():
    """
    Health check endpoint for GCP load balancers or uptime checks.
    """
    return {"status": "healthy"}
