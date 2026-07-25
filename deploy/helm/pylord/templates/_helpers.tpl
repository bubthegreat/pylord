{{/* Chart name, overridable. */}}
{{- define "pylord.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Fully qualified resource name. */}}
{{- define "pylord.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := include "pylord.name" . }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/* Labels on every resource. */}}
{{- define "pylord.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{ include "pylord.selectorLabels" . }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/* Selector labels -- immutable, so nothing derived from values here. */}}
{{- define "pylord.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pylord.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* The Secret holding the database password/URL. */}}
{{- define "pylord.dbSecretName" -}}
{{- if .Values.mysql.auth.existingSecret }}
{{- .Values.mysql.auth.existingSecret }}
{{- else }}
{{- printf "%s-db" (include "pylord.fullname" .) }}
{{- end }}
{{- end }}

{{/*
The SQLAlchemy URL the game connects with.

utf8mb4 is not optional: character names and mail are free text, and the
older utf8 alias is a three-byte subset that cannot store an emoji.
*/}}
{{- define "pylord.dbUrl" -}}
{{- printf "mysql+aiomysql://%s:%s@%s-mysql:3306/%s?charset=utf8mb4" .Values.mysql.user .Values.mysql.auth.password (include "pylord.fullname" .) .Values.mysql.database }}
{{- end }}

{{/* The PVC the deployment mounts: an existing one, or ours. */}}
{{- define "pylord.claimName" -}}
{{- if .Values.persistence.existingClaim }}
{{- .Values.persistence.existingClaim }}
{{- else }}
{{- printf "%s-data" (include "pylord.fullname" .) }}
{{- end }}
{{- end }}
