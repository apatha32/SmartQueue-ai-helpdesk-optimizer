package queue

import (
	"context"
	"time"
)

// Queue defines the interface for a distributed job queue.
type Queue interface {
	Enqueue(ctx context.Context, job *Job) error
	Dequeue(ctx context.Context) (*Job, error)
	Complete(ctx context.Context, jobID string) error
	Fail(ctx context.Context, jobID string, err error) error
	Requeue(ctx context.Context, job *Job) error
	MoveToDeadLetter(ctx context.Context, job *Job) error
	Stats(ctx context.Context) (*Stats, error)

	// GetJob fetches a single job by ID. Returns nil, nil when not found.
	GetJob(ctx context.Context, jobID string) (*Job, error)

	// RecoverStale re-enqueues jobs that have been in the processing set for
	// longer than timeout (handles crashed workers). Returns the number recovered.
	RecoverStale(ctx context.Context, timeout time.Duration) (int, error)

	// RetryDead removes a job from the dead-letter list, resets its retry
	// counter, and re-enqueues it.
	RetryDead(ctx context.Context, jobID string) (*Job, error)

	// ListDeadJobs returns up to limit dead-letter jobs, newest first.
	ListDeadJobs(ctx context.Context, limit int64) ([]*Job, error)
}
