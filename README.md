# coupon-code-workflow

A [Mistral Workflows](https://docs.mistral.ai/workflows/getting-started/introduction) project.

## Setup

```bash
uv sync
```

## Commands

### Register workflows in AI Studio

Auto-discovers all workflow classes in `src/workflows/`, registers them with AI Studio, and starts polling for executions. The [deployment name](https://docs.mistral.ai/workflows/managing-workflows-in-production/deployments) is set to `{hostname}-{project}-{adjective}-{noun}` so multiple projects on the same machine stay isolated:

```bash
make start-worker
```

### Execute a workflow

In a separate terminal, trigger a workflow execution by name:

```bash
make execute workflow=hello-world input='{"name": "World"}'
```

## Project layout

```
src/
├── entrypoints/ # Runnable modules, invoked via `python -m entrypoints.<module>`
│   ├── worker.py   # `python -m entrypoints.worker` — discover and run workflows
│   ├── start.py    # `python -m entrypoints.start`  — trigger a workflow execution
│   └── dev.py      # `python -m entrypoints.dev`    — worker with file-watch auto-reload
└── workflows/   # Your workflow classes (auto-discovered by `entrypoints.worker`)
```

## Development

```bash
# Format
uv run ruff format .

# Lint
uv run ruff check --fix .
```
