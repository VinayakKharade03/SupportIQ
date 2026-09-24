import time
from llama_cpp import Llama

MODEL_PATH = "models/phi-3-mini-q4.gguf"

print("Loading model...")
start = time.time()

llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1,
    n_ctx=2048,
    verbose=True,
)

print(f"Model loaded in {time.time() - start:.2f}s")

prompt = "Customer says: My earbuds wont connect to Bluetooth. What should I ask them first?"

print("\nGenerating response...\n")
start = time.time()

output = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful customer support assistant for an audio electronics brand."},
        {"role": "user", "content": prompt},
    ],
    max_tokens=200,
)

elapsed = time.time() - start
response_text = output["choices"][0]["message"]["content"]

print("RESPONSE:")
print(response_text)
print(f"\nGenerated in {elapsed:.2f}s")
