{{/*
Expand the name of the chart.
*/}}
{{- define "dtq.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully-qualified app name.
*/}}
{{- define "dtq.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label.
*/}}
{{- define "dtq.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "dtq.labels" -}}
helm.sh/chart: {{ include "dtq.chart" . }}
{{ include "dtq.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "dtq.selectorLabels" -}}
app.kubernetes.io/name: {{ include "dtq.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Redis service address — used by API and worker as REDIS_ADDR.
*/}}
{{- define "dtq.redisAddr" -}}
{{- printf "%s-redis:%d" (include "dtq.fullname" .) (.Values.redis.service.port | int) }}
{{- end }}

{{/*
Resolve a full image reference: <registry>/<repository>:<tag>
*/}}
{{- define "dtq.image" -}}
{{- $registry := .registry }}
{{- $repo     := .repository }}
{{- $tag      := .tag | default "latest" }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repo $tag }}
{{- else }}
{{- printf "%s:%s" $repo $tag }}
{{- end }}
{{- end }}
