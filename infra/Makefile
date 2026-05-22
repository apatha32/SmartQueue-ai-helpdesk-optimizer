CLUSTER_NAME ?= dtq-cluster
REGION       ?= us-east-1
NAMESPACE    ?= dtq
ARGOCD_NS    ?= argocd
HELM_RELEASE ?= dtq

.PHONY: help tf-init tf-plan tf-apply tf-destroy \
        kubeconfig bootstrap argocd-apply \
        helm-lint helm-dry-run \
        argocd-password port-forward-argocd port-forward-api \
        status clean

help:   ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'

# ── Terraform ────────────────────────────────────────────────────────────────

tf-init:   ## Initialise Terraform (run once)
	cd terraform && terraform init

tf-plan:   ## Preview infrastructure changes
	cd terraform && terraform plan

tf-apply:  ## Provision EKS cluster, ECR repos, IAM roles
	cd terraform && terraform apply -auto-approve

tf-destroy: ## DESTROY all infrastructure (irreversible)
	cd terraform && terraform destroy

# ── Kubernetes / kubectl ──────────────────────────────────────────────────────

kubeconfig: ## Configure kubectl to point at the EKS cluster
	aws eks update-kubeconfig --region $(REGION) --name $(CLUSTER_NAME)

# ── Bootstrap (run once after tf-apply) ──────────────────────────────────────

bootstrap: kubeconfig _install-argocd _install-prometheus _install-adapter argocd-apply  ## Full one-shot cluster bootstrap

_install-argocd:
	kubectl create namespace $(ARGOCD_NS) --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n $(ARGOCD_NS) \
	  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
	kubectl wait --for=condition=available --timeout=180s \
	  deployment/argocd-server -n $(ARGOCD_NS)
	@echo "ArgoCD installed."

_install-prometheus:
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm repo update
	helm upgrade --install kube-prometheus-stack \
	  prometheus-community/kube-prometheus-stack \
	  --namespace monitoring --create-namespace \
	  --set grafana.adminPassword=admin \
	  --wait
	@echo "kube-prometheus-stack installed."

_install-adapter:  ## Install prometheus-adapter with custom queue-depth metric rule
	helm upgrade --install prometheus-adapter \
	  prometheus-community/prometheus-adapter \
	  --namespace monitoring \
	  --values prometheus-adapter-values.yaml \
	  --wait
	@echo "prometheus-adapter installed."

argocd-apply:  ## Apply ArgoCD project and application manifests
	kubectl apply -f argocd/namespace.yaml
	kubectl apply -f argocd/project.yaml
	kubectl apply -f argocd/application.yaml
	@echo "ArgoCD Application 'dtq' created — it will sync automatically."

# ── Helm (local dev / CI validation) ─────────────────────────────────────────

helm-lint:  ## Lint the Helm chart
	helm lint helm/dtq

helm-dry-run:  ## Dry-run render the chart (shows all manifests without deploying)
	helm install $(HELM_RELEASE) helm/dtq \
	  --namespace $(NAMESPACE) \
	  --dry-run --debug

# ── Utilities ─────────────────────────────────────────────────────────────────

argocd-password:  ## Print the initial ArgoCD admin password
	@kubectl -n $(ARGOCD_NS) get secret argocd-initial-admin-secret \
	  -o jsonpath="{.data.password}" | base64 -d && echo

port-forward-argocd:  ## Forward ArgoCD UI to localhost:8080
	kubectl port-forward svc/argocd-server -n $(ARGOCD_NS) 8080:443

port-forward-api:  ## Forward DTQ API to localhost:8888
	kubectl port-forward svc/$(HELM_RELEASE)-dtq-api -n $(NAMESPACE) 8888:8080

status:  ## Show pods, HPA, and queue metrics
	@echo "\n=== Pods ==="
	kubectl get pods -n $(NAMESPACE)
	@echo "\n=== HPA ==="
	kubectl get hpa -n $(NAMESPACE)
	@echo "\n=== Custom metric: dtq_queue_depth ==="
	kubectl get --raw \
	  "/apis/external.metrics.k8s.io/v1beta1/namespaces/$(NAMESPACE)/dtq_queue_depth" \
	  2>/dev/null | python3 -m json.tool || echo "(metric not yet available)"
