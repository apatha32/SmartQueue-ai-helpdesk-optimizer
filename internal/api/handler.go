package api

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"distributed-task-queue/internal/queue"
)

// Handler holds dependencies for HTTP handlers.
type Handler struct {
	queue queue.Queue
}

func NewHandler(q queue.Queue) *Handler {
	return &Handler{queue: q}
}

type submitRequest struct {
	Type       string         `json:"type"        binding:"required"`
	Payload    map[string]any `json:"payload"`
	Priority   int            `json:"priority"`    // 1=high 2=medium 3=low, default 2
	MaxRetries int            `json:"max_retries"` // default 3
}

// POST /api/v1/jobs — enqueue a new job.
func (h *Handler) SubmitJob(c *gin.Context) {
	var req submitRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Priority < 1 || req.Priority > 3 {
		req.Priority = int(queue.PriorityMedium)
	}
	if req.MaxRetries == 0 {
		req.MaxRetries = 3
	}

	job := &queue.Job{
		ID:         uuid.New().String(),
		Type:       req.Type,
		Payload:    req.Payload,
		Priority:   queue.Priority(req.Priority),
		Status:     queue.StatusPending,
		MaxRetries: req.MaxRetries,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	if err := h.queue.Enqueue(c.Request.Context(), job); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, job)
}

// GET /api/v1/stats — return current queue counters.
func (h *Handler) GetStats(c *gin.Context) {
	stats, err := h.queue.Stats(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

// GET /api/v1/jobs/:id — fetch a single job by ID.
func (h *Handler) GetJob(c *gin.Context) {
	job, err := h.queue.GetJob(c.Request.Context(), c.Param("id"))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if job == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}
	c.JSON(http.StatusOK, job)
}

// POST /api/v1/jobs/:id/retry — requeue a dead-letter job.
func (h *Handler) RetryJob(c *gin.Context) {
	job, err := h.queue.RetryDead(c.Request.Context(), c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if job == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}
	c.JSON(http.StatusOK, job)
}

// GET /api/v1/jobs/dead — list dead-letter jobs (newest first, up to 50).
func (h *Handler) ListDeadJobs(c *gin.Context) {
	jobs, err := h.queue.ListDeadJobs(c.Request.Context(), 50)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if jobs == nil {
		jobs = []*queue.Job{}
	}
	c.JSON(http.StatusOK, jobs)
}

// GET /health — liveness probe.
func (h *Handler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}
