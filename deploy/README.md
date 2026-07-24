# Deploying pylord

The realm runs on the homelab k3s cluster as a Helm release, delivered by
ArgoCD. Nothing is applied by hand: CI builds the image, writes the new tag
into `values/prod.yaml`, and Argo rolls it out.

```
deploy/
  helm/pylord/     the chart (the only place manifests are defined)
  values/          per-environment values: local.yaml, prod.yaml
  argocd/          the Application manifest to register in homelab-app-config
```

## Layout decisions

- **One chart, values per environment.** The previous convention in this
  homelab was kustomize overlays (see `kbk`); this is the Helm equivalent,
  and Argo renders it the same way.
- **LoadBalancer, not the shared nginx TCP ConfigMap.** Telnet needs a raw
  TCP port. `kbk` routes it through `ingress-nginx`'s `tcp-services`
  ConfigMap, which means editing a cluster-wide object owned by another
  Argo app for every new game. MetalLB is available (`general-pool`,
  192.168.0.41-100), so pylord takes its own address instead and touches
  nothing shared. Set `service.type: ClusterIP` and add a `tcp-services`
  entry if you'd rather have the nginx route.
- **The volume outlives the release.** `longhorn-retain`, plus
  `helm.sh/resource-policy: keep` and `argocd.argoproj.io/sync-options:
  Delete=false` on the PVC: deleting or pruning the Application does not
  delete anyone's character.
- **`Recreate`, one replica.** SQLite has a single writer and the volume is
  ReadWriteOnce.
- **IGMs are seeded, not baked.** An init container copies the image's
  bundled IGMs onto the volume the first time only, so a sysop can edit or
  remove them without rebuilding.

## First-time setup

1. **Docker Hub token** — add a `DOCKER_HUB_TOKEN` repository secret to
   `bubthegreat/pylord` (Settings → Secrets → Actions) so the build
   workflow can push `bubthegreat/pylord`.

2. **Register the app with Argo** — copy the Application into the GitOps
   repo and commit:

   ```sh
   cp deploy/argocd/pylord-prod.yaml ../homelab-app-config/apps/
   cd ../homelab-app-config && git add apps/pylord-prod.yaml \
     && git commit -m "feat: deploy pylord to prod" && git push
   ```

   The root app (`app-config-root`) recurses `apps/`, so the realm appears
   within a sync cycle. Watch it:

   ```sh
   kubectl -n argocd get application pylord-prod -w
   ```

3. **Find the address and play**:

   ```sh
   kubectl -n pylord-prod get svc pylord \
     -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
   telnet <that address> 2323
   ```

## Day-to-day

| Task | How |
|------|-----|
| Ship a change | Merge to `main`. CI builds, writes the tag to `values/prod.yaml`, Argo syncs. |
| Change a game knob | Edit `values/prod.yaml`'s `game:` block and push — the config checksum restarts the pod. |
| Roll back | Revert the tag commit, or `argocd app rollback pylord-prod`. |
| Sysop CLI | `kubectl -n pylord-prod exec deploy/pylord -- pylord players --config /config/config.toml` |
| Back up the realm | `kubectl -n pylord-prod exec deploy/pylord -- cat /data/lord.db > lord.db` (Longhorn also snapshots the volume). |

## Local development

`tilt up` runs the same chart against a local cluster with
`values/local.yaml` (ClusterIP + port-forward on 2323, a small volume, and a
one-minute fight-regeneration clock so the timer is quick to watch). Editing
anything under `pylord/` or `igms/` live-syncs into the pod; changing
dependencies rebuilds the image.

Without a cluster, `uv run pylord serve` and `uv run pylord smoke` need
nothing but the repo.
