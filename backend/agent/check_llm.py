from .agent import get_client, MODEL

if __name__ == "__main__":
    r = get_client().chat.completions.create(model=MODEL, messages=[{"role":"user","content":"Dis bonjour en une phrase."}], max_tokens=500)
    print(r.choices[0].message.content)
