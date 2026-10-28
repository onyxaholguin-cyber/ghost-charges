"""Ask a local open-weight model (any OpenAI-compatible server, e.g. llama.cpp's llama-server) to READ one bank descriptor.

The model only reads: who the merchant is and what kind of charge it looks like, with the exact words it used.
Grouping, cadence, totals and flags are plain code (find.py)."""
import json
import time
import urllib.request

KINDS = ["subscription_or_membership", "shopping_or_food", "transfer_or_payment_app", "income", "other"]

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["merchant", "quote", "kind"],
          "properties": {"merchant": {"type": "string"}, "quote": {"type": "string"},
                         "kind": {"type": "string", "enum": KINDS}}}

SYSTEM = (
    "You read one line from a bank or card statement. Bank descriptors are messy: they add payment processors "
    "(PAYPAL *, SQ *, TST*), phone numbers, store numbers, cities and reference codes. Return: merchant (the "
    "business's plain brand name in Title Case, e.g. 'Netflix', without the processor, numbers or city), quote "
    "(the exact characters from the line that name the merchant, copied character for character), and kind "
    "(subscription_or_membership for streaming, software, apps, gyms, news, memberships; shopping_or_food for "
    "stores, gas, restaurants, marketplaces; transfer_or_payment_app for Venmo/Zelle/transfers; income for payroll "
    "or deposits; other). Do not guess a brand that is not in the line."
)


def read_descriptor(text, base_url="http://127.0.0.1:8080", model="local", timeout=300):
    body = {"model": model, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": "Statement line:\n<<<" + text.strip() + ">>>"}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "descriptor", "schema": SCHEMA}}}
    req = urllib.request.Request(base_url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.load(r)
    return json.loads(resp["choices"][0]["message"]["content"]), round(time.time() - t0, 1)
