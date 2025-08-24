# app/main.py
from flask import Flask, jsonify, request
import time
import random
import logging
from prometheus_client import start_http_server, Counter, Histogram

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import os

app = Flask(__name__)

# Configure logging to output JSON for better parsing by Loki
logging.basicConfig(level=logging.INFO, format='{"time": "%(asctime)s.%(msecs)03dZ", "level": "%(levelname)s", "message": "%(message)s", "service": "atlan-api", "trace_id": "%(otelTraceID)s", "span_id": "%(otelSpanID)s"}', datefmt="%Y-%m-%dT%H:%M:%S")
logger = logging.getLogger(__name__)

# OpenTelemetry Configuration
# Set service name from environment variable
service_name = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "service.name=default-service").split("=")[1]
resource = Resource.create({"service.name": service_name})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# Export spans to OTLP collector
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True) # insecure for local testing
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrument Flask and requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument() # Instrument the requests library if used for outgoing calls

# Prometheus Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP Request Latency', ['method', 'endpoint'])

@app.route('/health')
def health_check():
    current_span = trace.get_current_span()
    trace_id = current_span.context.trace_id if current_span else "N/A"
    span_id = current_span.context.span_id if current_span else "N/A"
    logger.info("Health check endpoint accessed.", extra={'otelTraceID': f"{trace_id:x}", 'otelSpanID': f"{span_id:x}"})
    return jsonify({"status": "healthy"}), 200

@app.route('/api/data')
def get_data():
    start_time = time.time()
    method = 'GET'
    endpoint = '/api/data'
    status = 200

    current_span = trace.get_current_span()
    trace_id = current_span.context.trace_id if current_span else "N/A"
    span_id = current_span.context.span_id if current_span else "N/A"
    log_extra = {'otelTraceID': f"{trace_id:x}", 'otelSpanID': f"{span_id:x}"}

    try:
        with tracer.start_as_current_span("simulate_db_call"):
            logger.debug(f"[{endpoint}] Starting data retrieval process.", extra=log_extra)
            time.sleep(random.uniform(0.05, 0.5)) # Simulate DB query or external API call
        
        if random.random() < 0.1: # Simulate a 10% error rate
            current_span.set_attribute("error.type", "simulated_internal_error")
            current_span.record_exception(ValueError("Simulated internal service error"))
            current_span.set_status(trace.StatusCode.ERROR, "Simulated internal service error")
            raise ValueError("Simulated internal service error")

        data = {"message": "Data retrieved successfully!", "value": random.randint(1, 100)}
        logger.info(f"[{endpoint}] Data retrieval successful. Value: {data['value']}", extra=log_extra)
        return jsonify(data), status
    except ValueError as e:
        status = 500
        logger.error(f"[{endpoint}] Error during data retrieval: {e}", exc_info=True, extra=log_extra)
        return jsonify({"error": str(e)}), status
    except Exception as e:
        status = 500
        logger.critical(f"[{endpoint}] An unexpected error occurred: {e}", exc_info=True, extra=log_extra)
        return jsonify({"error": "An unexpected error occurred"}), status
    finally:
        latency = time.time() - start_time
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        logger.debug(f"[{endpoint}] Request completed in {latency:.4f} seconds with status {status}.", extra=log_extra)

if __name__ == '__main__':
    start_http_server(8000)
    logger.info("Prometheus metrics server started on port 8000.")
    app.run(host='0.0.0.0', port=5000)
