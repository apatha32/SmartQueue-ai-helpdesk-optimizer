package queue

import "time"

// Priority levels — lower number = higher priority
type Priority int

const (
	PriorityHigh   Priority = 1
	PriorityMedium Priority = 2
	PriorityLow    Priority = 3
)

type JobStatus string

const (
	StatusPending    JobStatus = "pending"
	StatusProcessing JobStatus = "processing"
	StatusCompleted  JobStatus = "completed"
	StatusFailed     JobStatus = "failed"
	StatusDead       JobStatus = "dead"
)

type Job struct {
	ID         string         `json:"id"`
	Type       string         `json:"type"`
	Payload    map[string]any `json:"payload"`
	Priority   Priority       `json:"priority"`
	Status     JobStatus      `json:"status"`
	Retries    int            `json:"retries"`
	MaxRetries int            `json:"max_retries"`
	CreatedAt  time.Time      `json:"created_at"`
	UpdatedAt  time.Time      `json:"updated_at"`
	Error      string         `json:"error,omitempty"`
}

type Stats struct {
	PendingCount    int64 `json:"pending_count"`
	ProcessingCount int64 `json:"processing_count"`
	CompletedCount  int64 `json:"completed_count"`
	FailedCount     int64 `json:"failed_count"`
	DeadCount       int64 `json:"dead_count"`
}
