"""CLI entry: python -m ea_knowledge_agent [--host ...] [--port ...]
[--db ...] [--web ...]"""

import argparse

from .api import create_server
from .config import load_settings


def main():
    s = load_settings()
    ap = argparse.ArgumentParser(prog="ea_knowledge_agent")
    ap.add_argument("--host", default=s.host)
    ap.add_argument("--port", type=int, default=s.port)
    ap.add_argument("--db", default=s.db_path)
    ap.add_argument("--web", default=s.web_dir)
    args = ap.parse_args()
    server = create_server(args.host, args.port, args.db, args.web)
    print(f"EA Knowledge Agent POC listening on "
          f"http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
