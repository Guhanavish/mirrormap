# Only parsed as an AST. This demo does not install or run FastAPI.
from fastapi import FastAPI
app = FastAPI()

@app.get('/status')
def status():
    return {'status': 'ok'}
