# python-backend-patterns

Dependency-free building blocks for Python backends: retries, circuit breakers,
rate limits, idempotency, transactional outbox, structured logging and friends.

Every pattern is a single module under `patterns/` with a focused `unittest`
suite. No framework, no third-party packages, no ceremony — copy the module you
need, or read it as a reference implementation.

## Design rules

- **Standard library only.** Nothing to install, nothing to pin.
- **Time is injectable.** Every time-based module takes a `clock` callable so
  tests are deterministic instead of `sleep`-based.
- **Thread-safe by default.** Anything with mutable state guards it with a lock.
- **Small surface.** One class or one function per module, documented in the
  docstring, with the trade-off spelled out.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

Python 3.10+.

## Patterns

| Pattern | Module | What it solves |
| ------- | ------ | -------------- |
| Retry with backoff | [`patterns/retry.py`](patterns/retry.py) | Flaky upstream calls without retry storms |
| Circuit breaker | [`patterns/circuit_breaker.py`](patterns/circuit_breaker.py) | Stop hammering a dependency that is already down |
| Token bucket rate limiter | [`patterns/rate_limit.py`](patterns/rate_limit.py) | Bursts allowed, sustained rate capped |
| Idempotency keys | [`patterns/idempotency.py`](patterns/idempotency.py) | Duplicate webhook and payment deliveries cause one side effect |
| Transactional outbox | [`patterns/outbox.py`](patterns/outbox.py) | A database commit and a broker publish cannot both be atomic |
| Structured JSON logging | [`patterns/json_logging.py`](patterns/json_logging.py) | Find every line of one request at 3am |
| Cursor pagination | [`patterns/pagination.py`](patterns/pagination.py) | OFFSET gets slow and skips rows under concurrent inserts |
