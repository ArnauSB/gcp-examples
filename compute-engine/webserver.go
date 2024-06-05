package main

import (
	"fmt"
	"net/http"
	"os"
)

const port = 8080

func indexHandler(w http.ResponseWriter, r *http.Request) {
	// Get the hostname
	hostname, err := os.Hostname()
	if err != nil {
		http.Error(w, "Error getting hostname", http.StatusInternalServerError)
		return
	}

	// Get request headers
	userAgent := r.Header.Get("User-Agent")

	// Formulate the response
	response := fmt.Sprintf("Hostname: %s\nUser-Agent: %s", hostname, userAgent)

	// Write the response
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(response))
}

func healthzHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func main() {
	// Print a startup message
	fmt.Println("Server starting...")

	// Set up the handler
	http.HandleFunc("/", indexHandler)
	http.HandleFunc("/healthz", healthzHandler)

	// Start the server
	fmt.Printf("Starting HTTP server at port %d\n", port)
	if err := http.ListenAndServe(fmt.Sprintf(":%d", port), nil); err != nil {
		fmt.Fprintf(os.Stderr, "Error starting server: %v\n", err)
		os.Exit(1)
	}
}
