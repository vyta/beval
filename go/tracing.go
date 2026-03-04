package beval

// Tracer holds tracing state for the beval framework.
//
// Will use: go.opentelemetry.io/otel and go.opentelemetry.io/otel/sdk
type Tracer struct {
	ServiceName string
}

// SetupTracing configures OpenTelemetry tracing with an in-memory exporter.
//
// Returns a Tracer that process graders can use to inspect captured spans.
// See SPEC §9 (Process Graders via Traces).
//
// Will use: go.opentelemetry.io/otel/sdk/trace with InMemoryExporter
func SetupTracing(serviceName string) *Tracer {
	// Stub: returns a Tracer with the service name.
	return &Tracer{ServiceName: serviceName}
}

// GetTracer returns a tracer instance for the given name.
//
// Will use: go.opentelemetry.io/otel.GetTracerProvider().Tracer(name)
func GetTracer(name string) *Tracer {
	// Stub: returns a new Tracer.
	return &Tracer{ServiceName: name}
}
