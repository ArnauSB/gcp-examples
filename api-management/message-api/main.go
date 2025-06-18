package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"strconv"
	"sync"
)

type Message struct {
	ID      int    `json:"id"`
	Content string `json:"content"`
}

var (
	messages = make(map[int]Message)
	counter  = 1
	mu       sync.Mutex
)

func main() {
	http.HandleFunc("/", serveIndex)
	http.HandleFunc("/messages", messagesHandler)
	http.HandleFunc("/messages/", messageHandler)

	fs := http.FileServer(http.Dir("./static"))
	http.Handle("/static/", http.StripPrefix("/static/", fs))

	port := "8080"
	fmt.Println("Escuchando en http://localhost:" + port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func serveIndex(w http.ResponseWriter, r *http.Request) {
	tmpl := template.Must(template.ParseFiles("static/index.html"))
	tmpl.Execute(w, nil)
}

// /messages (GET, POST)
func messagesHandler(w http.ResponseWriter, r *http.Request) {
	mu.Lock()
	defer mu.Unlock()

	switch r.Method {
	case http.MethodGet:
		var list []Message
		for _, msg := range messages {
			list = append(list, msg)
		}
		json.NewEncoder(w).Encode(list)

	case http.MethodPost:
		var msg Message
		if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		msg.ID = counter
		counter++
		messages[msg.ID] = msg
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(msg)

	default:
		http.Error(w, "Método no permitido", http.StatusMethodNotAllowed)
	}
}

// /messages/{id} (GET, PUT, DELETE)
func messageHandler(w http.ResponseWriter, r *http.Request) {
	mu.Lock()
	defer mu.Unlock()

	idStr := r.URL.Path[len("/messages/"):]
	id, err := strconv.Atoi(idStr)
	if err != nil {
		http.Error(w, "ID inválido", http.StatusBadRequest)
		return
	}

	msg, exists := messages[id]

	switch r.Method {
	case http.MethodGet:
		if !exists {
			http.Error(w, "No encontrado", http.StatusNotFound)
			return
		}
		json.NewEncoder(w).Encode(msg)

	case http.MethodPut:
		if !exists {
			http.Error(w, "No encontrado", http.StatusNotFound)
			return
		}
		var updated Message
		if err := json.NewDecoder(r.Body).Decode(&updated); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		updated.ID = id
		messages[id] = updated
		json.NewEncoder(w).Encode(updated)

	case http.MethodDelete:
		if !exists {
			http.Error(w, "No encontrado", http.StatusNotFound)
			return
		}
		delete(messages, id)
		w.WriteHeader(http.StatusNoContent)

	default:
		http.Error(w, "Método no permitido", http.StatusMethodNotAllowed)
	}
}
