package worker

import (
	"context"
	"log"
	"sync"
	"time"

	"distributed-task-queue/internal/queue"
)

const (
	// defaultJobTimeout is the maximum time a single job handler may run.
	defaultJobTimeout = 30 * time.Second
	// staleSweepInterval controls how often the pool checks for stuck jobs.
	staleSweepInterval = 30 * time.Second
	// staleJobTimeout is how long a job can sit in "processing" before being
	// considered lost (worker crash) and re-enqueued.
	staleJobTimeout = 5 * time.Minute
)

// Pool runs N workers concurrently against the same queue.
type Pool struct {
	size       int
	queue      queue.Queue
	handlers   map[string]HandlerFunc
	jobTimeout time.Duration
}

func NewPool(size int, q queue.Queue, handlers map[string]HandlerFunc, jobTimeout time.Duration) *Pool {
	if jobTimeout == 0 {
		jobTimeout = defaultJobTimeout
	}
	return &Pool{size: size, queue: q, handlers: handlers, jobTimeout: jobTimeout}
}

// Run blocks until ctx is cancelled; all workers and the sweeper drain cleanly.
func (p *Pool) Run(ctx context.Context) {
	var wg sync.WaitGroup

	// Stale-job sweeper — recovers jobs orphaned by crashed workers.
	wg.Add(1)
	go func() {
		defer wg.Done()
		ticker := time.NewTicker(staleSweepInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				n, err := p.queue.RecoverStale(ctx, staleJobTimeout)
				if err != nil {
					log.Printf("[sweeper] error recovering stale jobs: %v", err)
				} else if n > 0 {
					log.Printf("[sweeper] recovered %d stale job(s)", n)
				}
			}
		}
	}()

	for i := 0; i < p.size; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			New(id, p.queue, p.handlers, p.jobTimeout).Run(ctx)
		}(i)
	}
	wg.Wait()
}
