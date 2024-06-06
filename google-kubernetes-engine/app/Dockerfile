FROM golang:1.21-alpine

# Set working directory
WORKDIR /app

# Copy the application source code
COPY . ./

# Build the application binary
RUN go build -o /webserver

# Expose the port
EXPOSE 8080

# Set the command to run the application
CMD ["/webserver"]
