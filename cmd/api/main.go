package main

import (
	"log"
	"os"

	"github.com/redis/go-redis/v9"

	"distributed-task-queue/internal/api"
	"distributed-task-queue/internal/queue"
)

func main() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	client := redis.NewClient(&redis.Options{Addr: redisAddr})
	q := queue.NewRedisQueue(client)

	handler := api.NewHandler(q)
	router := api.NewRouter(handler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("API server listening on :%s", port)
	if err := router.Run(":" + port); err != nil {
		log.Fatal(err)
	}
}
