{{/*
=============================================================================
InfraProbe Helm Chart — Template Helpers
=============================================================================
Standard helper templates for name generation, label construction,
and selector label construction.
=============================================================================
*/}}

{{/*
Expand the name of the chart.
Truncated to 63 characters (Kubernetes name length limit).
*/}}
{{- define "infraprobe.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a fully qualified app name.
We truncate to 63 chars because Kubernetes name fields are limited to this.
If release name contains the chart name it will be used as a full name.
*/}}
{{- define "infraprobe.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "infraprobe.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "infraprobe.labels" -}}
helm.sh/chart: {{ include "infraprobe.chart" . }}
{{ include "infraprobe.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels used in Deployment matchLabels and Service selectors.
These must remain immutable across upgrades.
*/}}
{{- define "infraprobe.selectorLabels" -}}
app.kubernetes.io/name: {{ include "infraprobe.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the ServiceAccount to use.
*/}}
{{- define "infraprobe.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "infraprobe.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
