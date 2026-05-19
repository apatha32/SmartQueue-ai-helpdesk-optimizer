package api

import "github.com/gin-gonic/gin"

func NewRouter(h *Handler) *gin.Engine {
	r := gin.Default()

	r.GET("/health", h.Health)

	v1 := r.Group("/api/v1")
	{
		v1.POST("/jobs", h.SubmitJob)
		v1.GET("/jobs/:id", h.GetJob)
		v1.POST("/jobs/:id/retry", h.RetryJob)
		v1.GET("/stats", h.GetStats)
	}

	return r
}
