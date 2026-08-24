import os

import uvicorn


def main() -> None:
    if not os.environ.get("INFRAI_API_KEY"):
        raise SystemExit("INFRAI_API_KEY is required")
    uvicorn.run("src.order_update_service:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
