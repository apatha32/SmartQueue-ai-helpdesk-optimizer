package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	pendingKey   = "queue:pending"    // Sorted Set — score encodes priority + timestamp
	processingKey = "queue:processing" // Hash — jobID -> enqueue timestamp (ms)
	deadKey      = "queue:dead"       // List — dead job IDs
	jobKeyPrefix = "job:"
	statsPrefix  = "stats:"
)

// RedisQueue is a priority-aware, reliable Redis-backed job queue.
type RedisQueue struct {
	client *redis.Client
}

func NewRedisQueue(client *redis.Client) *RedisQueue {
	return &RedisQueue{client: client}
}

func jobKey(id string) string {
	return jobKeyPrefix + id
}

// Enqueue adds a job to the pending sorted set.
// Score = priority * 1e10 + unix_ms so jobs are sorted by priority first, then FIFO.
func (q *RedisQueue) Enqueue(ctx context.Context, job *Job) error {
	data, err := json.Marshal(job)
	if err != nil {
		return fmt.Errorf("marshal job: %w", err)
	}

	score := float64(int(job.Priority)*1e10) + float64(time.Now().UnixMilli())

	pipe := q.client.Pipeline()
	pipe.Set(ctx, jobKey(job.ID), data, 0)
	pipe.ZAdd(ctx, pendingKey, redis.Z{Score: score, Member: job.ID})
	_, err = pipe.Exec(ctx)
	return err
}

// Dequeue atomically pops the highest-priority job and moves it to the processing set.
func (q *RedisQueue) Dequeue(ctx context.Context) (*Job, error) {
	results, err := q.client.ZPopMin(ctx, pendingKey, 1).Result()
	if err != nil {
		return nil, err
	}
	if len(results) == 0 {
		return nil, nil
	}

	jobID, ok := results[0].Member.(string)
	if !ok {
		return nil, fmt.Errorf("unexpected member type in sorted set")
	}

	pipe := q.client.Pipeline()
	pipe.HSet(ctx, processingKey, jobID, time.Now().UnixMilli())
	if _, err = pipe.Exec(ctx); err != nil {
		return nil, err
	}

	data, err := q.client.Get(ctx, jobKey(jobID)).Bytes()
	if err != nil {
		return nil, fmt.Errorf("get job data: %w", err)
	}

	var job Job
	if err := json.Unmarshal(data, &job); err != nil {
		return nil, fmt.Errorf("unmarshal job: %w", err)
	}

	job.Status = StatusProcessing
	job.UpdatedAt = time.Now()

	updated, _ := json.Marshal(job)
	q.client.Set(ctx, jobKey(job.ID), updated, 0)

	return &job, nil
}

// Complete marks a job as successfully done and removes it from the processing set.
func (q *RedisQueue) Complete(ctx context.Context, jobID string) error {
	data, err := q.client.Get(ctx, jobKey(jobID)).Bytes()
	if err != nil {
		return err
	}

	var job Job
	if err := json.Unmarshal(data, &job); err != nil {
		return err
	}

	job.Status = StatusCompleted
	job.UpdatedAt = time.Now()
	updated, _ := json.Marshal(job)

	pipe := q.client.Pipeline()
	pipe.Set(ctx, jobKey(jobID), updated, 24*time.Hour)
	pipe.HDel(ctx, processingKey, jobID)
	pipe.Incr(ctx, statsPrefix+"completed")
	_, err = pipe.Exec(ctx)
	return err
}

// Fail increments retry count and either requeues or dead-letters the job.
func (q *RedisQueue) Fail(ctx context.Context, jobID string, jobErr error) error {
	data, err := q.client.Get(ctx, jobKey(jobID)).Bytes()
	if err != nil {
		return err
	}

	var job Job
	if err := json.Unmarshal(data, &job); err != nil {
		return err
	}

	job.Retries++
	job.Error = jobErr.Error()
	job.UpdatedAt = time.Now()

	if job.Retries >= job.MaxRetries {
		return q.MoveToDeadLetter(ctx, &job)
	}

	job.Status = StatusFailed
	updated, _ := json.Marshal(job)

	pipe := q.client.Pipeline()
	pipe.Set(ctx, jobKey(jobID), updated, 0)
	pipe.HDel(ctx, processingKey, jobID)
	pipe.Incr(ctx, statsPrefix+"failed")
	if _, err = pipe.Exec(ctx); err != nil {
		return err
	}

	return q.Requeue(ctx, &job)
}

// Requeue re-adds a failed job with a back-off penalty to its score.
func (q *RedisQueue) Requeue(ctx context.Context, job *Job) error {
	job.Status = StatusPending
	job.UpdatedAt = time.Now()

	data, _ := json.Marshal(job)

	// Penalty pushes retried jobs slightly behind fresh jobs of the same priority.
	penalty := float64(job.Retries * 5000)
	score := float64(int(job.Priority)*1e10) + float64(time.Now().UnixMilli()) + penalty

	pipe := q.client.Pipeline()
	pipe.Set(ctx, jobKey(job.ID), data, 0)
	pipe.ZAdd(ctx, pendingKey, redis.Z{Score: score, Member: job.ID})
	_, err := pipe.Exec(ctx)
	return err
}

// MoveToDeadLetter permanently parks a job that exhausted all retries.
func (q *RedisQueue) MoveToDeadLetter(ctx context.Context, job *Job) error {
	job.Status = StatusDead
	job.UpdatedAt = time.Now()
	data, _ := json.Marshal(job)

	pipe := q.client.Pipeline()
	pipe.Set(ctx, jobKey(job.ID), data, 7*24*time.Hour)
	pipe.HDel(ctx, processingKey, job.ID)
	pipe.LPush(ctx, deadKey, job.ID)
	pipe.Incr(ctx, statsPrefix+"dead")
	_, err := pipe.Exec(ctx)
	return err
}

// Stats returns current queue counters.
func (q *RedisQueue) Stats(ctx context.Context) (*Stats, error) {
	pipe := q.client.Pipeline()
	pendingCmd := pipe.ZCard(ctx, pendingKey)
	processingCmd := pipe.HLen(ctx, processingKey)
	completedCmd := pipe.Get(ctx, statsPrefix+"completed")
	failedCmd := pipe.Get(ctx, statsPrefix+"failed")
	deadCmd := pipe.LLen(ctx, deadKey)
	pipe.Exec(ctx)

	completed, _ := completedCmd.Int64()
	failed, _ := failedCmd.Int64()

	return &Stats{
		PendingCount:    pendingCmd.Val(),
		ProcessingCount: processingCmd.Val(),
		CompletedCount:  completed,
		FailedCount:     failed,
		DeadCount:       deadCmd.Val(),
	}, nil
}

// GetJob fetches a single job by ID. Returns nil, nil when the job does not exist.
func (q *RedisQueue) GetJob(ctx context.Context, jobID string) (*Job, error) {
	data, err := q.client.Get(ctx, jobKey(jobID)).Bytes()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("get job: %w", err)
	}
	var job Job
	if err := json.Unmarshal(data, &job); err != nil {
		return nil, fmt.Errorf("unmarshal job: %w", err)
	}
	return &job, nil
}

// RecoverStale re-enqueues jobs that have been in the processing set for longer
// than timeout, which indicates a crashed worker. Returns the number recovered.
func (q *RedisQueue) RecoverStale(ctx context.Context, timeout time.Duration) (int, error) {
	entries, err := q.client.HGetAll(ctx, processingKey).Result()
	if err != nil {
		return 0, fmt.Errorf("hgetall processing: %w", err)
	}

	cutoff := time.Now().Add(-timeout).UnixMilli()
	recovered := 0

	for jobID, tsStr := range entries {
		ts, err := strconv.ParseInt(tsStr, 10, 64)
		if err != nil {
			continue
		}
		if ts > cutoff {
			continue // still within the allowed window
		}

		data, err := q.client.Get(ctx, jobKey(jobID)).Bytes()
		if err != nil {
			continue
		}
		var job Job
		if err := json.Unmarshal(data, &job); err != nil {
			continue
		}

		// Remove from processing first, then re-enqueue.
		if err := q.client.HDel(ctx, processingKey, jobID).Err(); err != nil {
			continue
		}
		if err := q.Requeue(ctx, &job); err != nil {
			continue
		}
		recovered++
	}

	return recovered, nil
}

// RetryDead removes a job from the dead-letter list, resets its retry counter,
// and re-enqueues it as a fresh pending job.
func (q *RedisQueue) RetryDead(ctx context.Context, jobID string) (*Job, error) {
	job, err := q.GetJob(ctx, jobID)
	if err != nil {
		return nil, err
	}
	if job == nil {
		return nil, nil
	}
	if job.Status != StatusDead {
		return nil, fmt.Errorf("job %s is not in dead status (current: %s)", jobID, job.Status)
	}

	// Remove from the dead-letter list (all occurrences, just in case).
	q.client.LRem(ctx, deadKey, 0, jobID)

	// Decrement the dead counter to keep stats consistent.
	q.client.Decr(ctx, statsPrefix+"dead")

	job.Retries = 0
	job.Error = ""
	job.Status = StatusPending
	job.UpdatedAt = time.Now()

	if err := q.Enqueue(ctx, job); err != nil {
		return nil, fmt.Errorf("re-enqueue job: %w", err)
	}
	return job, nil
}
