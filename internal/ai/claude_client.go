package ai

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
)

const (
	anthropicAPIURL = "https://api.anthropic.com/v1/messages"
	anthropicModel  = "claude-sonnet-4-20250514"
	anthropicVersion = "2023-06-01"
	maxTokens       = 1024
)

type claudeRequest struct {
	Model     string    `json:"model"`
	MaxTokens int       `json:"max_tokens"`
	Messages  []message `json:"messages"`
}

type message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type claudeResponse struct {
	Content []contentBlock `json:"content"`
	Error   *claudeError   `json:"error,omitempty"`
}

type contentBlock struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type claudeError struct {
	Type    string `json:"type"`
	Message string `json:"message"`
}

// Complete sends a single user message to Claude and returns the text response.
func Complete(ctx context.Context, task string) (string, error) {
	apiKey := os.Getenv("ANTHROPIC_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("ANTHROPIC_API_KEY environment variable not set")
	}

	reqBody := claudeRequest{
		Model:     anthropicModel,
		MaxTokens: maxTokens,
		Messages: []message{
			{Role: "user", Content: task},
		},
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, anthropicAPIURL, bytes.NewReader(bodyBytes))
	if err != nil {
		return "", fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", anthropicVersion)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read response: %w", err)
	}

	var claudeResp claudeResponse
	if err := json.Unmarshal(respBytes, &claudeResp); err != nil {
		return "", fmt.Errorf("unmarshal response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		if claudeResp.Error != nil {
			return "", fmt.Errorf("anthropic API error (%d): %s", resp.StatusCode, claudeResp.Error.Message)
		}
		return "", fmt.Errorf("anthropic API returned status %d", resp.StatusCode)
	}

	if len(claudeResp.Content) == 0 {
		return "", fmt.Errorf("empty response from Claude")
	}

	return claudeResp.Content[0].Text, nil
}
