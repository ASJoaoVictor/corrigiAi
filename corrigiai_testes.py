"""Separate Windows entrypoint: local SQLite only, no production configuration."""
if __name__ == '__main__':
    from desktop.launcher import main
    main(sqlite_test=True)
