# Architecture

The project is organized into three layers:

- src/shared: reusable modules such as auth, logging, price-book handling, and configuration.
- src/trackers: individual tracker entry points for futures and options.
- src/orchestration: a single launcher for running all trackers together.

Generated data is written under data/ so that runtime artifacts stay out of the source tree.
