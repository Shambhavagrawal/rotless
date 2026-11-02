import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--source", choices=["web", "code"], default="web")
ap.add_argument("query")
a = ap.parse_args()
print(f"[{a.source}] 3 hits for {a.query!r}: retry-policy.md, backoff.md, timeouts.md")
