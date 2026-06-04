import sys
from nptmpl.cli.app import CLIApp

def main():
    """Main entry point for the nptmpl CLI."""
    app = CLIApp(sys.argv[1:])
    app.run()

if __name__ == "__main__":
    main()
