# SupportIQ

AI-powered customer service agent — final year project.

## Setup

1. Create a venv and install dependencies: `pip install -r requirements.txt`
2. `llama-cpp-python` and `pywhispercpp` must be built with CUDA support for GPU inference.
3. Put the Phi-3-mini GGUF model at `backend/models/phi-3-mini-q4.gguf`.
4. Create `backend/.env` with `DATABASE_URL` and `JWT_SECRET_KEY`.
5. Create the tables: `alembic upgrade head`, then `python seed_products.py`.
6. Build the generated files (they are not committed):
   - `python create_training_data.py`
   - `python train_classifiers.py`
   - `python scripts_build_index.py`
7. Run the API: `uvicorn app.main:app`

## Voice replies

`POST /voice/reply` takes an audio file and streams back spoken answers (server-sent events: transcript, then one base64 WAV per sentence). Speech uses Kokoro (`af_heart`) on the CPU.

- The first run downloads about 330MB of Kokoro weights and a small spaCy model, so it needs internet once.
- On startup the server loads all models in the background. Wait for `[WARMUP] TTS cache ready` in the log (about 20 seconds) before sending requests.
- Try it with `python test_voice_reply_api.py "how long is the warranty"` while uvicorn is running.
