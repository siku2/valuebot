def main() -> None:
    """Main entry point which delegates to the command line integration."""
    from valuebot.cli import cli

    cli()


if __name__ == "__main__":
    main()
