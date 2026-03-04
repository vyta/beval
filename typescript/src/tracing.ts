/**
 * OpenTelemetry tracing setup for the beval framework.
 *
 * Provides tracing configuration for process graders that inspect execution
 * traces. See SPEC.md §9 (Process Graders via Traces) and spec/otel-conventions.md.
 */

import { trace, type Tracer } from "@opentelemetry/api";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from "@opentelemetry/sdk-trace-node";

/**
 * Configure OpenTelemetry tracing with an in-memory exporter.
 *
 * Returns the exporter so process graders can inspect captured spans.
 */
export function setupTracing(serviceName = "beval"): InMemorySpanExporter {
  const exporter = new InMemorySpanExporter();
  const provider = new NodeTracerProvider();
  provider.addSpanProcessor(new SimpleSpanProcessor(exporter));
  provider.register();
  return exporter;
}

/** Get a tracer instance from the current provider. */
export function getTracer(name = "beval"): Tracer {
  return trace.getTracer(name);
}
