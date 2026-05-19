package main

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	"distributed-task-queue/internal/queue"
	"distributed-task-queue/internal/worker"
)

func main() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	poolSize, _ := strconv.Atoi(os.Getenv("WORKER_POOL_SIZE"))
	if poolSize == 0 {
		poolSize = 5
	}

	client := redis.NewClient(&redis.Options{Addr: redisAddr})
	q := queue.NewRedisQueue(client)

	// Register job type handlers — swap these out for real business logic.
	handlers := map[string]worker.HandlerFunc{
		"email": func(ctx context.Context, job *queue.Job) error {
			log.Printf("sending email payload=%v", job.Payload)
			time.Sleep(time.Duration(rand.Intn(400)+100) * time.Millisecond)
			return nil
		},
		"image_resize": func(ctx context.Context, job *queue.Job) error {
			log.Printf("resizing image payload=%v", job.Payload)
			time.Sleep(time.Duration(rand.Intn(900)+200) * time.Millisecond)
			// Simulate ~20% failure rate to exercise retry + dead-letter paths.
			if rand.Float32() < 0.2 {
				return fmt.Errorf("GPU unavailable")
			}
			return nil
		},
		"report": func(ctx context.Context, job *queue.Job) error {
			log.Printf("generating report payload=%v", job.Payload)
			time.Sleep(time.Duration(rand.Intn(1500)+500) * time.Millisecond)
			return nil
		},
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sig
		log.Println("received shutdown signal — draining workers")
		cancel()
	}()

	log.Printf("worker pool starting with %d workers", poolSize)
	worker.NewPool(poolSize, q, handlers, 0 /* use default 30s timeout */).Run(ctx)
}
