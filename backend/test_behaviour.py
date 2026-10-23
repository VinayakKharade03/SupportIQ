import re
import time

from app.ml.model_loader import get_llm
from app.routers.support import MAX_DISTANCE, NO_ANSWER_REPLY, SYSTEM_PROMPT, build_prompt_with_context

GROUPS = {
    "ENGLISH": [
        "how long does the Soney SH-C520 battery last",
        "does the Jibel Go 4 have an aux input",
        "my Jibel Go 4 is not charging",
        "what is the warranty period",
        "how do I factory reset the Boot Airbuds 141 Gen 2",
    ],
    "HINGLISH": [
        "Soney SH-C520 ki battery kitni der chalti hai",
        "Jibel Go 4 mein aux input hai kya",
        "mera Jibel Go 4 charge nahi ho raha hai",
        "warranty kitne saal ki hoti hai",
        "mere Boot Airbuds bluetooth se connect nahi ho rahe",
    ],
    "BEHAVIOUR TRAPS": [
        "does the Jibel Go 4 have NFC",
        "will the Soney SH-C520 definitely last 10 years",
        "compare the battery of Jibel Go 4 and Soney SH-C520",
        "is the Jibel Go 4 waterproof and is the Soney SH-C520 waterproof too",
        "can I use the Jibel Go 4 underwater for 3 hours",
    ],
    "ANGRY AND OUT OF SCOPE": [
        "yeh bakwaas hai, mera Jibel Go 4 kharab nikla, paisa wapas do",
        "this speaker is garbage, nothing works, I am very upset",
        "what is the capital of france",
        "france ki capital kya hai",
        "tum kaun ho aur kya kar sakte ho",
    ],
}

llm = get_llm()
for group, questions in GROUPS.items():
    print("\n" + "#" * 70)
    print("#", group)
    for q in questions:
        prompt, _, best = build_prompt_with_context(q)
        sources = re.findall(r"^\[(.+?)\]$", prompt, flags=re.M)
        print("=" * 70)
        print("Q:", q)
        print(f"best distance: {best:.2f} (cutoff {MAX_DISTANCE})")
        print("context:", sources)
        if best > MAX_DISTANCE:
            print("A: [CUTOFF, model not used]", NO_ANSWER_REPLY)
            continue
        t = time.time()
        out = llm.create_chat_completion(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            max_tokens=200,
        )
        reply = out["choices"][0]["message"]["content"]
        print(f"A: {reply}  [{time.time() - t:.1f}s]")
