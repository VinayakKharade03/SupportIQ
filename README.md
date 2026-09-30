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
