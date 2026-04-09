package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math/rand"
	"net/http"
	"os"
	"strings"
	"time"
)

// responseWriter wraps http.ResponseWriter to capture the status code.
type responseWriter struct {
	http.ResponseWriter
	status int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.status = code
	rw.ResponseWriter.WriteHeader(code)
}

// loggingMiddleware logs each request as a structured JSON log line.
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		requestID := fmt.Sprintf("%016x", rand.Uint64())

		w.Header().Set("X-Request-ID", requestID)
		rw := &responseWriter{ResponseWriter: w, status: http.StatusOK}

		next.ServeHTTP(rw, r)

		slog.Info("request",
			"method", r.Method,
			"path", r.URL.Path,
			"status", rw.status,
			"latency_ms", time.Since(start).Milliseconds(),
			"remote_addr", r.RemoteAddr,
			"user_agent", r.Header.Get("User-Agent"),
			"request_id", requestID,
		)
	})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func indexHandler(w http.ResponseWriter, r *http.Request) {
	hostname, err := os.Hostname()
	if err != nil {
		slog.Error("failed to get hostname", "error", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to get hostname"})
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"hostname":    hostname,
		"remote_addr": r.RemoteAddr,
		"user_agent":  r.Header.Get("User-Agent"),
		"project_id":  os.Getenv("PROJECT_ID"),
		"zone":        os.Getenv("ZONE"),
		"instance_id": os.Getenv("INSTANCE_ID"),
	})
}

func headersHandler(w http.ResponseWriter, r *http.Request) {
	headers := make(map[string]string, len(r.Header))
	for k, v := range r.Header {
		headers[k] = strings.Join(v, ", ")
	}
	writeJSON(w, http.StatusOK, headers)
}

func envHandler(w http.ResponseWriter, r *http.Request) {
	envVars := make(map[string]string)
	for _, e := range os.Environ() {
		k, v, _ := strings.Cut(e, "=")
		envVars[k] = v
	}
	writeJSON(w, http.StatusOK, envVars)
}

// infoHandler fetches live GCP instance metadata from the metadata server.
// Returns a timeout error when not running on GCP.
func infoHandler(w http.ResponseWriter, r *http.Request) {
	client := &http.Client{Timeout: 2 * time.Second}

	fields := []string{"hostname", "zone", "machine-type", "id"}
	info := make(map[string]string, len(fields))

	for _, field := range fields {
		url := "http://metadata.google.internal/computeMetadata/v1/instance/" + field
		req, err := http.NewRequest(http.MethodGet, url, nil)
		if err != nil {
			slog.Error("metadata request build failed", "field", field, "error", err)
			continue
		}
		req.Header.Set("Metadata-Flavor", "Google")

		resp, err := client.Do(req)
		if err != nil {
			slog.Warn("metadata fetch failed", "field", field, "error", err)
			info[field] = "unavailable"
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		info[field] = string(body)
	}

	writeJSON(w, http.StatusOK, info)
}

func healthzHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", indexHandler)
	mux.HandleFunc("/headers", headersHandler)
	mux.HandleFunc("/env", envHandler)
	mux.HandleFunc("/info", infoHandler)
	mux.HandleFunc("/healthz", healthzHandler)

	slog.Info("server starting", "port", port)
	if err := http.ListenAndServe(":"+port, loggingMiddleware(mux)); err != nil {
		slog.Error("server failed", "error", err)
		os.Exit(1)
	}
}
