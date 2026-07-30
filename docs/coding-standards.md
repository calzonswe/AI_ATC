# Coding Standards

## Python / FastAPI (ATC Engine, Speech Pipeline, LLM Proxy)

### Style & Linting

- **Formatter**: `ruff format` with line length 100
- **Linter**: `ruff check` with recommended rules + `B`, `I`, `N`, `S`, `T20`
- **Type Checker**: `pyright` (strict mode)
- **Sort Imports**: `ruff check --select I --fix`

### Typing Rules

```python
# Always annotate function signatures
def process_radio_call(
    callsign: str,
    audio_pcm: npt.NDArray[np.float32],
    sample_rate: int,
) -> RadioCallResult: ...

# Use pydantic for all data structures
from pydantic import BaseModel, Field

class Position(BaseModel):
    lat: float = Field(ge=-90, le=90, description="Decimal degrees")
    lon: float = Field(ge=-180, le=180)
    alt_ft: float = Field(ge=-1000, le=100_000)

# Prefer Final, TypeAlias, and NewType for domain primitives
from typing import Final, TypeAlias
Callsign: TypeAlias = str
FrequencyHz: TypeAlias = float
```

### Conventions

- **No `__init__.py` code** — packages are implicit-namespace
- **Dependency injection** via FastAPI `Depends()` or explicit constructor injection
- **All services** use structured logging via `structlog`
- **Config** loaded from environment via `pydantic-settings` (single `Settings` class per service)
- **Async first** — use `async def` and `asyncio` for I/O; CPU-bound work (STT, TTS) offloaded to thread pool
- **Database** — use raw SQL with `asyncpg` (no ORM); migrations via Alembic
- **Tests** — `pytest` with `pytest-asyncio`, `pytest-cov` (target 90%+), factories via `factory_boy`

### Version

- Python 3.12 minimum
- Type hints from `__future__` annotations not required (3.12 has PEP 649 deferred eval natively)

## C# / .NET (SimConnect Client)

### Style & Linting

- **Formatting**: `dotnet format` with `.editorconfig` (indent 4 spaces, file-scoped namespaces)
- **Analyzers**: .NET SDK analyzers + Roslynator + SonarAnalyzer.CSharp
- **Treat warnings as errors** in CI

### Typing & Conventions

```csharp
// File-scoped namespaces
namespace OpenAtc.SimConnect;

// Primary constructors for simple types
public record TelemetryFrame(
    string Callsign,
    double Latitude,
    double Longitude,
    double AltitudeFeet,
    double HeadingDegrees,
    double SpeedKnots,
    long TimestampUnixMs
);

// Nullable reference types enabled
#nullable enable

// Use readonly structs for hot paths
public readonly struct SimConnectData { ... }
```

### Conventions

- **Async all the way** — `IAsyncEnumerable<T>` for telemetry streams
- **No `Task.Result` or `Task.Wait`** (except in `Main`)
- **Audio loopback** uses `NAudio` or `CSCore` for WASAPI capture/playback
- **SimConnect** calls run on a dedicated STA thread
- **Tests** — xUnit + FluentAssertions + NSubstitute

### Version

- .NET 8 SDK
- `Microsoft.FlightSimulator.SimConnect` SDK (shipped with MSFS)

## TypeScript / React (Web UI)

### Style & Linting

- **Formatter**: Prettier with `printWidth: 100`, `semi: true`, `singleQuote: true`
- **Linter**: ESLint flat config with `@typescript-eslint/strict-type-checked`
- **Type Checker**: `tsc --noEmit --strict`

### Typing

```typescript
// Prefer interface for public API shapes, type for unions/computed
interface TelemetryFrame {
  callsign: string;
  lat: number;
  lon: number;
  alt_ft: number;
  heading: number;
  speed_kn: number;
  ts: number;
}

// Branded types for domain primitives
type Callsign = string & { readonly __brand: 'Callsign' };
type Frequency = number & { readonly __brand: 'Frequency' };

// Use discriminated unions for state
type RadioState =
  | { status: 'idle' }
  | { status: 'transmitting'; since: number }
  | { status: 'receiving'; callsign: Callsign };
```

### Conventions

- **Functional components** with hooks (no classes)
- **State management** — React context + `useReducer` for global ATC state; Zustand optional for complex forms
- **WebSocket** — single shared connection with automatic reconnection (exponential backoff)
- **CSS** — Tailwind CSS utility classes; MUI components for complex widgets (strip board, radar)
- **Tests** — Vitest + React Testing Library + MSW (for WebSocket mocking)

### Version

- TypeScript 5.4+
- Node.js 20 LTS
- Vite 5+ for build
