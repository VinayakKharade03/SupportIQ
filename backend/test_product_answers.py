import re
import time

from app.ml.model_loader import get_llm
from app.routers.support import MAX_DISTANCE, NO_ANSWER_REPLY, SYSTEM_PROMPT, build_prompt_with_context

QUESTIONS = [
    "how do I factory reset the Boot Airbuds 141 Gen 2",
    "does the Jibel Go 4 have an aux input",
    "how long does the Soney SH-C520 battery last",
    "is the Soney SH-C520 waterproof",
    "my earbuds wont connect to bluetooth",
    "what is the capital of france",
]

llm = get_llm()
for q in QUESTIONS:
    prompt, _, best = build_prompt_with_context(q)
    sources = re.findall(r"^\[(.+?)\]$", prompt, flags=re.M)
    if best > MAX_DISTANCE:
        reply = NO_ANSWER_REPLY
    else:
        t = time.time()
        out = llm.create_chat_completion(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            max_tokens=200,
        )
        reply = out["choices"][0]["message"]["content"]
        reply += f"  [{time.time() - t:.1f}s]"
    print("=" * 70)
    print("Q:", q)
    print("context:", sources)
    print("A:", reply)
