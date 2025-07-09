# Crypto Portfolio Analyzer

A sophisticated Python CLI tool for cryptocurrency portfolio management with real-time price fetching, analytics, and comprehensive reporting capabilities.

1. Code Execution

![code_execution1](https://github.com/user-attachments/assets/ddbfad00-ecb5-40a7-a405-743976bab7ee)

![code_execution2](https://github.com/user-attachments/assets/f0ebc0af-dbff-44fc-86ef-2bcbe185b51e)

![code_execution3](https://github.com/user-attachments/assets/8b05281a-8481-473f-9325-a567e0f7ce56)

![code_execution1](https://github.com/user-attachments/assets/b55f399b-f858-423e-a71a-0abc16a58933)

![code_execution2](https://github.com/user-attachments/assets/7e567ff0-5b1b-4c04-ad3b-71a6b5215c94)

![Code_execution1](https://github.com/user-attachments/assets/9578350d-3468-4646-99f5-05e5f9e13ede)

![code_execution2](https://github.com/user-attachments/assets/30e433df-6ac6-4c7a-9b9b-98e6a97c54eb)

![code_execution3](https://github.com/user-attachments/assets/7d9eeb8a-a129-4bcb-bd1d-ab747306da7c)

![code_execution1](https://github.com/user-attachments/assets/6e874082-8d2f-4471-9ccb-43faaa4e2fd5)

![code_execution2](https://github.com/user-attachments/assets/8a7a972c-4343-48d9-a7b2-66030d4f2cee)

![code_execution1](https://github.com/user-attachments/assets/4603ec40-a0bc-4fef-a169-7984b761d765)

![code_execution2](https://github.com/user-attachments/assets/7f1218bd-01ec-4697-9ab6-0ad7d4947771)

![code_execution1](https://github.com/user-attachments/assets/b3ee016b-0f8b-48d3-8e60-6757ad5e824d)

![code_execution2](https://github.com/user-attachments/assets/904a54d0-0328-4693-ae88-0b650e0a6db8)

![code_execution1](https://github.com/user-attachments/assets/5aa77be8-ef43-47ae-bd2e-5fb72dd898a4)

![code_execution2](https://github.com/user-attachments/assets/8fe0a55b-e384-427d-9ee0-ed4475cd5f06)


2. Test Execution

![test_execution](https://github.com/user-attachments/assets/0aa02ecb-8d79-4b83-bf40-b1b50db6d9ae)

![test_execution](https://github.com/user-attachments/assets/4c4f3571-1603-4d4b-82f7-91f58a347940)

![test_execution1](https://github.com/user-attachments/assets/a087015f-ae18-4b63-97bc-4a254733c169)

![Test_execution](https://github.com/user-attachments/assets/56ecd16a-981f-4385-9441-8fe895fe94fe)

![test_execution1](https://github.com/user-attachments/assets/2147e5fd-4f4f-480e-8dde-dfbc50ac95f0)

![test_execution2](https://github.com/user-attachments/assets/9fc638f4-31d2-489d-9701-b32aa941a40a)

![test_execution](https://github.com/user-attachments/assets/b0f6338a-2b4b-4f38-9d72-2afc011badb4)

![tes_execution1](https://github.com/user-attachments/assets/ff726e63-c3a1-475a-8c23-e82bbb45333d)

![test_execution2](https://github.com/user-attachments/assets/aa04bc03-5596-44cb-b6d5-d78df08c0b23)

![test_execution1](https://github.com/user-attachments/assets/357f8903-0c17-4a8f-b647-fb205dd78246)

![test_execution2](https://github.com/user-attachments/assets/a50eebd9-5305-4249-868b-ec240cbfca5c)

Project Features Mapped to Conversations

   Conversation 1: Feature 1 establishes a meta-driven, plugin-enabled CLI with dynamic command discovery from both pyproject.toml entry points and a local plugins/ directory, hot-reloading new commands on file changes. A hierarchical configuration system merges YAML defaults and dotenv overrides for flexible environment management. Structured JSON logging includes dynamic sampling and Sentry integration. Pre-commit hooks enforce mypy, flake8, and Bandit checks, while a custom Click parameter type validates values against remote schemas with shell autocompletion. A GitHub Actions CI pipeline automates linting, type-checking, testing, and Docker image builds.
   
   Conversation 2: Feature 2 delivers a high-throughput, resilient price-fetching engine built on asyncio and aiohttp, coordinating a token-bucket RateLimiter for API calls. It implements a custom exponential backoff with full jitter, differential retry logic for idempotent methods, and a two-level cache: in-memory LRU for hot symbols and persistent SQLite for cold data. Each API response is validated against a JSON Schema via Pydantic, and OpenTelemetry spans export traces to Jaeger. A Rich-powered TUI batch mode processes CSV-driven bulk imports with real-time progress feedback.
   
   Conversation 3: Feature 3 applies domain-driven design to portfolio management, defining an aggregate root and value objects (Coin, Amount, CostBasis) that enforce business invariants. A generic Repository[T] interface enables runtime swapping between in-memory and SQLAlchemy-backed stores, with thread safety via asyncio.Lock and threading.RLock. Pydantic models validate inputs and auto-generate OpenAPI schemas for future HTTP endpoints. A domain event bus streams CoinAdded and CoinRemoved events to Kafka for real-time dashboards. Chunked pandas CSV imports and CLI autocompletion complete a robust asset-management workflow.
   
   Conversation 4: Feature 4 introduces a plugin registry for performance metrics: implementations of BaseMetric (e.g., Sharpe, Sortino) are auto-discovered and computed in a streaming pipeline ingesting WebSocket price ticks. A CQRS pattern writes events to an append-only PostgreSQL event store, projecting read models for fast P/L and exposure queries. Async tasks update a Rich TUI dashboard with live spinners, while Prometheus metrics and bundled Grafana dashboards track operational health. Dask integration scales calculations across clusters, and Hypothesis-based fuzz testing ensures metric stability under randomized inputs.
   
   Conversation 5: Feature 5 establishes enterprise-grade persistence with SQLAlchemy Core and ORM hybrid models, custom indexes, and scoped sessions for concurrency safety. Alembic integration supports auto-generated migrations tested end-to-end in memory. On startup, schema drift is detected and either auto-patched or reported as a schema diff. Sensitive fields use encrypted SQLAlchemy TypeDecorators backed by AWS KMS. A backup/restore CLI streams compressed snapshots to S3 with checksum verification. Built-in health checks, connection pooling, and an optional “migrate-on-startup” flag ensure resilience and disaster recovery.

   Conversation 6: Feature 6 provides a modular plotting engine that loads visualizer plugins from visualizers/, each exposing a draw(ax, data) interface. A headless “report server” mode powered by FastAPI and Uvicorn serves cached SVG charts from Redis, while a JSON-driven layout system supports complex grid specs, dual axes, and annotated subplots. A real-time Bokeh dashboard polls Prometheus exporters for live updates. Pytest with the Agg backend validates figure structure automatically. CLI hot-reload, strict mypy enforcement, and rendering telemetry round out a fully observable visualization suite.

   Conversation 7: Feature 7 implements a Strategy pattern for report generation, dynamically loading CSVReporter, PDFReporter, and HTMLReporter classes via entry points. HTML reports leverage Jinja2 templates, bundled CSS/JS, and Chart.js for interactive data, while PDFs incorporate watermarks, encryption for per-user permissions, and embedded metadata. The send-report command integrates with SendGrid, managing TLS, retries, and local audit logging. Docker packaging spins up a secure HTTP server with Let’s Encrypt TLS. CI security scans, performance benchmarks, and optional cloud storage exports ensure compliant, scalable distribution pipelines.

   Conversation 8: Feature 8 completes the lifecycle with CI/CD, packaging, and observability. A tox.ini automates testing across Python 3.8–3.11 in parallel environments (async, db, report). A multi-stage Dockerfile separates lint, test, and runtime stages into minimal production images. GitHub Actions matrices run flake8, mypy, pytest with coverage gates, CodeQL scans, Docker builds, and PyPI deployments on tags. Sentry captures performance spans, while Prometheus exporters and Grafana dashboards monitor latency, error rates, and resource usage. End-to-end smoke tests validate nightly PyPI installs and core CLI commands.









