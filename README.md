Install app:
  poetry install
Run main app:
  poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Run docker:
```bash
docker-compose -f deployments/docker-compose.yaml up -d
```