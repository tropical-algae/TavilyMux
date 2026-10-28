from tavily_mux.app import create_app
from tavily_mux.cli import run

app = create_app()


if __name__ == "__main__":
    run()
