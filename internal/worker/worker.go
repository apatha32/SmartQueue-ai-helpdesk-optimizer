package worker

import (
	"context"
	"fmt"
	"log"
	"time"

	"distributed-task-queue/internal/queue"
)

// HandlerFunc processes a single job. Return an error to trigger retry logic.
type HandlerFunc func(ctx context.Context, job *queue.Job) error

// Worker polls the queue and dispatches jobs to registered handlers.
type Worker struct {
	id         int
	queue      queue.Queue
	handlers   map[string]HandlerFunc
	jobTimeout time.Duration // maximum time a single handler may run; 0 = no limit
}

func New(id int, q queue.Queue, handlers map[string]HandlerFunc, jobTimeout time.Duration) *Worker {
	return &Worker{id: id, queue: q, handlers: handlers, jobTimeout: jobTimeout}
}

// Run blocks until ctx is cancelled, processing jobs in a tight loop.
func (w *Worker) Run(ctx context.Context) {
	log.Printf("[worker %d] started", w.id)
	for {
		select {
		case <-ctx.Done():
			log.Printf("[worker %d] shutting down", w.id)
			return
		default:
			if err := w.processNext(ctx); err != nil {
				log.Printf("[worker %d] error: %v", w.id, err)
				time.Sleep(time.Second)
			}
		}
	}
}

func (w *Worker) processNext(ctx context.Context) error {
	job, err := w.queue.Dequeue(ctx)
	if err != nil {
		return err
	}
	if job == nil {
		// Queue is empty — back off briefly to avoid spinning.
		time.Sleep(500 * time.Millisecond)
		return nil
	}

	log.Printf("[worker %d] processing job %s type=%s priority=%d", w.id, job.ID, job.Type, job.Priority)

	handler, ok := w.handlers[job.Type]
	if !ok {
		return w.queue.Fail(ctx, job.ID, fmt.Errorf("no handler registered for job type %q", job.Type))
	}

	jobCtx := ctx
	if w.jobTimeout > 0 {
		var cancel context.CancelFunc
		jobCtx, cancel = context.WithTimeout(ctx, w.jobTimeout)
		defer cancel()
	}

	if err := handler(jobCtx, job); err != nil {
		log.Printf("[worker %d] job %s failed (attempt %d/%d): %v", w.id, job.ID, job.Retries+1, job.MaxRetries, err)
		return w.queue.Fail(ctx, job.ID, err)
	}

	log.Printf("[worker %d] job %s completed", w.id, job.ID)
	return w.queue.Complete(ctx, job.ID)
}
